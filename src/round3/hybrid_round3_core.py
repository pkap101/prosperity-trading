from __future__ import annotations

import json
import math
from typing import Dict, List, Optional, Sequence

from datamodel import Order, OrderDepth, Trade, TradingState

HYDRO = "HYDROGEL_PACK"
VELVET = "VELVETFRUIT_EXTRACT"
CORE_VOUCHERS: list[str] = [
    "VEV_4000",
    "VEV_4500",
    "VEV_5000",
    "VEV_5100",
    "VEV_5200",
    "VEV_5300",
    "VEV_5400",
    "VEV_5500",
]
WIDE_VOUCHERS: list[str] = ["VEV_6000", "VEV_6500"]
ALL_VOUCHERS: list[str] = CORE_VOUCHERS + WIDE_VOUCHERS
VOUCHER_STRIKES: Dict[str, int] = {p: int(p.split("_")[1]) for p in ALL_VOUCHERS}
POSITION_LIMITS: Dict[str, int] = {HYDRO: 200, VELVET: 200, **{p: 300 for p in ALL_VOUCHERS}}

# Tiny sigma constants from v22 are calibrated to the tick-time Black-Scholes convention used there.
SIGMA_SMILE = {
    4000: 0.0008960,
    4500: 0.0004921,
    5000: 0.0002616,
    5100: 0.0002558,
    5200: 0.0002671,
    5300: 0.0002705,
    5400: 0.0002515,
    5500: 0.0002697,
    6000: 0.0002400,
    6500: 0.0002250,
}
T_EXPIRY_TICKS = 30_000
TICK_STEP = 100
FLOW_DECAY = 0.92
TAKE_WIDTH = 1
ANCHOR_WARMUP = 100
DIVERGE_TAKE_SIZE = 30
SPREAD_FRACTION = 0.5
VOL_WINDOW = 100
VOL_SCALE_MAX = 2.0


def search_sells(depth: OrderDepth):
    for price in sorted(depth.sell_orders):
        yield price, -depth.sell_orders[price]


def search_buys(depth: OrderDepth):
    for price in sorted(depth.buy_orders, reverse=True):
        yield price, depth.buy_orders[price]


def full_depth_mid(depth: OrderDepth) -> float:
    bids, asks = list(search_buys(depth)), list(search_sells(depth))
    bv = sum(v for _, v in bids)
    av = sum(v for _, v in asks)
    if bv <= 0 or av <= 0:
        return (max(depth.buy_orders) + min(depth.sell_orders)) / 2.0
    return (sum(p * v for p, v in bids) / bv + sum(p * v for p, v in asks) / av) / 2.0


def microprice(depth: OrderDepth) -> float:
    bb = max(depth.buy_orders)
    ba = min(depth.sell_orders)
    bv = depth.buy_orders[bb]
    av = -depth.sell_orders[ba]
    tot = bv + av
    return (bb * av + ba * bv) / tot if tot > 0 else (bb + ba) / 2.0


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_call(spot: float, strike: float, t: float, sigma: float) -> float:
    if t <= 0 or sigma <= 0 or spot <= 0:
        return max(spot - strike, 0.0)
    sqrt_t = math.sqrt(t)
    d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * t) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    return spot * norm_cdf(d1) - strike * norm_cdf(d2)


def realized_vol(mids: Sequence[float]) -> float:
    if len(mids) < 2:
        return 0.0
    diffs = [mids[i] - mids[i - 1] for i in range(1, len(mids))]
    mean = sum(diffs) / len(diffs)
    return math.sqrt(sum((d - mean) ** 2 for d in diffs) / len(diffs))


def trim(history: list, window: int) -> None:
    if len(history) > window:
        del history[: len(history) - window]


def aggressor_side(price: int, best_bid: int, best_ask: int) -> int:
    if price >= best_ask:
        return 1
    if price <= best_bid:
        return -1
    return 0


def update_flow_threshold_scratch(scratch: dict, market_trades: list[Trade], best_bid: int, best_ask: int) -> float:
    flow = scratch.get("_flow", 0.0) * FLOW_DECAY
    for trade in market_trades or []:
        if trade.price >= best_ask:
            flow += trade.quantity
        elif trade.price <= best_bid:
            flow -= trade.quantity
    scratch["_flow"] = flow
    return flow


