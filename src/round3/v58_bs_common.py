import json
import math
from dataclasses import dataclass
from typing import Dict, Any, Optional

from datamodel import Order, TradingState

TAKE_WIDTH = 1
ANCHOR_WARMUP = 100
BASE_DIVERGE_TAKE_SIZE = 30

INFORMED_SIZE_VFE = 11
INFORMED_GAIN_S = 10
INFORMED_DECAY = 0.998

ROUND3_START_TTE_DAYS = 5.0
TIMESTAMP_UNITS_PER_DAY = 1_000_000.0
YEAR_DAYS = 365.0
MIN_TTE_DAYS = 4.0

VELVET = "VELVETFRUIT_EXTRACT"

KALMAN_MR_PRODUCTS = [
    {
        "product": "HYDROGEL_PACK",
        "position_limit": 200,
        "k_ss": 0.02,
        "fair_static": 10030,
        "mr_gain": 1000,
        "sigma_init": 30.0,
        "take_max_pay": -6,
        "quote_edge": 3,
        "quote_size": 30,
    },
    {
        "product": VELVET,
        "position_limit": 200,
        "k_ss": 0.02,
        "fair_static": 5275,
        "mr_gain": 2000,
        "sigma_init": 15.0,
        "take_max_pay": -2,
        "quote_edge": 1,
        "quote_size": 30,
    },
]

ZSCORE_PRODUCTS = [
    {"product": "VEV_4000", "position_limit": 300, "quote_size": 30, "diverge_threshold": 18, "max_diverge_position": 295},
    {"product": "VEV_4500", "position_limit": 300, "quote_size": 30, "diverge_threshold": 18, "max_diverge_position": 295},
    {"product": "VEV_5000", "position_limit": 300, "quote_size": 30, "diverge_threshold": 15, "max_diverge_position": 295},
    {"product": "VEV_5100", "position_limit": 300, "quote_size": 30, "diverge_threshold": 13, "max_diverge_position": 295},
    {"product": "VEV_5200", "position_limit": 300, "quote_size": 30, "diverge_threshold": 10, "max_diverge_position": 295},
    {"product": "VEV_5300", "position_limit": 300, "quote_size": 30, "diverge_threshold": 7, "max_diverge_position": 295},
    {"product": "VEV_5400", "position_limit": 300, "quote_size": 30, "diverge_threshold": 4, "max_diverge_position": 295},
    {"product": "VEV_5500", "position_limit": 300, "quote_size": 30, "diverge_threshold": 2, "max_diverge_position": 295},
]


@dataclass
class VoucherOverlayConfig:
    mode: str
    residual_tol: float
    blend_alpha: float = 0.0
    disagree_scale: float = 1.0
    quote_shift_scale: float = 0.0


def search_sells(depth):
    for p in sorted(depth.sell_orders):
        yield p, -depth.sell_orders[p]


def search_buys(depth):
    for p in sorted(depth.buy_orders, reverse=True):
        yield p, depth.buy_orders[p]


def full_depth_mid(depth):
    bids, asks = list(search_buys(depth)), list(search_sells(depth))
    bv, av = sum(v for _, v in bids), sum(v for _, v in asks)
    if bv <= 0 or av <= 0:
        return (max(depth.buy_orders) + min(depth.sell_orders)) / 2
    return (sum(p * v for p, v in bids) / bv + sum(p * v for p, v in asks) / av) / 2


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _bs_call_price(spot: float, strike: float, t_years: float, sigma: float) -> float:
    if t_years <= 0.0:
        return max(0.0, spot - strike)
    if sigma <= 1e-6:
        return max(0.0, spot - strike)
    root_t = math.sqrt(t_years)
    d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * t_years) / (sigma * root_t)
    d2 = d1 - sigma * root_t
    return spot * _norm_cdf(d1) - strike * _norm_cdf(d2)