def update_aggressor_history(scratch: dict, market_trades: list[Trade], best_bid: int, best_ask: int) -> float:
    flow = sum(aggressor_side(t.price, best_bid, best_ask) * t.quantity for t in market_trades or [])
    hist = scratch.setdefault("agg_flow", [])
    hist.append(flow)
    trim(hist, 10)
    return sum(hist)


def mm_bot_prices(depth: OrderDepth, adverse_threshold: int) -> tuple[Optional[int], Optional[int]]:
    if not depth.buy_orders or not depth.sell_orders:
        return None, None
    buy_levels = sorted(depth.buy_orders.items(), reverse=True)
    sell_levels = sorted(depth.sell_orders.items())
    mm_bid = buy_levels[0][0]
    mm_ask = sell_levels[0][0]
    for price, volume in buy_levels[:3]:
        if volume >= adverse_threshold:
            mm_bid = price
            break
    for price, volume in sell_levels[:3]:
        if -volume >= adverse_threshold:
            mm_ask = price
            break
    return mm_bid, mm_ask


def mmbot_underlier_orders(product: str, cfg: dict, state: TradingState, scratch: dict) -> list[Order]:
    depth = state.order_depths.get(product)
    if depth is None or not depth.buy_orders or not depth.sell_orders:
        return []
    mm_bid, mm_ask = mm_bot_prices(depth, cfg["threshold"])
    if mm_bid is None or mm_ask is None:
        return []
    current_mid = (mm_bid + mm_ask) / 2.0
    prev_mid = scratch.get("prev_mid", current_mid)
    log_ret = math.log(max(current_mid, 1.0) / max(prev_mid, 1.0))
    pred_mid = current_mid * math.exp(cfg["revert"] * log_ret)
    pos = state.position.get(product, 0)
    theo = pred_mid - cfg["retreat"] * pos
    buy_price = min(int(math.floor(theo)), max(depth.buy_orders) + 1)
    sell_price = max(int(math.ceil(theo)), min(depth.sell_orders) - 1)
    bid_edge = theo - buy_price
    ask_edge = sell_price - theo
    buy_qty = int(max(0.0, bid_edge / cfg["edge_per_lot"]))
    sell_qty = int(max(0.0, ask_edge / cfg["edge_per_lot"]))
    buy_qty = min(buy_qty, cfg["cap"], POSITION_LIMITS[product] - pos)
    sell_qty = min(sell_qty, cfg["cap"], POSITION_LIMITS[product] + pos)
    orders: list[Order] = []
    if buy_qty > 0 and buy_price < min(depth.sell_orders):
        orders.append(Order(product, buy_price, buy_qty))
    if sell_qty > 0 and sell_price > max(depth.buy_orders) and sell_price > buy_price:
        orders.append(Order(product, sell_price, -sell_qty))
    scratch["prev_mid"] = current_mid
    return orders


def kalman_underlier_orders(cfg: dict, state: TradingState, scratch: dict) -> list[Order]:
    depth = state.order_depths.get(cfg["product"])
    if not depth or not depth.buy_orders or not depth.sell_orders:
        return []
    product = cfg["product"]
    limit = cfg["position_limit"]
    bb = max(depth.buy_orders)
    ba = min(depth.sell_orders)
    bv_tob = depth.buy_orders[bb]
    av_tob = -depth.sell_orders[ba]
    tot = bv_tob + av_tob
    micro = (bb * av_tob + ba * bv_tob) / tot if tot > 0 else (bb + ba) / 2.0
    mid = (bb + ba) / 2.0

    k_ss = cfg["k_ss"]
    fair = scratch.get("_f", micro)
    innov = micro - fair
    err_ema = scratch.get("_err", abs(innov))
    err_ema += k_ss * (abs(innov) - err_ema)
    fair += (k_ss / (1.0 + err_ema)) * innov
    scratch["_f"], scratch["_err"] = fair, err_ema

    n = scratch.get("_n", 0) + 1
    s2 = scratch.get("_s2", 0.0) + (mid - fair) ** 2
    scratch["_n"], scratch["_s2"] = n, s2
    sigma = max(1.0, (s2 / n) ** 0.5) if n > 50 else cfg["sigma_init"]

    anchor = cfg["fair_static"]
    target = max(-limit, min(limit, round(cfg["mr_gain"] * (anchor - mid) / sigma)))
    take_max_pay = cfg["take_max_pay"]
    quote_edge = cfg["quote_edge"]
    quote_size = cfg["quote_size"]

    orders: list[Order] = []
    bv = sv = 0
    position = state.position.get(product, 0)
    delta = target - position
    if delta > 0:
        for ask in sorted(depth.sell_orders):
            if ask > fair + take_max_pay:
                break
            room = min(-depth.sell_orders[ask], delta - bv, limit - position - bv)
            if room <= 0:
                break
            orders.append(Order(product, ask, room))
            bv += room
    elif delta < 0:
        need = -delta
        for bid in sorted(depth.buy_orders, reverse=True):
            if bid < fair - take_max_pay:
                break
            room = min(depth.buy_orders[bid], need - sv, limit + position - sv)
            if room <= 0:
                break
            orders.append(Order(product, bid, -room))
            sv += room

    baaf = min((p for p in depth.sell_orders if p >= fair + quote_edge), default=None)
    bbbf = max((p for p in depth.buy_orders if p <= fair - quote_edge), default=None)
    if bbbf is not None:
        buy_q = min(quote_size, limit - position - bv)
        if buy_q > 0:
            orders.append(Order(product, bbbf + 1, buy_q))
    if baaf is not None:
        sell_q = min(quote_size, limit + position - sv)
        if sell_q > 0:
            orders.append(Order(product, baaf - 1, -sell_q))
    return orders


def divergence_take_orders(cfg: dict, depth: OrderDepth, scratch: dict, position: int, anchor: float, mid: float) -> tuple[list[Order], int, int]:
    threshold = cfg.get("diverge_threshold", 0)
    if cfg.get("flow_threshold_tilt"):
        flow = scratch.get("_flow", 0.0)
        diverge = mid - anchor
        if diverge > 0 and flow > 1.0:
            threshold = max(1, threshold - 1)
        elif diverge < 0 and flow < -1.0:
            threshold = max(1, threshold - 1)
        elif diverge > 0 and flow < -1.0:
            threshold += 2
        elif diverge < 0 and flow > 1.0:
            threshold += 2
    if threshold <= 0 or scratch.get("anchor_n", 0) < ANCHOR_WARMUP:
        return [], 0, 0
    diverge = mid - anchor
    if abs(diverge) < threshold:
        return [], 0, 0

    product = cfg["product"]
    limit = cfg["position_limit"]
    max_pos = cfg.get("max_diverge_position", limit)
    out: list[Order] = []
    bought = sold = 0
    if diverge > 0 and position > -max_pos:
        room = position + max_pos
        for price, qty in search_buys(depth):
            cap = min(limit + position - sold, DIVERGE_TAKE_SIZE - sold, room - sold)
            if cap <= 0:
                break
            take = min(qty, cap)
            out.append(Order(product, price, -take))
            sold += take
    elif diverge < 0 and position < max_pos:
        room = max_pos - position
        for price, qty in search_sells(depth):
            cap = min(limit - position - bought, DIVERGE_TAKE_SIZE - bought, room - bought)
            if cap <= 0:
                break
            take = min(qty, cap)
            out.append(Order(product, price, take))
            bought += take
    return out, bought, sold


def take_orders(cfg: dict, depth: OrderDepth, fair: float, position: int) -> tuple[list[Order], int, int]:
    product = cfg["product"]
    limit = cfg["position_limit"]
    out: list[Order] = []
    bought = sold = 0
    for price, qty in search_sells(depth):
        if price >= fair - TAKE_WIDTH:
            break
        cap = limit - position - bought
        if cap <= 0:
            break
        take = min(qty, cap)
        out.append(Order(product, price, take))
        bought += take
    for price, qty in search_buys(depth):
        if price <= fair + TAKE_WIDTH:
            break
        cap = limit + position - sold
        if cap <= 0:
            break
        take = min(qty, cap)
        out.append(Order(product, price, -take))
        sold += take
    return out, bought, sold