def _implied_vol_call(price: float, spot: float, strike: float, t_years: float) -> Optional[float]:
    intrinsic = max(0.0, spot - strike)
    if t_years <= 0.0 or price <= intrinsic + 1e-6:
        return None
    lo, hi = 1e-4, 3.0
    f_lo = _bs_call_price(spot, strike, t_years, lo) - price
    f_hi = _bs_call_price(spot, strike, t_years, hi) - price
    if f_lo * f_hi > 0:
        return None
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        f_mid = _bs_call_price(spot, strike, t_years, mid) - price
        if abs(f_mid) < 1e-5:
            return mid
        if f_lo * f_mid <= 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return 0.5 * (lo + hi)


def _solve_quadratic_fit(points):
    # Fit sigma ~= a*m^2 + b*m + c with normal equations solved by Cramer's rule.
    s0 = len(points)
    s1 = sum(m for m, _ in points)
    s2 = sum(m * m for m, _ in points)
    s3 = sum(m * m * m for m, _ in points)
    s4 = sum(m * m * m * m for m, _ in points)
    y0 = sum(y for _, y in points)
    y1 = sum(m * y for m, y in points)
    y2 = sum(m * m * y for m, y in points)
    det = s0 * (s2 * s4 - s3 * s3) - s1 * (s1 * s4 - s3 * s2) + s2 * (s1 * s3 - s2 * s2)
    if abs(det) < 1e-12:
        return None
    det_c = y0 * (s2 * s4 - s3 * s3) - s1 * (y1 * s4 - s3 * y2) + s2 * (y1 * s3 - s2 * y2)
    det_b = s0 * (y1 * s4 - s3 * y2) - y0 * (s1 * s4 - s3 * s2) + s2 * (s1 * y2 - y1 * s2)
    det_a = s0 * (s2 * y2 - y1 * s3) - s1 * (s1 * y2 - y1 * s2) + y0 * (s1 * s3 - s2 * s2)
    return det_a / det, det_b / det, det_c / det


def _fit_sigma(smile_pts, m):
    if len(smile_pts) >= 3:
        coeffs = _solve_quadratic_fit(smile_pts)
        if coeffs is not None:
            a, b, c = coeffs
            return max(0.05, min(2.0, a * m * m + b * m + c))
    if smile_pts:
        return max(0.05, min(2.0, sum(iv for _, iv in smile_pts) / len(smile_pts)))
    return None


def _voucher_strike(product: str) -> float:
    return float(product.split("_")[1])


def build_voucher_bs_context(state: TradingState) -> Dict[str, Dict[str, float]]:
    velvet_depth = state.order_depths.get(VELVET)
    if velvet_depth is None or not velvet_depth.buy_orders or not velvet_depth.sell_orders:
        return {}

    spot_bid = max(velvet_depth.buy_orders)
    spot_ask = min(velvet_depth.sell_orders)
    spot_bid_vol = velvet_depth.buy_orders[spot_bid]
    spot_ask_vol = -velvet_depth.sell_orders[spot_ask]
    total_top = spot_bid_vol + spot_ask_vol
    if total_top <= 0:
        return {}

    spot_mid = (spot_bid + spot_ask) / 2.0
    spot_micro = (spot_bid * spot_ask_vol + spot_ask * spot_bid_vol) / total_top
    spot = 0.7 * spot_micro + 0.3 * spot_mid
    tte_days = max(MIN_TTE_DAYS, ROUND3_START_TTE_DAYS - state.timestamp / TIMESTAMP_UNITS_PER_DAY)
    t_years = tte_days / YEAR_DAYS
    root_t = math.sqrt(t_years)

    mids = {}
    smile_pts = []
    for cfg in ZSCORE_PRODUCTS:
        product = cfg["product"]
        depth = state.order_depths.get(product)
        if depth is None or not depth.buy_orders or not depth.sell_orders:
            continue
        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        mid = (best_bid + best_ask) / 2.0
        strike = _voucher_strike(product)
        iv = _implied_vol_call(mid, spot, strike, t_years)
        m = math.log(strike / spot) / root_t
        mids[product] = {"mid": mid, "m": m, "strike": strike, "iv": iv}
        if iv is not None:
            smile_pts.append((m, iv))

    context = {}
    for product, row in mids.items():
        fit_sigma = _fit_sigma(smile_pts, row["m"])
        if fit_sigma is None:
            continue
        bs_fair = _bs_call_price(spot, row["strike"], t_years, fit_sigma)
        context[product] = {
            "spot": spot,
            "tte_days": tte_days,
            "sigma": fit_sigma,
            "bs_fair": bs_fair,
            "residual": row["mid"] - bs_fair,
        }
    return context