def make_quote(cfg: dict, scratch: dict, fair: float, best_bid: int, best_ask: int, position: int, bought: int, sold: int) -> list[Order]:
    product = cfg["product"]
    limit = cfg["position_limit"]
    qsize = cfg.get("quote_size", 20)
    out: list[Order] = []
    mode = cfg.get("quote_mode", "midpoint")
    if mode == "skewed":
        mids = scratch.setdefault("mids", [])
        mids.append((best_bid + best_ask) / 2.0)
        trim(mids, VOL_WINDOW)
        c = SPREAD_FRACTION
        if len(mids) >= VOL_WINDOW // 2:
            baseline = cfg.get("baseline_vol", 0.5)
            vol = realized_vol(mids)
            if vol > baseline and baseline > 0:
                c = min(1.0, SPREAD_FRACTION * min(VOL_SCALE_MAX, vol / baseline))
        skew = position * cfg.get("skew_per_unit", 0.02)
        bid_px = min(math.floor(fair - c * (fair - best_bid) - skew), best_ask - 1)
        ask_px = max(math.ceil(fair + c * (best_ask - fair) - skew), best_bid + 1)
    else:
        bid_px = min(math.floor((fair + best_bid) / 2.0), best_ask - 1)
        ask_px = max(math.ceil((fair + best_ask) / 2.0), best_bid + 1)

    buy = max(0, min(qsize, limit - position - bought))
    sell = max(0, min(qsize, limit + position - sold))
    if buy > 0 and bid_px < ask_px:
        out.append(Order(product, bid_px, buy))
    if sell > 0 and ask_px > bid_px:
        out.append(Order(product, ask_px, -sell))
    return out


def wide_strike_orders(product: str, cfg: dict, state: TradingState) -> list[Order]:
    depth = state.order_depths.get(product)
    if not depth or not depth.buy_orders or not depth.sell_orders:
        return []
    best_bid = max(depth.buy_orders)
    best_ask = min(depth.sell_orders)
    if best_bid == 0 and best_ask == 1:
        pos = state.position.get(product, 0)
        size = cfg.get("wide_quote_size", 7)
        buy_size = min(size, POSITION_LIMITS[product] - pos)
        sell_size = min(size, POSITION_LIMITS[product] + pos)
        orders: list[Order] = []
        if buy_size > 0:
            orders.append(Order(product, 0, buy_size))
        if sell_size > 0:
            orders.append(Order(product, 1, -sell_size))
        return orders
    return []


def voucher_orders(product: str, cfg: dict, state: TradingState, scratch: dict, spot: Optional[float]) -> list[Order]:
    if product in WIDE_VOUCHERS:
        return wide_strike_orders(product, cfg, state)
    depth = state.order_depths.get(product)
    if not depth or not depth.buy_orders or not depth.sell_orders:
        return []

    best_bid = max(depth.buy_orders)
    best_ask = min(depth.sell_orders)
    mid = (best_bid + best_ask) / 2.0
    fair = full_depth_mid(depth)

    flow_sum = 0.0
    if cfg.get("aggressor_lambda"):
        flow_sum = update_aggressor_history(scratch, state.market_trades.get(product, []), best_bid, best_ask)
        fair += cfg["aggressor_lambda"] * flow_sum
    if cfg.get("flow_threshold_tilt"):
        update_flow_threshold_scratch(scratch, state.market_trades.get(product, []), best_bid, best_ask)

    n = scratch.get("anchor_n", 0) + 1
    s = scratch.get("anchor_sum", 0.0) + mid
    scratch["anchor_n"], scratch["anchor_sum"] = n, s
    running_anchor = s / n

    bs_anchor = None
    if spot is not None and spot > 0 and cfg.get("bs_weight", 0.0) > 0:
        strike = VOUCHER_STRIKES[product]
        sigma = SIGMA_SMILE[strike]
        ttx = max(1.0, T_EXPIRY_TICKS - state.timestamp / TICK_STEP)
        bs_anchor = bs_call(spot, strike, ttx, sigma)

    run_w = cfg.get("running_weight", 1.0)
    bs_w = cfg.get("bs_weight", 0.0 if bs_anchor is None else cfg.get("bs_weight", 0.0))
    if bs_anchor is None or bs_w <= 0:
        anchor = running_anchor
    else:
        total = run_w + bs_w
        anchor = (run_w * running_anchor + bs_w * bs_anchor) / total if total > 0 else running_anchor

    effective_cfg = dict(cfg)
    guard = cfg.get("anchor_gap_guard")
    if bs_anchor is not None and guard is not None:
        gap = abs(running_anchor - bs_anchor)
        scratch["last_anchor_gap"] = gap
        if gap >= guard:
            effective_cfg["max_diverge_position"] = min(effective_cfg.get("max_diverge_position", POSITION_LIMITS[product]), cfg.get("guard_max_diverge_position", 40))
            effective_cfg["quote_size"] = min(effective_cfg.get("quote_size", 20), cfg.get("guard_quote_size", 12))
            if cfg.get("disable_diverge_on_guard"):
                effective_cfg["diverge_threshold"] = 10**9
    position = state.position.get(product, 0)

    if cfg.get("passive_only"):
        diverge = []
        d_bought = d_sold = 0
    else:
        diverge, d_bought, d_sold = divergence_take_orders(effective_cfg, depth, scratch, position, anchor, mid)
    pos_eff = position + d_bought - d_sold
    takes, bought, sold = take_orders(effective_cfg, depth, fair, pos_eff)
    bought += d_bought
    sold += d_sold
    quotes = make_quote(effective_cfg, scratch, fair, best_bid, best_ask, position, bought, sold)
    return diverge + takes + quotes