def divergence_take_orders(cfg, depth, position, anchor, mid, take_size, max_pos):
    threshold = cfg.get("diverge_threshold", 0)
    if abs(mid - anchor) < threshold:
        return [], 0, 0

    product, limit = cfg["product"], cfg["position_limit"]
    out, bought, sold = [], 0, 0
    diverge = mid - anchor
    if diverge > 0 and position > -max_pos:
        room = position + max_pos
        for price, qty in search_buys(depth):
            cap = min(limit + position - sold, take_size - sold, room - sold)
            if cap <= 0:
                break
            take = min(qty, cap)
            out.append(Order(product, price, -take))
            sold += take
    elif diverge < 0 and position < max_pos:
        room = max_pos - position
        for price, qty in search_sells(depth):
            cap = min(limit - position - bought, take_size - bought, room - bought)
            if cap <= 0:
                break
            take = min(qty, cap)
            out.append(Order(product, price, take))
            bought += take
    return out, bought, sold


def take_orders(cfg, depth, fair, position):
    product, limit = cfg["product"], cfg["position_limit"]
    out, bought, sold = [], 0, 0
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


def make_quote(cfg, fair, best_bid, best_ask, position, bought, sold):
    product, limit = cfg["product"], cfg["position_limit"]
    qsize = cfg.get("quote_size", 20)
    bid_px = min(math.floor((fair + best_bid) / 2), best_ask - 1)
    ask_px = max(math.ceil((fair + best_ask) / 2), best_bid + 1)
    buy = max(0, min(qsize, limit - position - bought))
    sell = max(0, min(qsize, limit + position - sold))
    out = []
    if buy > 0 and bid_px < ask_px:
        out.append(Order(product, bid_px, buy))
    if sell > 0 and ask_px > bid_px:
        out.append(Order(product, ask_px, -sell))
    return out


def zscore_orders(cfg, state, scratch, bs_ctx, overlay_cfg: VoucherOverlayConfig):
    depth = state.order_depths.get(cfg["product"])
    if not depth or not depth.buy_orders or not depth.sell_orders:
        return []

    best_bid = max(depth.buy_orders)
    best_ask = min(depth.sell_orders)
    mid = (best_bid + best_ask) / 2.0
    fair = full_depth_mid(depth)

    n = scratch.get("anchor_n", 0) + 1
    s = scratch.get("anchor_sum", 0.0) + mid
    scratch["anchor_n"], scratch["anchor_sum"] = n, s
    anchor = s / n
    position = state.position.get(cfg["product"], 0)
    diverge = mid - anchor

    overlay = bs_ctx.get(cfg["product"], {})
    residual = overlay.get("residual")
    bs_fair = overlay.get("bs_fair")

    take_size = BASE_DIVERGE_TAKE_SIZE
    max_pos = cfg.get("max_diverge_position", 60)
    fair_for_takes = fair
    fair_for_quotes = fair
    allow_diverge = scratch.get("anchor_n", 0) >= ANCHOR_WARMUP

    if residual is not None and bs_fair is not None:
        if overlay_cfg.mode == "confirm":
            if diverge > 0 and residual < -overlay_cfg.residual_tol:
                allow_diverge = False
            elif diverge < 0 and residual > overlay_cfg.residual_tol:
                allow_diverge = False
        elif overlay_cfg.mode == "blend":
            fair_for_takes = (1.0 - overlay_cfg.blend_alpha) * fair + overlay_cfg.blend_alpha * bs_fair
            fair_for_quotes = fair_for_takes + overlay_cfg.quote_shift_scale * residual
        elif overlay_cfg.mode == "haircut":
            disagree = (diverge > 0 and residual < -overlay_cfg.residual_tol) or (diverge < 0 and residual > overlay_cfg.residual_tol)
            if disagree:
                take_size = max(8, int(round(BASE_DIVERGE_TAKE_SIZE * overlay_cfg.disagree_scale)))
                max_pos = max(80, int(round(max_pos * overlay_cfg.disagree_scale)))

    diverge_orders, d_bought, d_sold = [], 0, 0
    if allow_diverge and abs(diverge) >= cfg.get("diverge_threshold", 0):
        diverge_orders, d_bought, d_sold = divergence_take_orders(
            cfg, depth, position, anchor, mid, take_size, max_pos
        )

    pos_eff = position + d_bought - d_sold
    takes, bought, sold = take_orders(cfg, depth, fair_for_takes, pos_eff)
    bought += d_bought
    sold += d_sold
    quotes = make_quote(cfg, fair_for_quotes, best_bid, best_ask, position, bought, sold)
    return diverge_orders + takes + quotes