def call_spread_arb_orders(state: TradingState, allowed: Sequence[str]) -> dict[str, list[Order]]:
    allowed_sorted = sorted(allowed, key=lambda p: VOUCHER_STRIKES[p])
    arb_orders: dict[str, list[Order]] = {}
    used: dict[str, list[int]] = {p: [0, 0] for p in allowed_sorted}

    def remaining_buy(prod: str) -> int:
        pos = state.position.get(prod, 0)
        return POSITION_LIMITS[prod] - pos - used[prod][0]

    def remaining_sell(prod: str) -> int:
        pos = state.position.get(prod, 0)
        return POSITION_LIMITS[prod] + pos - used[prod][1]

    for i, low in enumerate(allowed_sorted):
        for high in allowed_sorted[i + 1 :]:
            od_lo = state.order_depths.get(low)
            od_hi = state.order_depths.get(high)
            if od_lo is None or od_hi is None:
                continue
            strike_diff = VOUCHER_STRIKES[high] - VOUCHER_STRIKES[low]
            if od_lo.buy_orders and od_hi.sell_orders:
                bid_lo = max(od_lo.buy_orders)
                ask_hi = min(od_hi.sell_orders)
                edge = bid_lo - ask_hi - strike_diff
                if edge > 0:
                    qty = min(od_lo.buy_orders[bid_lo], -od_hi.sell_orders[ask_hi], remaining_sell(low), remaining_buy(high))
                    if qty > 0:
                        arb_orders.setdefault(low, []).append(Order(low, bid_lo, -qty))
                        arb_orders.setdefault(high, []).append(Order(high, ask_hi, qty))
                        used[low][1] += qty
                        used[high][0] += qty
            if od_lo.sell_orders and od_hi.buy_orders:
                ask_lo = min(od_lo.sell_orders)
                bid_hi = max(od_hi.buy_orders)
                edge = bid_hi - ask_lo
                if edge > 0:
                    qty = min(-od_lo.sell_orders[ask_lo], od_hi.buy_orders[bid_hi], remaining_buy(low), remaining_sell(high))
                    if qty > 0:
                        arb_orders.setdefault(low, []).append(Order(low, ask_lo, qty))
                        arb_orders.setdefault(high, []).append(Order(high, bid_hi, -qty))
                        used[low][0] += qty
                        used[high][1] += qty
    return arb_orders


def make_trader_class(config: dict):
    class Trader:
        def run(self, state: TradingState):
            try:
                store = json.loads(state.traderData) if state.traderData else {}
                if not isinstance(store, dict):
                    store = {}
            except Exception:
                store = {}
            orders: dict[str, list[Order]] = {}

            spot = None
            vfe_depth = state.order_depths.get(VELVET)
            if vfe_depth and vfe_depth.buy_orders and vfe_depth.sell_orders:
                spot = microprice(vfe_depth)

            underlying_mode = config.get("underlying_mode", "mmbot")
            for prod, ucfg in config.get("underlier_cfg", {}).items():
                scratch = store.setdefault(prod, {})
                if underlying_mode == "kalman":
                    ors = kalman_underlier_orders(ucfg, state, scratch)
                else:
                    ors = mmbot_underlier_orders(prod, ucfg, state, scratch)
                if ors:
                    orders[prod] = ors

            if config.get("enable_call_spread_arb"):
                arb = call_spread_arb_orders(state, config.get("arb_products", CORE_VOUCHERS))
                for prod, ors in arb.items():
                    if ors:
                        orders.setdefault(prod, []).extend(ors)

            for prod, vcfg in config.get("voucher_cfg", {}).items():
                scratch = store.setdefault(prod, {})
                ors = voucher_orders(prod, vcfg, state, scratch, spot)
                if ors:
                    orders.setdefault(prod, []).extend(ors)

            return orders, 0, json.dumps(store, separators=(",", ":"))

    return Trader