def kalman_mr_orders(cfg, depth, position, scratch, target_bias=0):
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
    target = max(-limit, min(limit, round(cfg["mr_gain"] * (anchor - mid) / sigma) + target_bias))

    take_max_pay = cfg["take_max_pay"]
    quote_edge = cfg["quote_edge"]
    quote_size = cfg["quote_size"]

    orders = []
    bv = sv = 0
    delta = target - position

    if delta > 0:
        for a in sorted(depth.sell_orders):
            if a > fair + take_max_pay:
                break
            room = min(-depth.sell_orders[a], delta - bv, limit - position - bv)
            if room <= 0:
                break
            orders.append(Order(product, a, room))
            bv += room
    elif delta < 0:
        need = -delta
        for b in sorted(depth.buy_orders, reverse=True):
            if b < fair - take_max_pay:
                break
            room = min(depth.buy_orders[b], need - sv, limit + position - sv)
            if room <= 0:
                break
            orders.append(Order(product, b, -room))
            sv += room

    baaf = min((p for p in depth.sell_orders if p >= fair + quote_edge), default=None)
    bbbf = max((p for p in depth.buy_orders if p <= fair - quote_edge), default=None)
    if bbbf is not None:
        buy_q = min(cfg["quote_size"], limit - position - bv)
        if buy_q > 0:
            orders.append(Order(product, bbbf + 1, buy_q))
    if baaf is not None:
        sell_q = min(cfg["quote_size"], limit + position - sv)
        if sell_q > 0:
            orders.append(Order(product, baaf - 1, -sell_q))
    return orders


def update_informed_signal(store, market_trades_vfe, vfe_bid, vfe_ask):
    sig = store.get("_inf", 0.0) * INFORMED_DECAY
    for t in market_trades_vfe or []:
        if t.quantity < INFORMED_SIZE_VFE:
            continue
        if t.price >= vfe_ask:
            sig += t.quantity
        elif t.price <= vfe_bid:
            sig -= t.quantity
    store["_inf"] = sig
    return sig


class VoucherOverlayTrader:
    overlay_cfg: VoucherOverlayConfig

    def bid(self):
        return 0

    def run(self, state: TradingState):
        try:
            store = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            store = {}

        orders: Dict[str, list[Order]] = {}
        bs_ctx = build_voucher_bs_context(state)

        for cfg in KALMAN_MR_PRODUCTS:
            depth = state.order_depths.get(cfg["product"])
            target_bias = 0
            if cfg["product"] == VELVET and depth and depth.buy_orders and depth.sell_orders:
                vfe_bid_ = max(depth.buy_orders)
                vfe_ask_ = min(depth.sell_orders)
                sig = update_informed_signal(
                    store.setdefault("_inf_store", {}),
                    state.market_trades.get(VELVET, []),
                    vfe_bid_,
                    vfe_ask_,
                )
                target_bias = int(round(INFORMED_GAIN_S * sig))
            ors = kalman_mr_orders(
                cfg,
                depth,
                state.position.get(cfg["product"], 0),
                store.setdefault(cfg["product"], {}),
                target_bias=target_bias,
            )
            if ors:
                orders[cfg["product"]] = ors

        for cfg in ZSCORE_PRODUCTS:
            ors = zscore_orders(
                cfg,
                state,
                store.setdefault(cfg["product"], {}),
                bs_ctx,
                self.overlay_cfg,
            )
            if ors:
                orders[cfg["product"]] = ors

        return orders, 0, json.dumps(store)
