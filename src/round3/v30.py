from __future__ import annotations

import json
import math
from statistics import NormalDist
from typing import Dict, List, Optional, Sequence, Tuple

try:
    from datamodel import Order, OrderDepth, Trade, TradingState
except ModuleNotFoundError:
    from trader_factory.core.datamodel import Order, OrderDepth, Trade, TradingState


_N = NormalDist()

HYDROGEL = "HYDROGEL_PACK"
VELVET = "VELVETFRUIT_EXTRACT"
VOUCHER_STRIKES: Dict[str, int] = {
    "VEV_4000": 4000,
    "VEV_4500": 4500,
    "VEV_5000": 5000,
    "VEV_5100": 5100,
    "VEV_5200": 5200,
    "VEV_5300": 5300,
    "VEV_5400": 5400,
    "VEV_5500": 5500,
    "VEV_6000": 6000,
    "VEV_6500": 6500,
}

LIMITS: Dict[str, int] = {
    HYDROGEL: 200,
    VELVET: 200,
    **{product: 300 for product in VOUCHER_STRIKES},
}

# Round 3 starts with 5 days to expiry.
TTE_YEARS = 5.0 / 365.0
MIDDLE_STRIKE_SET = {5100, 5200, 5300, 5400}
BASE_WORKING_VOUCHER_CAP = 100
MIDDLE_STRIKE_CAP = 80
MIDDLE_CLUSTER_CAP = 170
ADJ_SAME_SIDE_CAP = 170
UNCONFIRMED_OUTRIGHT_CAP = 85
STRIP_DELTA_SOFT_CAP = 150.0
STRIP_DELTA_HARD_CAP = 187.5
PAIR_DISTANCE_LIMIT = 2
PAIR_PRIMARY_BIAS_THRESHOLD = 0.45
PAIR_CONTINUOUS_THRESHOLD_MULT = 0.92
STEADY_PAIR_SCALP = "STEADY_PAIR_SCALP"
BROAD_SHOCK_SCALP = "BROAD_SHOCK_SCALP"
HARVEST_MODE = "HARVEST"

UNDERLYING_CFG = {
    HYDROGEL: {
        "anchor": 10000.0,
        "anchor_w": 0.54,
        "stable_w": 0.29,
        "micro_w": 0.17,
        "imbalance_w": 1.05,
        "take_edge": 2.2,
        "quote_edge": 3.0,
        "clear_edge": 1.0,
        "soft_limit": 100,
        "take_max": 22,
        "clear_max": 36,
        "quote_size": 24,
        "inv_skew": 8.0,
    },
    VELVET: {
        "anchor": 5250.0,
        "anchor_w": 0.46,
        "stable_w": 0.34,
        "micro_w": 0.20,
        "imbalance_w": 0.85,
        "take_edge": 1.2,
        "quote_edge": 1.5,
        "clear_edge": 0.6,
        "soft_limit": 120,
        "take_max": 34,
        "clear_max": 50,
        "quote_size": 36,
        "inv_skew": 5.0,
    },
}


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def sign(x: float) -> int:
    if x > 1e-9:
        return 1
    if x < -1e-9:
        return -1
    return 0


def ema(prev: Optional[float], value: float, alpha: float) -> float:
    if prev is None:
        return float(value)
    return (1.0 - alpha) * float(prev) + alpha * float(value)


def load_memory(trader_data: str) -> dict:
    if not trader_data:
        return {}
    try:
        obj = json.loads(trader_data)
        return obj if isinstance(obj, dict) else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def dump_memory(memory: dict) -> str:
    return json.dumps(memory, separators=(",", ":"))


class OrderManager:
    def __init__(self, product: str, position: int, limit: int) -> None:
        self.product = product
        self.position = int(position)
        self.limit = int(limit)
        self.buy_cap = max(0, limit - position)
        self.sell_cap = max(0, limit + position)
        self._orders: List[Order] = []

    def projected(self) -> int:
        return self.position + sum(order.quantity for order in self._orders)

    def buy(self, price: int, qty: int) -> None:
        size = min(max(0, int(qty)), self.buy_cap)
        if size > 0:
            self._orders.append(Order(self.product, int(price), size))
            self.buy_cap -= size

    def sell(self, price: int, qty: int) -> None:
        size = min(max(0, int(qty)), self.sell_cap)
        if size > 0:
            self._orders.append(Order(self.product, int(price), -size))
            self.sell_cap -= size

    def flush(self) -> List[Order]:
        orders = self._orders
        self._orders = []
        return orders


def best_bid(od: OrderDepth) -> Optional[int]:
    return max(od.buy_orders) if od.buy_orders else None


def best_ask(od: OrderDepth) -> Optional[int]:
    return min(od.sell_orders) if od.sell_orders else None


def raw_mid(od: OrderDepth) -> Optional[float]:
    bb = best_bid(od)
    ba = best_ask(od)
    if bb is None or ba is None or bb >= ba:
        return None
    return 0.5 * (bb + ba)


def top_bid_levels(od: OrderDepth, levels: int = 3) -> List[Tuple[int, int]]:
    return sorted(od.buy_orders.items(), reverse=True)[:levels]


def top_ask_levels(od: OrderDepth, levels: int = 3) -> List[Tuple[int, int]]:
    return sorted(od.sell_orders.items())[:levels]


def size_wall_prices(od: OrderDepth, levels: int = 3) -> Tuple[Optional[int], Optional[int]]:
    if not od.buy_orders or not od.sell_orders:
        return None, None
    bid_levels = top_bid_levels(od, levels)
    ask_levels = top_ask_levels(od, levels)
    bid_px = max(bid_levels, key=lambda x: (x[1], x[0]))[0]
    ask_px = min(ask_levels, key=lambda x: (x[1], x[0]))[0]
    return bid_px, ask_px


def wall_mid(od: OrderDepth) -> Optional[float]:
    bid_wall, ask_wall = size_wall_prices(od, levels=3)
    if bid_wall is None or ask_wall is None or bid_wall >= ask_wall:
        return raw_mid(od)
    return 0.5 * (bid_wall + ask_wall)


def thick_mid(od: OrderDepth, levels: int = 3) -> Optional[float]:
    if not od.buy_orders or not od.sell_orders:
        return raw_mid(od)
    bid_levels = top_bid_levels(od, levels)
    ask_levels = top_ask_levels(od, levels)
    bid_vol = sum(volume for _, volume in bid_levels)
    ask_vol = sum(abs(volume) for _, volume in ask_levels)
    if bid_vol <= 0 or ask_vol <= 0:
        return raw_mid(od)
    bid_px = sum(price * volume for price, volume in bid_levels) / bid_vol
    ask_px = sum(price * abs(volume) for price, volume in ask_levels) / ask_vol
    if bid_px >= ask_px:
        return raw_mid(od)
    return 0.5 * (bid_px + ask_px)


def micro_price(od: OrderDepth) -> Optional[float]:
    bb = best_bid(od)
    ba = best_ask(od)
    if bb is None or ba is None or bb >= ba:
        return raw_mid(od)
    bid_vol = od.buy_orders[bb]
    ask_vol = abs(od.sell_orders[ba])
    total = bid_vol + ask_vol
    if total <= 0:
        return raw_mid(od)
    return (ba * bid_vol + bb * ask_vol) / total


def book_imbalance(od: OrderDepth, levels: int = 2) -> float:
    if not od.buy_orders or not od.sell_orders:
        return 0.0
    bid_levels = top_bid_levels(od, levels)
    ask_levels = top_ask_levels(od, levels)
    bid_vol = sum(volume for _, volume in bid_levels)
    ask_vol = sum(abs(volume) for _, volume in ask_levels)
    total = bid_vol + ask_vol
    if total <= 0:
        return 0.0
    return (bid_vol - ask_vol) / total


def stable_mid(od: OrderDepth) -> Optional[float]:
    mids = [value for value in (wall_mid(od), thick_mid(od), raw_mid(od)) if value is not None]
    return sum(mids) / len(mids) if mids else None


def norm_cdf(x: float) -> float:
    return _N.cdf(x)


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def black_scholes_call(spot: float, strike: float, tte_years: float, sigma: float) -> float:
    if spot <= 0.0 or strike <= 0.0:
        return 0.0
    if tte_years <= 0.0 or sigma <= 0.0:
        return max(spot - strike, 0.0)
    sqrt_t = math.sqrt(tte_years)
    d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * tte_years) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    return spot * norm_cdf(d1) - strike * norm_cdf(d2)


def black_scholes_delta_call(spot: float, strike: float, tte_years: float, sigma: float) -> float:
    if spot <= 0.0 or strike <= 0.0:
        return 0.0
    if tte_years <= 0.0 or sigma <= 0.0:
        return 1.0 if spot > strike else 0.0
    sqrt_t = math.sqrt(tte_years)
    d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * tte_years) / (sigma * sqrt_t)
    return norm_cdf(d1)


def black_scholes_vega_proxy(spot: float, strike: float, tte_years: float, sigma: float) -> float:
    if spot <= 0.0 or strike <= 0.0 or tte_years <= 0.0 or sigma <= 0.0:
        return 0.0
    sqrt_t = math.sqrt(tte_years)
    d1 = (math.log(spot / strike) + 0.5 * sigma * sigma * tte_years) / (sigma * sqrt_t)
    return spot * norm_pdf(d1) * sqrt_t


def implied_vol_call(price: float, spot: float, strike: float, tte_years: float, iterations: int = 60) -> float:
    intrinsic = max(spot - strike, 0.0)
    if spot <= 0.0 or strike <= 0.0 or tte_years <= 0.0:
        return 1e-6
    if price <= intrinsic + 1e-6:
        return 1e-6

    lo, hi = 1e-6, 3.0
    for _ in range(iterations):
        mid = 0.5 * (lo + hi)
        fair = black_scholes_call(spot, strike, tte_years, mid)
        if fair < price:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def round_down(x: float) -> int:
    return math.floor(x)


def round_up(x: float) -> int:
    return math.ceil(x)


def trade_mid(trade: Trade) -> float:
    return float(trade.price)


def solve_3x3(a: List[List[float]], b: List[float]) -> Optional[List[float]]:
    mat = [row[:] + [rhs] for row, rhs in zip(a, b)]
    n = 3
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(mat[r][col]))
        if abs(mat[pivot][col]) < 1e-12:
            return None
        if pivot != col:
            mat[col], mat[pivot] = mat[pivot], mat[col]
        factor = mat[col][col]
        for j in range(col, n + 1):
            mat[col][j] /= factor
        for row in range(n):
            if row == col:
                continue
            factor = mat[row][col]
            for j in range(col, n + 1):
                mat[row][j] -= factor * mat[col][j]
    return [mat[i][n] for i in range(n)]


def fit_quadratic(xs: Sequence[float], ys: Sequence[float]) -> Tuple[float, float, float]:
    if len(xs) != len(ys) or len(xs) < 3:
        median = sorted(ys)[len(ys) // 2] if ys else 0.18
        return (0.0, 0.0, float(median))

    s0 = float(len(xs))
    s1 = sum(xs)
    s2 = sum(x * x for x in xs)
    s3 = sum(x * x * x for x in xs)
    s4 = sum(x * x * x * x for x in xs)
    t0 = sum(ys)
    t1 = sum(x * y for x, y in zip(xs, ys))
    t2 = sum((x * x) * y for x, y in zip(xs, ys))
    sol = solve_3x3(
        [
            [s4, s3, s2],
            [s3, s2, s1],
            [s2, s1, s0],
        ],
        [t2, t1, t0],
    )
    if sol is None:
        median = sorted(ys)[len(ys) // 2]
        return (0.0, 0.0, float(median))
    return (float(sol[0]), float(sol[1]), float(sol[2]))


def fit_quadratic_weighted(
    xs: Sequence[float], ys: Sequence[float], ws: Sequence[float]
) -> Tuple[float, float, float]:
    if len(xs) != len(ys) or len(xs) != len(ws) or len(xs) < 3:
        return fit_quadratic(xs, ys)

    safe_ws = [max(1e-6, float(w)) for w in ws]
    s0 = sum(safe_ws)
    s1 = sum(w * x for x, w in zip(xs, safe_ws))
    s2 = sum(w * x * x for x, w in zip(xs, safe_ws))
    s3 = sum(w * x * x * x for x, w in zip(xs, safe_ws))
    s4 = sum(w * x * x * x * x for x, w in zip(xs, safe_ws))
    t0 = sum(w * y for y, w in zip(ys, safe_ws))
    t1 = sum(w * x * y for x, y, w in zip(xs, ys, safe_ws))
    t2 = sum(w * x * x * y for x, y, w in zip(xs, ys, safe_ws))
    sol = solve_3x3(
        [
            [s4, s3, s2],
            [s3, s2, s1],
            [s2, s1, s0],
        ],
        [t2, t1, t0],
    )
    if sol is None:
        return fit_quadratic(xs, ys)
    return (float(sol[0]), float(sol[1]), float(sol[2]))


def polyval(coeffs: Tuple[float, float, float], x: float) -> float:
    a, b, c = coeffs
    return a * x * x + b * x + c


class Trader:
    def _reset_day_if_needed(self, memory: dict, timestamp: int) -> None:
        last_ts = memory.get("last_timestamp")
        if last_ts is not None and timestamp < last_ts:
            memory["velvet_overlay"] = {
                "day_low": 10**18,
                "day_high": -(10**18),
                "signal": 0.0,
                "age": 999,
            }
            memory["hydro_state"] = {
                "extreme_side": 0,
                "extreme_hold_bars": 0,
                "ema_fast": None,
                "ema_slow": None,
                "ret_ema": 0.0,
                "last_mid": None,
                "long_peak_score": 0.0,
                "short_peak_score": 0.0,
                "long_peak_mid": None,
                "short_peak_mid": None,
                "long_peak_trend": 0.0,
                "short_peak_trend": 0.0,
                "exit_mode": "",
                "exit_age": 0,
            }
        memory["last_timestamp"] = timestamp
        memory.setdefault(
            "velvet_overlay",
            {
                "day_low": 10**18,
                "day_high": -(10**18),
                "signal": 0.0,
                "age": 999,
            },
        )
        memory.setdefault(
            "hydro_state",
            {
                "extreme_side": 0,
                "extreme_hold_bars": 0,
                "ema_fast": None,
                "ema_slow": None,
                "ret_ema": 0.0,
                "last_mid": None,
                "long_peak_score": 0.0,
                "short_peak_score": 0.0,
                "long_peak_mid": None,
                "short_peak_mid": None,
                "long_peak_trend": 0.0,
                "short_peak_trend": 0.0,
                "exit_mode": "",
                "exit_age": 0,
            },
        )

    def _update_velvet_overlay(self, state: TradingState, memory: dict) -> float:
        overlay = memory["velvet_overlay"]
        trades = sorted(state.market_trades.get(VELVET, []), key=lambda t: t.timestamp)
        saw_event = False

        for trade in trades:
            qty = abs(int(trade.quantity))
            price = trade_mid(trade)
            is_new_low = price < float(overlay["day_low"])
            is_new_high = price > float(overlay["day_high"])

            if is_new_low:
                overlay["day_low"] = price
            if is_new_high:
                overlay["day_high"] = price

            if 10 <= qty <= 11 and is_new_low:
                overlay["signal"] = min(1.5, float(overlay["signal"]) + 1.0)
                overlay["age"] = 0
                saw_event = True

        if not saw_event:
            overlay["age"] = int(overlay.get("age", 999)) + 1
            overlay["signal"] = float(overlay.get("signal", 0.0)) * 0.96

        return 0.75 * max(0.0, min(1.0, float(overlay["signal"])))

    def _underlying_fair(self, product: str, od: OrderDepth, overlay_bias: float = 0.0) -> float:
        cfg = UNDERLYING_CFG[product]
        anchor = cfg["anchor"]
        stable = stable_mid(od)
        micro = micro_price(od)
        bb = best_bid(od)
        ba = best_ask(od)
        spread = (ba - bb) if bb is not None and ba is not None else 2.0

        stable_component = stable if stable is not None else anchor
        micro_component = micro if micro is not None else stable_component
        fair = (
            cfg["anchor_w"] * anchor
            + cfg["stable_w"] * stable_component
            + cfg["micro_w"] * micro_component
        )
        fair += cfg["imbalance_w"] * book_imbalance(od, levels=2) * max(1.0, 0.5 * spread)
        fair += overlay_bias
        return fair

    def _build_hydrogel_targets(self, state: TradingState, fair: float, memory: dict) -> dict:
        od = state.order_depths[HYDROGEL]
        bb = best_bid(od)
        ba = best_ask(od)
        mid = raw_mid(od)
        if mid is None:
            mid = stable_mid(od)
        if mid is None:
            mid = fair

        stable = stable_mid(od)
        if stable is None:
            stable = mid

        micro = micro_price(od)
        if micro is None:
            micro = mid

        spread = float((ba - bb) if bb is not None and ba is not None else 8.0)
        top_depth = 0.0
        if bb is not None:
            top_depth += float(max(0, od.buy_orders.get(bb, 0)))
        if ba is not None:
            top_depth += float(abs(od.sell_orders.get(ba, 0)))
        hydro_state = memory["hydro_state"]
        prev_fast = hydro_state.get("ema_fast")
        prev_slow = hydro_state.get("ema_slow")
        prev_last_mid = hydro_state.get("last_mid")
        prev_ret_ema = float(hydro_state.get("ret_ema", 0.0))

        ema_fast = float(mid) if prev_fast is None else 0.16 * float(mid) + 0.84 * float(prev_fast)
        ema_slow = float(mid) if prev_slow is None else 0.035 * float(mid) + 0.965 * float(prev_slow)
        ret = 0.0 if prev_last_mid is None else float(mid) - float(prev_last_mid)
        ret_ema = 0.12 * ret + 0.88 * prev_ret_ema
        hydro_state["ema_fast"] = ema_fast
        hydro_state["ema_slow"] = ema_slow
        hydro_state["ret_ema"] = ret_ema
        hydro_state["last_mid"] = float(mid)

        signal = (fair - float(mid)) / max(1.0, 0.5 * spread)
        good_book = (
            bb is not None
            and ba is not None
            and bb < ba
            and spread <= 18.0
            and top_depth >= 20.0
            and abs(float(stable) - float(mid)) <= 1.1
        )

        anchor_gap = float(mid) - UNDERLYING_CFG[HYDROGEL]["anchor"]
        trend_gap = ema_fast - ema_slow
        micro_gap = float(micro) - float(mid)
        imbalance = book_imbalance(od, levels=2)

        anchor_score = clamp(anchor_gap / 35.0, -3.0, 3.0)
        trend_score = clamp(trend_gap / 7.5, -3.0, 3.0)
        micro_score = clamp(micro_gap / max(1.0, 0.5 * spread), -1.5, 1.5)
        flow_score = clamp(micro_score + 0.75 * imbalance + 0.35 * clamp(ret_ema / 3.0, -2.0, 2.0), -2.0, 2.0)
        regime_score = 0.60 * trend_score + 0.30 * anchor_score + 0.10 * flow_score

        strength = abs(regime_score)
        if not good_book:
            confidence = "guarded"
            target_cap = 60
        elif strength < 0.75:
            confidence = "neutral"
            target_cap = 0
        elif strength < 1.30:
            confidence = "weak"
            target_cap = 80
        elif strength < 2.00:
            confidence = "medium"
            target_cap = 140
        else:
            confidence = "strong"
            target_cap = 200

        progress = clamp(state.timestamp / 3_000_000.0, 0.0, 1.0)
        current_pos = int(state.position.get(HYDROGEL, 0))
        entry_cap = target_cap
        if progress > 0.78:
            entry_cap = int(round(entry_cap * 0.88))
        if progress > 0.90:
            entry_cap = int(round(entry_cap * 0.65))
        if progress > 0.97:
            entry_cap = min(entry_cap, 50)

        hold_cap = entry_cap
        hold_zone = 110
        if abs(current_pos) > 120 and abs(trend_score) < 1.8:
            hold_cap = min(hold_cap, 100)
        if abs(current_pos) > 120 and abs(trend_score) < 1.2:
            hold_cap = min(hold_cap, 60)
        if abs(current_pos) > 160 and abs(trend_score) < 1.6:
            hold_cap = min(hold_cap, 80)
        if abs(current_pos) > 160 and abs(regime_score) < 1.2:
            hold_cap = min(hold_cap, 50)
        if abs(current_pos) > 140 and abs(trend_score) < 1.9:
            hold_cap = min(hold_cap, 90)
        if abs(current_pos) > 140 and abs(regime_score) < 1.1:
            hold_cap = min(hold_cap, 45)
        if progress > 0.94:
            hold_cap = min(hold_cap, 70)
        if progress > 0.98:
            hold_cap = min(hold_cap, 40)

        entry_target = int(round(clamp(200.0 * math.tanh(0.95 * regime_score), -float(entry_cap), float(entry_cap))))
        hold_score = 0.88 * regime_score + 0.12 * trend_score
        hold_target = int(round(clamp(200.0 * math.tanh(0.88 * hold_score), -float(hold_cap), float(hold_cap))))
        target = entry_target if abs(current_pos) < hold_zone else hold_target
        if current_pos > 80:
            hydro_state["long_peak_score"] = max(float(hydro_state.get("long_peak_score", 0.0)), float(regime_score))
            prev_peak_mid = hydro_state.get("long_peak_mid")
            hydro_state["long_peak_mid"] = float(mid) if prev_peak_mid is None else max(float(prev_peak_mid), float(mid))
            hydro_state["long_peak_trend"] = max(float(hydro_state.get("long_peak_trend", 0.0)), float(trend_score))
            hydro_state["short_peak_score"] = 0.0
            hydro_state["short_peak_mid"] = None
            hydro_state["short_peak_trend"] = 0.0
        elif current_pos < -80:
            hydro_state["short_peak_score"] = min(float(hydro_state.get("short_peak_score", 0.0)), float(regime_score))
            prev_peak_mid = hydro_state.get("short_peak_mid")
            hydro_state["short_peak_mid"] = float(mid) if prev_peak_mid is None else min(float(prev_peak_mid), float(mid))
            hydro_state["short_peak_trend"] = min(float(hydro_state.get("short_peak_trend", 0.0)), float(trend_score))
            hydro_state["long_peak_score"] = 0.0
            hydro_state["long_peak_mid"] = None
            hydro_state["long_peak_trend"] = 0.0
        elif abs(current_pos) < 40:
            hydro_state["long_peak_score"] = 0.0
            hydro_state["short_peak_score"] = 0.0
            hydro_state["long_peak_mid"] = None
            hydro_state["short_peak_mid"] = None
            hydro_state["long_peak_trend"] = 0.0
            hydro_state["short_peak_trend"] = 0.0
            hydro_state["exit_mode"] = ""
            hydro_state["exit_age"] = 0

        side = 1 if current_pos > 120 else -1 if current_pos < -120 else 0
        if side == 0:
            hydro_state["extreme_side"] = 0
            hydro_state["extreme_hold_bars"] = 0
        elif side == int(hydro_state.get("extreme_side", 0)):
            hydro_state["extreme_hold_bars"] = int(hydro_state.get("extreme_hold_bars", 0)) + 1
        else:
            hydro_state["extreme_side"] = side
            hydro_state["extreme_hold_bars"] = 1

        extreme_hold_bars = int(hydro_state.get("extreme_hold_bars", 0))
        if extreme_hold_bars > 24 and abs(regime_score) < 1.4:
            target = int(round(target * 0.70))
        elif extreme_hold_bars > 12 and abs(regime_score) < 1.0:
            target = int(round(target * 0.85))

        flatten_before_flip = False
        if current_pos * target < 0 and abs(current_pos) > 60:
            target = 0
            flatten_before_flip = True

        long_peak_score = float(hydro_state.get("long_peak_score", 0.0))
        short_peak_score = float(hydro_state.get("short_peak_score", 0.0))
        long_peak_mid = hydro_state.get("long_peak_mid")
        short_peak_mid = hydro_state.get("short_peak_mid")
        long_peak_trend = float(hydro_state.get("long_peak_trend", 0.0))
        short_peak_trend = float(hydro_state.get("short_peak_trend", 0.0))
        long_drawdown = 0.0 if long_peak_mid is None else float(long_peak_mid) - float(mid)
        short_drawup = 0.0 if short_peak_mid is None else float(mid) - float(short_peak_mid)
        trend_fade_long = long_peak_trend > 0.0 and trend_score < 0.70 * long_peak_trend
        trend_fade_short = short_peak_trend < 0.0 and trend_score > 0.70 * short_peak_trend
        fair_gap = abs(fair - float(mid))
        signal_fade = fair_gap < max(4.0, 0.55 * spread)

        unwind_long = current_pos > 150 and (
            (
                long_peak_score >= 1.35
                and long_drawdown >= 12.0
                and regime_score < max(0.70, 0.65 * long_peak_score)
                and trend_score < 1.25
            )
            or (trend_fade_long and long_drawdown >= 8.0)
            or (ret_ema < 0.0 and long_drawdown >= 8.0)
            or (signal_fade and long_drawdown >= 10.0 and current_pos > 140)
            or (long_drawdown >= 18.0 and ret_ema < -0.12)
            or (progress > 0.90 and long_drawdown >= 10.0 and trend_score < 0.95)
        )
        unwind_long_hard = current_pos > 170 and (
            (trend_fade_long and long_drawdown >= 16.0 and ret_ema < -0.05)
            or (long_drawdown >= 28.0 and ret_ema < -0.18)
            or (progress > 0.94 and long_drawdown >= 12.0)
        )
        unwind_short = current_pos < -150 and (
            (
                short_peak_score <= -1.35
                and short_drawup >= 12.0
                and regime_score > min(-0.70, 0.65 * short_peak_score)
                and trend_score > -1.25
            )
            or (trend_fade_short and short_drawup >= 8.0)
            or (ret_ema > 0.0 and short_drawup >= 8.0)
            or (signal_fade and short_drawup >= 10.0 and current_pos < -140)
            or (short_drawup >= 18.0 and ret_ema > 0.12)
            or (progress > 0.90 and short_drawup >= 10.0 and trend_score > -0.95)
        )
        unwind_short_hard = current_pos < -170 and (
            (trend_fade_short and short_drawup >= 16.0 and ret_ema > 0.05)
            or (short_drawup >= 28.0 and ret_ema > 0.18)
            or (progress > 0.94 and short_drawup >= 12.0)
        )

        prev_exit_mode = str(hydro_state.get("exit_mode", ""))
        prev_exit_age = int(hydro_state.get("exit_age", 0))
        strong_long_reconfirm = (
            current_pos > 60
            and long_peak_trend > 0.0
            and trend_score > max(1.90, 0.94 * long_peak_trend)
            and regime_score > max(1.65, 0.85 * long_peak_score)
            and ret_ema > 0.10
            and long_drawdown < 6.0
            and fair_gap > max(4.0, 0.55 * spread)
        )
        strong_short_reconfirm = (
            current_pos < -60
            and short_peak_trend < 0.0
            and trend_score < min(-1.90, 0.94 * short_peak_trend)
            and regime_score < min(-1.65, 0.85 * short_peak_score)
            and ret_ema < -0.10
            and short_drawup < 6.0
            and fair_gap > max(4.0, 0.55 * spread)
        )

        exit_mode = ""
        if prev_exit_mode.startswith("long") and current_pos > 60:
            if strong_long_reconfirm:
                exit_mode = ""
            elif unwind_long_hard or prev_exit_mode == "long_hard" or (prev_exit_age >= 8 and long_drawdown >= 12.0):
                exit_mode = "long_hard"
            else:
                exit_mode = "long"
        elif prev_exit_mode.startswith("short") and current_pos < -60:
            if strong_short_reconfirm:
                exit_mode = ""
            elif unwind_short_hard or prev_exit_mode == "short_hard" or (prev_exit_age >= 8 and short_drawup >= 12.0):
                exit_mode = "short_hard"
            else:
                exit_mode = "short"
        elif unwind_long_hard:
            exit_mode = "long_hard"
        elif unwind_long:
            exit_mode = "long"
        elif unwind_short_hard:
            exit_mode = "short_hard"
        elif unwind_short:
            exit_mode = "short"

        if exit_mode:
            hydro_state["exit_age"] = prev_exit_age + 1 if exit_mode == prev_exit_mode else 1
        else:
            hydro_state["exit_age"] = 0
        hydro_state["exit_mode"] = exit_mode

        exit_age = int(hydro_state.get("exit_age", 0))
        if exit_mode == "long":
            if exit_age <= 3:
                target = min(target, 120)
            elif exit_age <= 8:
                target = min(target, 80)
            elif exit_age <= 14:
                target = min(target, 40 if progress < 0.95 else 20)
            else:
                target = min(target, 0 if progress > 0.90 or long_drawdown >= 16.0 else 20)
        elif exit_mode == "long_hard":
            if exit_age <= 2:
                target = min(target, 80)
            elif exit_age <= 6:
                target = min(target, 40)
            else:
                target = min(target, 0 if progress > 0.88 or long_drawdown >= 14.0 else 20)
        elif exit_mode == "short":
            if exit_age <= 3:
                target = max(target, -120)
            elif exit_age <= 8:
                target = max(target, -80)
            elif exit_age <= 14:
                target = max(target, -40 if progress < 0.95 else -20)
            else:
                target = max(target, 0 if progress > 0.90 or short_drawup >= 16.0 else -20)
        elif exit_mode == "short_hard":
            if exit_age <= 2:
                target = max(target, -80)
            elif exit_age <= 6:
                target = max(target, -40)
            else:
                target = max(target, 0 if progress > 0.88 or short_drawup >= 14.0 else -20)

        stretch_long = current_pos > 150
        stretch_short = current_pos < -150
        absolute_danger_long = current_pos >= 150
        absolute_danger_short = current_pos <= -150
        exceptional_buy = regime_score >= 2.5 and progress < 0.88
        exceptional_sell = regime_score <= -2.5 and progress < 0.88

        quote_bias = 0.0 if abs(regime_score) < 0.75 else -0.06 * signal
        fair_shift = clamp(12.0 * regime_score, -48.0, 48.0)
        if exit_mode.startswith("long"):
            fair_shift -= 5.0
        elif exit_mode.startswith("short"):
            fair_shift += 5.0

        size_mult = 0.75 if confidence == "guarded" else 1.0
        if confidence == "neutral":
            size_mult *= 0.45
        if progress > 0.90 and abs(regime_score) < 1.6:
            size_mult *= 0.80
        if extreme_hold_bars > 20 and abs(regime_score) < 1.5:
            size_mult *= 0.85
        if exit_mode:
            size_mult *= 0.85
        if absolute_danger_long or absolute_danger_short:
            size_mult *= 0.75

        return {
            "mid": float(mid),
            "signal": float(signal),
            "regime_score": float(regime_score),
            "trend_score": float(trend_score),
            "anchor_score": float(anchor_score),
            "flow_score": float(flow_score),
            "confidence": confidence,
            "entry_cap": int(entry_cap),
            "hold_cap": int(hold_cap),
            "entry_target": int(entry_target),
            "hold_target": int(hold_target),
            "target": int(clamp(float(target), -200.0, 200.0)),
            "good_book": good_book,
            "progress": progress,
            "extreme_hold_bars": extreme_hold_bars,
            "flatten_before_flip": flatten_before_flip,
            "exit_mode": exit_mode,
            "exit_age": exit_age,
            "long_peak_score": long_peak_score,
            "short_peak_score": short_peak_score,
            "long_peak_trend": long_peak_trend,
            "short_peak_trend": short_peak_trend,
            "long_drawdown": long_drawdown,
            "short_drawup": short_drawup,
            "stretch_long": stretch_long,
            "stretch_short": stretch_short,
            "absolute_danger_long": absolute_danger_long,
            "absolute_danger_short": absolute_danger_short,
            "same_side_bid_block": exit_mode.startswith("long") or absolute_danger_long or (stretch_long and not exceptional_buy),
            "same_side_ask_block": exit_mode.startswith("short") or absolute_danger_short or (stretch_short and not exceptional_sell),
            "buy_take_extra": 3.0 if exit_mode.startswith("long") else 2.5 if absolute_danger_long else 2.0 if stretch_long and not exceptional_buy else 0.0,
            "sell_take_extra": 3.0 if exit_mode.startswith("short") else 2.5 if absolute_danger_short else 2.0 if stretch_short and not exceptional_sell else 0.0,
            "quote_bias": quote_bias,
            "fair_shift": fair_shift,
            "size_mult": size_mult,
        }

    def _trade_hydrogel(self, state: TradingState, fair: float, hydro_ctx: dict) -> List[Order]:
        od = state.order_depths[HYDROGEL]
        cfg = UNDERLYING_CFG[HYDROGEL]
        mgr = OrderManager(HYDROGEL, state.position.get(HYDROGEL, 0), LIMITS[HYDROGEL])

        bb = best_bid(od)
        ba = best_ask(od)
        spread = (ba - bb) if bb is not None and ba is not None else 2.0
        fair = fair + float(hydro_ctx.get("fair_shift", 0.0))
        target = float(hydro_ctx["target"])
        current_pos = int(state.position.get(HYDROGEL, 0))
        unwind_long = str(hydro_ctx.get("exit_mode", "")).startswith("long")
        unwind_short = str(hydro_ctx.get("exit_mode", "")).startswith("short")
        same_side_bid_block = bool(hydro_ctx.get("same_side_bid_block", False))
        same_side_ask_block = bool(hydro_ctx.get("same_side_ask_block", False))
        absolute_danger_long = bool(hydro_ctx.get("absolute_danger_long", False))
        absolute_danger_short = bool(hydro_ctx.get("absolute_danger_short", False))
        buy_take_allowed = not (same_side_bid_block or unwind_long or absolute_danger_long or current_pos >= 140)
        sell_take_allowed = not (same_side_ask_block or unwind_short or absolute_danger_short or current_pos <= -140)

        buy_take_edge = cfg["take_edge"] + float(hydro_ctx["buy_take_extra"])
        sell_take_edge = cfg["take_edge"] + float(hydro_ctx["sell_take_extra"])

        for ask, volume in sorted(od.sell_orders.items()):
            edge = fair - ask
            if not buy_take_allowed:
                break
            if edge >= buy_take_edge:
                mgr.buy(ask, min(-volume, cfg["take_max"]))
            elif edge >= cfg["take_edge"] + 2.5:
                mgr.buy(ask, min(-volume, cfg["take_max"]))
            else:
                break

        for bid, volume in sorted(od.buy_orders.items(), reverse=True):
            edge = bid - fair
            if not sell_take_allowed:
                break
            if edge >= sell_take_edge:
                mgr.sell(bid, min(volume, cfg["take_max"]))
            elif edge >= cfg["take_edge"] + 2.5:
                mgr.sell(bid, min(volume, cfg["take_max"]))
            else:
                break

        pos = mgr.projected()
        relative_pos = pos - target
        soft_limit = 80
        hard_zone = 130
        clear_edge = cfg["clear_edge"]
        hard_clear_edge = clear_edge + 1.5
        soft_clear_max = cfg["clear_max"]
        hard_clear_max = max(cfg["clear_max"], 56)
        if unwind_long or unwind_short:
            soft_limit = 25
            hard_zone = 45
            clear_edge += 2.0
            hard_clear_edge += 3.0
            soft_clear_max = max(cfg["clear_max"], 72)
            hard_clear_max = max(cfg["clear_max"], 96)
        elif absolute_danger_long or absolute_danger_short:
            soft_limit = 30
            hard_zone = 55
            clear_edge += 1.6
            hard_clear_edge += 2.6
            soft_clear_max = max(cfg["clear_max"], 64)
            hard_clear_max = max(cfg["clear_max"], 84)

        if relative_pos > hard_zone and bb is not None and (bb >= fair - hard_clear_edge or unwind_long or absolute_danger_long):
            mgr.sell(bb, min(int(math.ceil(relative_pos - soft_limit)), hard_clear_max))
        elif relative_pos > soft_limit and bb is not None and (bb >= fair - clear_edge or unwind_long or absolute_danger_long):
            mgr.sell(bb, min(int(math.ceil(relative_pos - soft_limit)), soft_clear_max))

        pos = mgr.projected()
        relative_pos = pos - target
        if relative_pos < -hard_zone and ba is not None and (ba <= fair + hard_clear_edge or unwind_short or absolute_danger_short):
            mgr.buy(ba, min(int(math.ceil((-soft_limit) - relative_pos)), hard_clear_max))
        elif relative_pos < -soft_limit and ba is not None and (ba <= fair + clear_edge or unwind_short or absolute_danger_short):
            mgr.buy(ba, min(int(math.ceil((-soft_limit) - relative_pos)), soft_clear_max))

        pos = mgr.projected()
        relative_pos = pos - target
        inv_ratio = relative_pos / LIMITS[HYDROGEL]
        reservation = fair + float(hydro_ctx["quote_bias"]) - (cfg["inv_skew"] + 4.0) * inv_ratio
        quote_edge = cfg["quote_edge"] + max(0.0, 0.12 * (spread - 4.0))

        buy_px = round_down(reservation - quote_edge)
        sell_px = round_up(reservation + quote_edge)

        if bb is not None and ba is not None and bb < ba:
            if spread >= 3:
                buy_px = max(buy_px, bb + 1)
                sell_px = min(sell_px, ba - 1)
            else:
                buy_px = min(buy_px, bb)
                sell_px = max(sell_px, ba)
            buy_px = min(buy_px, ba - 1)
            sell_px = max(sell_px, bb + 1)

        size_scale = max(0.20, 1.0 - abs(inv_ratio)) * max(0.35, float(hydro_ctx["size_mult"]))
        if same_side_bid_block or same_side_ask_block:
            size_scale *= 0.85
        quote_size = max(6, int(round(cfg["quote_size"] * size_scale)))

        can_bid = mgr.buy_cap > 0
        can_ask = mgr.sell_cap > 0
        if same_side_bid_block:
            can_bid = False
        if same_side_ask_block:
            can_ask = False
        if unwind_long:
            can_bid = False
        if unwind_short:
            can_ask = False
        if absolute_danger_long:
            can_bid = False
        if absolute_danger_short:
            can_ask = False

        if can_bid and (ba is None or buy_px < ba):
            mgr.buy(buy_px, quote_size)
        if can_ask and (bb is None or sell_px > bb):
            mgr.sell(sell_px, quote_size)

        return mgr.flush()

    def _trade_underlying(
        self,
        product: str,
        state: TradingState,
        fair: float,
        position_target: float = 0.0,
        take_bias: float = 0.0,
        quote_bias: float = 0.0,
        size_mult: float = 1.0,
        same_side_bid_block: bool = False,
        same_side_ask_block: bool = False,
    ) -> List[Order]:
        od = state.order_depths[product]
        cfg = UNDERLYING_CFG[product]
        limit = LIMITS[product]
        mgr = OrderManager(product, state.position.get(product, 0), limit)

        bb = best_bid(od)
        ba = best_ask(od)
        spread = (ba - bb) if bb is not None and ba is not None else 2.0

        if not same_side_bid_block:
            for ask, volume in sorted(od.sell_orders.items()):
                edge = (fair + take_bias) - ask
                if edge >= cfg["take_edge"]:
                    mgr.buy(ask, min(-volume, cfg["take_max"]))
                else:
                    break

        if not same_side_ask_block:
            for bid, volume in sorted(od.buy_orders.items(), reverse=True):
                edge = bid - (fair + take_bias)
                if edge >= cfg["take_edge"]:
                    mgr.sell(bid, min(volume, cfg["take_max"]))
                else:
                    break

        pos = mgr.projected()
        relative_pos = pos - position_target
        if relative_pos > cfg["soft_limit"] and bb is not None and bb >= fair - cfg["clear_edge"]:
            mgr.sell(bb, min(int(math.ceil(relative_pos - cfg["soft_limit"])), cfg["clear_max"]))
        elif relative_pos < -cfg["soft_limit"] and ba is not None and ba <= fair + cfg["clear_edge"]:
            mgr.buy(ba, min(int(math.ceil((-cfg["soft_limit"]) - relative_pos)), cfg["clear_max"]))

        pos = mgr.projected()
        relative_pos = pos - position_target
        inv_ratio = relative_pos / limit
        reservation = fair + quote_bias - cfg["inv_skew"] * inv_ratio
        quote_edge = cfg["quote_edge"] + max(0.0, 0.1 * (spread - 4.0))

        buy_px = round_down(reservation - quote_edge)
        sell_px = round_up(reservation + quote_edge)

        if bb is not None and ba is not None and bb < ba:
            if spread >= 3:
                buy_px = max(buy_px, bb + 1)
                sell_px = min(sell_px, ba - 1)
            else:
                buy_px = min(buy_px, bb)
                sell_px = max(sell_px, ba)
            buy_px = min(buy_px, ba - 1)
            sell_px = max(sell_px, bb + 1)

        size_scale = max(0.25, 1.0 - abs(inv_ratio)) * max(0.35, size_mult)
        quote_size = max(6, int(round(cfg["quote_size"] * size_scale)))

        if not same_side_bid_block and mgr.buy_cap > 0 and (ba is None or buy_px < ba):
            mgr.buy(buy_px, quote_size)
        if not same_side_ask_block and mgr.sell_cap > 0 and (bb is None or sell_px > bb):
            mgr.sell(sell_px, quote_size)

        return mgr.flush()

    def _repair_call_slice(
        self, strikes: Sequence[int], prices: Sequence[Optional[float]], spot_fair: float
    ) -> List[Optional[float]]:
        repaired: List[Optional[float]] = []
        for strike, price in zip(strikes, prices):
            if price is None:
                repaired.append(None)
                continue
            intrinsic = max(spot_fair - float(strike), 0.0) + 1e-3
            repaired.append(max(float(price), intrinsic))

        prev: Optional[float] = None
        for idx, price in enumerate(repaired):
            if price is None:
                continue
            if prev is not None:
                price = min(price, prev)
                repaired[idx] = price
            prev = price

        for _ in range(2):
            for idx in range(1, len(repaired) - 1):
                left = repaired[idx - 1]
                mid = repaired[idx]
                right = repaired[idx + 1]
                if left is None or mid is None or right is None:
                    continue
                mid_cap = 0.5 * (left + right)
                if mid > mid_cap:
                    repaired[idx] = mid_cap
            prev = None
            for idx, price in enumerate(repaired):
                if price is None:
                    continue
                if prev is not None:
                    price = min(price, prev)
                    repaired[idx] = price
                prev = price

        return repaired

    def _fit_voucher_iv_surface(
        self,
        strikes: Sequence[int],
        ivs: Sequence[Optional[float]],
        weights: Sequence[float],
        velvet_fair: float,
        fallback_coeffs: Optional[Tuple[float, float, float]] = None,
    ) -> dict:
        points_m: List[float] = []
        points_iv: List[float] = []
        points_w: List[float] = []
        for strike, iv, weight in zip(strikes, ivs, weights):
            if iv is None or not (1e-6 < float(iv) < 3.0):
                continue
            points_m.append(math.log(float(strike) / velvet_fair) / math.sqrt(TTE_YEARS))
            points_iv.append(float(iv))
            points_w.append(max(1e-6, float(weight)))

        fallback_used = False
        if len(points_iv) >= 3:
            sorted_ivs = sorted(points_iv)
            median_iv = sorted_ivs[len(sorted_ivs) // 2]
            clipped_ivs = [clamp(iv, median_iv - 0.25, median_iv + 0.25) for iv in points_iv]
            coeffs = fit_quadratic_weighted(points_m, clipped_ivs, points_w)
        elif fallback_coeffs is not None:
            coeffs = fallback_coeffs
            fallback_used = True
        elif points_iv:
            coeffs = (0.0, 0.0, float(sorted(points_iv)[len(points_iv) // 2]))
            fallback_used = True
        else:
            coeffs = (0.0, 0.0, 0.18)
            fallback_used = True

        if points_iv:
            fit_err = sum(abs(iv - polyval(coeffs, m)) for iv, m in zip(points_iv, points_m)) / len(points_iv)
        else:
            fit_err = 0.30
        density_score = clamp(len(points_iv) / max(4.0, 0.7 * len(strikes)), 0.0, 1.0)
        error_score = clamp(1.0 - 4.0 * fit_err, 0.0, 1.0)
        confidence = clamp(0.15 + 0.55 * density_score + 0.30 * error_score, 0.05, 1.0)
        return {
            "coeffs": coeffs,
            "usable_count": len(points_iv),
            "fit_error": fit_err,
            "confidence": confidence,
            "fallback_used": fallback_used,
        }

    def _build_voucher_surface(self, state: TradingState, velvet_fair: float, memory: dict) -> Dict[str, dict]:
        ordered_products = sorted(VOUCHER_STRIKES, key=VOUCHER_STRIKES.get)
        strikes = [VOUCHER_STRIKES[product] for product in ordered_products]
        row_by_product: Dict[str, dict] = {}
        raw_bid_prices: List[Optional[float]] = []
        raw_ask_prices: List[Optional[float]] = []
        raw_mid_prices: List[Optional[float]] = []
        weights: List[float] = []

        for product, strike in zip(ordered_products, strikes):
            od = state.order_depths.get(product)
            if od is None:
                raw_bid_prices.append(None)
                raw_ask_prices.append(None)
                raw_mid_prices.append(None)
                weights.append(0.5)
                continue

            bb = best_bid(od)
            ba = best_ask(od)
            spread = max(1.0, float((ba - bb) if bb is not None and ba is not None else 4.0))
            liquidity = 0.0
            if bb is not None:
                liquidity += float(max(0, od.buy_orders.get(bb, 0)))
            if ba is not None:
                liquidity += float(abs(od.sell_orders.get(ba, 0)))

            market_mid = raw_mid(od)
            if market_mid is None:
                market_mid = stable_mid(od)

            intrinsic = max(velvet_fair - strike, 0.0) + 1e-3
            bid_price = max(float(bb), intrinsic) if bb is not None else None
            ask_price = max(float(ba), intrinsic) if ba is not None else None
            mid_price = max(float(market_mid), intrinsic) if market_mid is not None else None

            raw_bid_prices.append(bid_price)
            raw_ask_prices.append(ask_price)
            raw_mid_prices.append(mid_price)

            m = math.log(strike / velvet_fair) / math.sqrt(TTE_YEARS)
            weight = clamp((math.log1p(liquidity) + 0.5) / spread, 0.35, 4.0)
            weight *= clamp(math.exp(-0.55 * abs(m)), 0.45, 1.0)
            weights.append(weight)
            row_by_product[product] = {
                "spread": spread,
                "liquidity": liquidity,
                "market_mid": market_mid,
                "bid_price": bid_price,
                "ask_price": ask_price,
                "mid_price": mid_price,
            }

        repaired_bid = self._repair_call_slice(strikes, raw_bid_prices, velvet_fair)
        repaired_ask = self._repair_call_slice(strikes, raw_ask_prices, velvet_fair)
        repaired_mid = self._repair_call_slice(strikes, raw_mid_prices, velvet_fair)

        bid_ivs = [implied_vol_call(px, velvet_fair, strike, TTE_YEARS) if px is not None else None for px, strike in zip(repaired_bid, strikes)]
        ask_ivs = [implied_vol_call(px, velvet_fair, strike, TTE_YEARS) if px is not None else None for px, strike in zip(repaired_ask, strikes)]
        mid_ivs = [implied_vol_call(px, velvet_fair, strike, TTE_YEARS) if px is not None else None for px, strike in zip(repaired_mid, strikes)]

        mid_fit = self._fit_voucher_iv_surface(strikes, mid_ivs, weights, velvet_fair)
        bid_fit = self._fit_voucher_iv_surface(strikes, bid_ivs, weights, velvet_fair, fallback_coeffs=mid_fit["coeffs"])
        ask_fit = self._fit_voucher_iv_surface(strikes, ask_ivs, weights, velvet_fair, fallback_coeffs=mid_fit["coeffs"])

        struct_mid_iv: Dict[str, float] = {}
        fair_bid_iv: Dict[str, float] = {}
        fair_ask_iv: Dict[str, float] = {}
        for product, strike in zip(ordered_products, strikes):
            m = math.log(strike / velvet_fair) / math.sqrt(TTE_YEARS)
            struct_mid_iv[product] = clamp(float(polyval(mid_fit["coeffs"], m)), 1e-4, 3.0)
            fair_bid_iv[product] = clamp(float(polyval(bid_fit["coeffs"], m)), 1e-4, 3.0)
            fair_ask_iv[product] = clamp(float(polyval(ask_fit["coeffs"], m)), 1e-4, 3.0)

        for idx, product in enumerate(ordered_products):
            neighbor_products = [product]
            if idx > 0:
                neighbor_products.append(ordered_products[idx - 1])
            if idx + 1 < len(ordered_products):
                neighbor_products.append(ordered_products[idx + 1])

            for target_map, obs_key in (
                (struct_mid_iv, "mid_iv"),
                (fair_bid_iv, "bid_iv"),
                (fair_ask_iv, "ask_iv"),
            ):
                sigma = target_map[product]
                neighbor_vals = sorted(target_map[p] for p in neighbor_products)
                neighbor_center = neighbor_vals[len(neighbor_vals) // 2]
                sigma = 0.75 * sigma + 0.25 * neighbor_center
                obs_iv = None
                if obs_key == "mid_iv":
                    obs_iv = mid_ivs[idx]
                elif obs_key == "bid_iv":
                    obs_iv = bid_ivs[idx]
                else:
                    obs_iv = ask_ivs[idx]
                row = row_by_product.get(product)
                if row is not None and obs_iv is not None and row["liquidity"] >= 18.0 and row["spread"] <= 6.0:
                    sigma = 0.88 * sigma + 0.12 * clamp(float(obs_iv), sigma - 0.10, sigma + 0.10)
                target_map[product] = clamp(sigma, 1e-4, 3.0)

        preliminary_abs_resids: List[float] = []
        for idx, product in enumerate(ordered_products):
            market_iv = mid_ivs[idx]
            if market_iv is not None:
                preliminary_abs_resids.append(abs(float(market_iv) - struct_mid_iv[product]))
        preliminary_avg_abs = (
            sum(preliminary_abs_resids) / len(preliminary_abs_resids) if preliminary_abs_resids else 0.0
        )

        local_iv_state = memory.setdefault("voucher_local_iv", {})
        surface: Dict[str, dict] = {}
        for idx, (product, strike) in enumerate(zip(ordered_products, strikes)):
            row = row_by_product.get(product, {})
            market_iv = mid_ivs[idx]
            market_bid_iv = bid_ivs[idx]
            market_ask_iv = ask_ivs[idx]
            local_prev = local_iv_state.get(product)

            observed_iv = None
            if market_iv is not None and row.get("spread", 8.0) <= 8.0:
                observed_iv = float(market_iv)
            if observed_iv is not None:
                local_iv = ema(local_prev, observed_iv, 0.18)
            elif local_prev is not None:
                local_iv = float(local_prev)
            else:
                local_iv = struct_mid_iv[product]
            local_iv_state[product] = float(local_iv)

            local_weight = 0.45 if (mid_fit["confidence"] < 0.45 or preliminary_avg_abs > 0.08) else 0.25
            hybrid_iv = clamp((1.0 - local_weight) * struct_mid_iv[product] + local_weight * local_iv, 1e-4, 3.0)

            fair_mid_price = black_scholes_call(velvet_fair, strike, TTE_YEARS, hybrid_iv)
            fair_bid_price = black_scholes_call(velvet_fair, strike, TTE_YEARS, fair_bid_iv[product])
            fair_ask_price = black_scholes_call(velvet_fair, strike, TTE_YEARS, fair_ask_iv[product])
            market_price = repaired_mid[idx] if repaired_mid[idx] is not None else fair_mid_price
            if market_iv is None:
                market_iv = implied_vol_call(market_price, velvet_fair, strike, TTE_YEARS)

            surface[product] = {
                "strike": strike,
                "sigma": hybrid_iv,
                "struct_iv_fair": struct_mid_iv[product],
                "local_iv_fair": float(local_iv),
                "hybrid_iv_fair": hybrid_iv,
                "fair_bid_iv": fair_bid_iv[product],
                "fair_ask_iv": fair_ask_iv[product],
                "fair": fair_mid_price,
                "fair_bid": fair_bid_price,
                "fair_ask": fair_ask_price,
                "delta": black_scholes_delta_call(velvet_fair, strike, TTE_YEARS, hybrid_iv),
                "vega_proxy": black_scholes_vega_proxy(velvet_fair, strike, TTE_YEARS, hybrid_iv),
                "moneyness": math.log(strike / velvet_fair) / math.sqrt(TTE_YEARS),
                "market_mid": row.get("market_mid"),
                "guarded_price": market_price,
                "market_iv": market_iv,
                "market_bid_iv": market_bid_iv,
                "market_ask_iv": market_ask_iv,
                "spread": float(row.get("spread", 4.0)),
                "liquidity": float(row.get("liquidity", 0.0)),
                "iv_residual": float(market_iv) - hybrid_iv,
                "bs_gap": float(market_price) - fair_mid_price,
            }

        surface["_meta"] = {
            "smile_stability_score": round(float(mid_fit["confidence"]), 4),
            "usable_mid_points": int(mid_fit["usable_count"]),
            "usable_bid_points": int(bid_fit["usable_count"]),
            "usable_ask_points": int(ask_fit["usable_count"]),
            "mid_fit_error": round(float(mid_fit["fit_error"]), 5),
            "bid_fallback": bool(bid_fit["fallback_used"]),
            "ask_fallback": bool(ask_fit["fallback_used"]),
        }
        return surface

    def _build_voucher_risk_context(self, state: TradingState, surface: Dict[str, dict], memory: dict) -> dict:
        ordered_products = sorted(VOUCHER_STRIKES, key=VOUCHER_STRIKES.get)
        meta = surface.get("_meta", {})
        liquid_products = [
            product
            for product in ordered_products
            if surface[product].get("market_mid") is not None
            and float(surface[product]["market_mid"]) > 0.5
            and float(surface[product]["liquidity"]) >= 10.0
        ]
        residual_pairs = [(product, float(surface[product]["iv_residual"])) for product in liquid_products]
        avg_abs_resid = sum(abs(resid) for _, resid in residual_pairs) / max(1, len(residual_pairs))
        resid_scale = max(0.035, avg_abs_resid)
        resid_threshold = max(0.032, 0.82 * resid_scale)
        extreme_resid_threshold = max(0.058, 1.45 * resid_scale)

        strip_state = memory.setdefault("voucher_strip_state", {})
        prev_avg_abs = float(strip_state.get("avg_abs_iv_residual", avg_abs_resid))
        resid_compression = prev_avg_abs - avg_abs_resid
        strip_state["avg_abs_iv_residual"] = avg_abs_resid
        peak_avg_abs = max(float(strip_state.get("peak_avg_abs_iv_residual", 0.0)), avg_abs_resid)
        strip_state["peak_avg_abs_iv_residual"] = peak_avg_abs
        progress = float((state.timestamp % 100000) / 100000.0)

        residual_rank: Dict[str, int] = {}
        sorted_residuals = sorted(liquid_products, key=lambda product: float(surface[product]["iv_residual"]))
        for rank, product in enumerate(sorted_residuals):
            residual_rank[product] = int(round(rank - (len(sorted_residuals) - 1) / 2.0))

        pair_target_bias: Dict[str, float] = {product: 0.0 for product in ordered_products}
        pair_bias: Dict[str, int] = {}
        pair_support: Dict[str, float] = {product: 0.0 for product in ordered_products}
        pair_agreement_count = 0
        pair_gap_threshold = max(0.040, 0.85 * resid_scale)
        for left, right in zip(ordered_products, ordered_products[1:]):
            if left not in liquid_products or right not in liquid_products:
                continue
            left_resid = float(surface[left]["iv_residual"])
            right_resid = float(surface[right]["iv_residual"])
            gap = right_resid - left_resid
            if abs(gap) < pair_gap_threshold:
                continue
            strength = clamp(abs(gap) / max(pair_gap_threshold, 1e-6), 0.0, 2.0)
            if gap > 0.0:
                pair_support[left] += 0.60 * strength
                pair_support[right] -= 0.60 * strength
                if left_resid < -0.55 * resid_scale and right_resid > 0.55 * resid_scale:
                    pair_agreement_count += 1
            else:
                pair_support[left] -= 0.60 * strength
                pair_support[right] += 0.60 * strength
                if left_resid > 0.55 * resid_scale and right_resid < -0.55 * resid_scale:
                    pair_agreement_count += 1

        for product, support in pair_support.items():
            pair_bias[product] = int(clamp(round(support), -1.0, 1.0))

        strip_delta = 0.0
        strip_vega = 0.0
        middle_abs = 0
        middle_net = 0
        low_wing_net = 0
        high_wing_net = 0
        adjacent_same_side_max = 0
        adjacent_same_side_products: List[str] = []
        positions = {product: int(state.position.get(product, 0)) for product in ordered_products}

        low_lane_scores: List[float] = []
        low_lane_cheap = 0
        low_lane_rich = 0
        for product in ordered_products:
            ctx = surface[product]
            pos = positions[product]
            delta = float(ctx["delta"])
            strip_delta += pos * delta
            strip_vega += pos * float(ctx["vega_proxy"])
            strike = VOUCHER_STRIKES[product]
            if strike in MIDDLE_STRIKE_SET:
                middle_abs += abs(pos)
                middle_net += pos
            if strike <= 5000:
                low_wing_net += pos
                score = -float(ctx["iv_residual"]) + 0.55 * float(pair_support.get(product, 0.0))
                low_lane_scores.append(score)
                if float(ctx["iv_residual"]) < -0.04:
                    low_lane_cheap += 1
                elif float(ctx["iv_residual"]) > 0.04:
                    low_lane_rich += 1
            elif strike >= 5400:
                high_wing_net += pos

        pair_candidates: List[dict] = []
        for left_index, left in enumerate(ordered_products):
            if left not in liquid_products:
                continue
            for right_index in range(left_index + 1, min(len(ordered_products), left_index + 1 + PAIR_DISTANCE_LIMIT)):
                right = ordered_products[right_index]
                if right not in liquid_products:
                    continue
                left_resid = float(surface[left]["iv_residual"])
                right_resid = float(surface[right]["iv_residual"])
                pair_spread = right_resid - left_resid
                opposite_signed = min(left_resid, right_resid) < -0.40 * resid_scale and max(left_resid, right_resid) > 0.40 * resid_scale
                if abs(pair_spread) < PAIR_CONTINUOUS_THRESHOLD_MULT * pair_gap_threshold:
                    continue
                if not opposite_signed and abs(pair_spread) < 1.25 * pair_gap_threshold:
                    continue
                if pair_spread > 0.0:
                    cheap, rich = left, right
                else:
                    cheap, rich = right, left
                    pair_spread = -pair_spread
                cheap_ctx = surface[cheap]
                rich_ctx = surface[rich]
                avg_liquidity = 0.5 * (float(cheap_ctx["liquidity"]) + float(rich_ctx["liquidity"]))
                net_pair_delta = abs(float(cheap_ctx["delta"]) - float(rich_ctx["delta"]))
                distance_penalty = 0.12 * max(0, right_index - left_index - 1)
                middle_penalty = 0.22 if (
                    VOUCHER_STRIKES[cheap] in MIDDLE_STRIKE_SET or VOUCHER_STRIKES[rich] in MIDDLE_STRIKE_SET
                ) else 0.0
                score = (
                    pair_spread / max(pair_gap_threshold, 1e-6)
                    + 0.20 * clamp(avg_liquidity / 25.0, 0.0, 2.0)
                    - 0.70 * net_pair_delta
                    - distance_penalty
                    - middle_penalty
                )
                if score <= 0.95:
                    continue
                pair_candidates.append(
                    {
                        "cheap": cheap,
                        "rich": rich,
                        "spread": pair_spread,
                        "score": score,
                        "net_delta": net_pair_delta,
                    }
                )

        provisional_broad = avg_abs_resid > 0.055 and pair_agreement_count >= 2
        max_pairs = 5 if provisional_broad and avg_abs_resid > 0.060 else 3
        selected_pairs: List[dict] = []
        used_products = set()
        for candidate in sorted(pair_candidates, key=lambda row: row["score"], reverse=True):
            if candidate["cheap"] in used_products or candidate["rich"] in used_products:
                continue
            selected_pairs.append(candidate)
            used_products.add(candidate["cheap"])
            used_products.add(candidate["rich"])
            if len(selected_pairs) >= max_pairs:
                break

        pair_intensity = 0.0
        for candidate in selected_pairs:
            weight = clamp(0.45 + 0.18 * candidate["score"], 0.45, 1.55)
            pair_target_bias[candidate["cheap"]] += weight
            pair_target_bias[candidate["rich"]] -= weight
            pair_intensity = max(pair_intensity, candidate["score"])

        active_scores: Dict[str, float] = {}
        active_caps: Dict[str, int] = {}
        activation_strength: Dict[str, float] = {}
        active_products: List[str] = []
        for product in ordered_products:
            ctx = surface[product]
            strike = VOUCHER_STRIKES[product]
            pair_strength = abs(pair_target_bias[product]) + 0.55 * abs(pair_support.get(product, 0.0))
            resid_strength = abs(float(ctx["iv_residual"])) / max(resid_threshold, 1e-6)
            liquidity_strength = clamp(float(ctx["liquidity"]) / 24.0, 0.0, 1.4)
            moneyness = abs(float(ctx["moneyness"]))
            if moneyness <= 0.55:
                moneyness_scale = 1.00
            elif moneyness <= 1.05:
                moneyness_scale = 0.95
            elif moneyness <= 1.60:
                moneyness_scale = 0.75
            else:
                moneyness_scale = 0.50
            if abs(float(ctx["iv_residual"])) >= 0.90 * extreme_resid_threshold:
                moneyness_scale = max(moneyness_scale, 0.82)
            active_score = (0.50 * pair_strength + 0.35 * resid_strength + 0.15 * liquidity_strength) * moneyness_scale
            active_scores[product] = active_score
            base_cap = MIDDLE_STRIKE_CAP if strike in MIDDLE_STRIKE_SET else BASE_WORKING_VOUCHER_CAP
            cap_scale = clamp(0.36 + 0.28 * active_score, 0.30, 1.00)
            active_cap = max(24, int(round(base_cap * cap_scale)))
            strength = 1.0
            if strike == 5100:
                trigger = max(
                    active_score / 1.00,
                    abs(pair_target_bias[product]) / 0.45,
                    abs(float(ctx["iv_residual"])) / max(0.75 * extreme_resid_threshold, 1e-6),
                )
                strength = 0.35 if trigger < 0.85 else (0.65 if trigger < 1.25 else 1.00)
            elif strike == 5200:
                trigger = max(
                    active_score / 1.05,
                    abs(pair_target_bias[product]) / 0.55,
                    abs(float(ctx["iv_residual"])) / max(extreme_resid_threshold, 1e-6),
                )
                strength = 0.20 if trigger < 0.90 else (0.55 if trigger < 1.30 else 0.95)
            elif strike >= 5300:
                trigger = max(
                    abs(pair_target_bias[product]) / 0.70,
                    (
                        abs(float(ctx["iv_residual"])) / max(1.15 * extreme_resid_threshold, 1e-6)
                        if provisional_broad and float(ctx["liquidity"]) >= 12.0
                        else 0.0
                    ),
                )
                strength = 0.0 if trigger < 0.90 else (0.30 if trigger < 1.25 else 0.75)
            activation_strength[product] = strength
            active_cap = int(round(active_cap * strength))
            if strike >= 5300 and strength > 0.0:
                active_cap = max(active_cap, 8)
            elif strike == 5200:
                active_cap = max(active_cap, 12 if strength > 0.0 else 0)
            elif strike == 5100:
                active_cap = max(active_cap, 18)
            if strength >= 0.55 and (active_score >= 0.95 or abs(pair_target_bias[product]) >= PAIR_PRIMARY_BIAS_THRESHOLD):
                active_products.append(product)
            active_caps[product] = active_cap

        for left, right in zip(ordered_products, ordered_products[1:]):
            left_pos = positions[left]
            right_pos = positions[right]
            if left_pos == 0 or right_pos == 0:
                continue
            if left_pos * right_pos > 0:
                concentration = abs(left_pos) + abs(right_pos)
                if concentration > adjacent_same_side_max:
                    adjacent_same_side_max = concentration
                    adjacent_same_side_products = [left, right]

        broad_dislocation = (
            avg_abs_resid > 0.055
            and pair_agreement_count >= 2
            and middle_abs < int(1.10 * MIDDLE_CLUSTER_CAP)
            and abs(strip_delta) < 0.95 * STRIP_DELTA_SOFT_CAP
        )
        if broad_dislocation:
            strip_state["saw_broad_dislocation"] = True
        compression_from_peak = (
            (peak_avg_abs - avg_abs_resid) / max(peak_avg_abs, 1e-6) if peak_avg_abs > 0.0 else 0.0
        )
        harvest_mode = bool(strip_state.get("harvest_mode", False))
        if bool(strip_state.get("saw_broad_dislocation", False)) and progress >= 0.76 and compression_from_peak >= 0.22:
            harvest_mode = True
        strip_state["harvest_mode"] = harvest_mode
        if harvest_mode:
            strip_mode = HARVEST_MODE
        elif broad_dislocation and (pair_intensity >= 1.25 or pair_agreement_count >= 3):
            strip_mode = BROAD_SHOCK_SCALP
        else:
            strip_mode = STEADY_PAIR_SCALP
        if abs(strip_delta) < 28.0:
            hedge_ratio = 0.0
        elif strip_mode == BROAD_SHOCK_SCALP:
            hedge_ratio = 0.75
        elif strip_mode == STEADY_PAIR_SCALP:
            hedge_ratio = 0.50
        else:
            hedge_ratio = 0.25
        if resid_compression > 0.010 or compression_from_peak > 0.18:
            hedge_ratio *= 0.50
        if resid_compression > 0.018 or compression_from_peak > 0.42:
            hedge_ratio = 0.0
        if harvest_mode:
            hedge_ratio = 0.0

        target_velvet_pos = int(round(clamp(-hedge_ratio * strip_delta, -100.0, 100.0)))
        velvet_pos = int(state.position.get(VELVET, 0))
        hedge_feasible_size_score = clamp(
            1.0
            - 0.45 * abs(strip_delta) / STRIP_DELTA_SOFT_CAP
            - 0.30 * middle_abs / max(1.0, float(MIDDLE_CLUSTER_CAP))
            - 0.20 * abs(velvet_pos - target_velvet_pos) / 100.0,
            0.35,
            1.0,
        )
        richest_products = sorted(liquid_products, key=lambda product: float(surface[product]["iv_residual"]), reverse=True)[:3]
        cheapest_products = sorted(liquid_products, key=lambda product: float(surface[product]["iv_residual"]))[:3]

        return {
            "resid_scale": resid_scale,
            "resid_threshold": resid_threshold,
            "extreme_resid_threshold": extreme_resid_threshold,
            "pair_gap_threshold": pair_gap_threshold,
            "pair_bias": pair_bias,
            "pair_support": pair_support,
            "pair_target_bias": pair_target_bias,
            "pair_agreement_count": pair_agreement_count,
            "pair_intensity": pair_intensity,
            "selected_pairs": selected_pairs,
            "residual_rank": residual_rank,
            "avg_abs_iv_residual": avg_abs_resid,
            "broad_dislocation": broad_dislocation,
            "resid_compression": resid_compression,
            "compression_from_peak": compression_from_peak,
            "harvest_mode": harvest_mode,
            "progress": progress,
            "strip_mode": strip_mode,
            "smile_stability_score": float(meta.get("smile_stability_score", 0.5)),
            "usable_mid_points": int(meta.get("usable_mid_points", 0)),
            "bid_fallback": bool(meta.get("bid_fallback", False)),
            "ask_fallback": bool(meta.get("ask_fallback", False)),
            "strip_delta": strip_delta,
            "strip_vega_proxy": strip_vega,
            "delta_pressure": clamp(strip_delta / 140.0, -2.0, 2.0),
            "hedge_ratio": hedge_ratio,
            "target_velvet_pos": target_velvet_pos,
            "middle_abs": middle_abs,
            "middle_net": middle_net,
            "middle_cap": MIDDLE_CLUSTER_CAP,
            "adjacent_same_side_max": adjacent_same_side_max,
            "adjacent_same_side_products": adjacent_same_side_products,
            "adjacent_cap": ADJ_SAME_SIDE_CAP,
            "low_wing_net": low_wing_net,
            "high_wing_net": high_wing_net,
            "low_lane_bias": sum(low_lane_scores) / max(1, len(low_lane_scores)) if low_lane_scores else 0.0,
            "low_lane_cheap": low_lane_cheap,
            "low_lane_rich": low_lane_rich,
            "cheap_rich_balance": low_lane_cheap - low_lane_rich,
            "active_scores": active_scores,
            "active_caps": active_caps,
            "activation_strength": activation_strength,
            "active_products": active_products,
            "total_delta_cap": STRIP_DELTA_SOFT_CAP,
            "unconfirmed_outright_cap": UNCONFIRMED_OUTRIGHT_CAP,
            "hedge_feasible_size_score": hedge_feasible_size_score,
            "richest_products": richest_products,
            "cheapest_products": cheapest_products,
        }

    def _build_velvet_plan(self, state: TradingState, velvet_fair: float, risk_ctx: dict) -> dict:
        od = state.order_depths[VELVET]
        mid = raw_mid(od)
        if mid is None:
            mid = stable_mid(od)
        if mid is None:
            mid = velvet_fair
        bb = best_bid(od)
        ba = best_ask(od)
        spread = max(1.0, float((ba - bb) if bb is not None and ba is not None else 4.0))

        strip_delta = float(risk_ctx["strip_delta"])
        hedge_target = float(risk_ctx["target_velvet_pos"])
        hedge_ratio = float(risk_ctx["hedge_ratio"])
        low_lane_bias = float(risk_ctx["low_lane_bias"])
        cheap_rich_balance = int(risk_ctx["cheap_rich_balance"])
        pair_intensity = float(risk_ctx.get("pair_intensity", 0.0))
        resid_compression = float(risk_ctx["resid_compression"])
        compression_from_peak = float(risk_ctx.get("compression_from_peak", 0.0))
        harvest_mode = bool(risk_ctx.get("harvest_mode", False))
        strip_mode = str(risk_ctx.get("strip_mode", STEADY_PAIR_SCALP))
        broad_dislocation = bool(risk_ctx["broad_dislocation"])
        smile_stability = float(risk_ctx["smile_stability_score"])

        alpha_signal = (velvet_fair - float(mid)) / max(1.0, 0.5 * spread)
        local_alpha = 12.0 * math.tanh(0.60 * alpha_signal)
        strip_alpha = 5.5 * math.tanh(0.75 * low_lane_bias) + 2.2 * clamp(float(cheap_rich_balance), -2.0, 2.0)
        strip_alpha += 2.0 * math.tanh(0.45 * pair_intensity)
        alpha_cap = 10.0 if strip_mode == BROAD_SHOCK_SCALP else 14.0
        if abs(strip_delta) >= 60.0:
            alpha_cap = min(alpha_cap, 6.0)
        if resid_compression > 0.010 or compression_from_peak > 0.18:
            strip_alpha *= 0.60
            local_alpha *= 0.80
        if resid_compression > 0.018 or compression_from_peak > 0.42:
            strip_alpha = 0.0
            local_alpha *= 0.35
            hedge_target = 0.0
        if smile_stability < 0.40:
            strip_alpha *= 0.80
        if harvest_mode:
            strip_alpha *= 0.20
            local_alpha *= 0.45
            hedge_target = 0.0
        alpha_target = clamp(local_alpha + strip_alpha, -alpha_cap, alpha_cap)
        if harvest_mode:
            alpha_target = clamp(alpha_target, -4.0, 4.0)
        final_target = int(round(clamp(hedge_target + alpha_target, -100.0, 100.0)))

        position = int(state.position.get(VELVET, 0))
        hedge_gap = float(position) - hedge_target
        quote_bias = -0.14 * float(risk_ctx["delta_pressure"]) - 0.10 * clamp(hedge_gap / 35.0, -1.0, 1.0)
        quote_bias += 0.03 * math.tanh(0.8 * low_lane_bias)
        if resid_compression > 0.010 or compression_from_peak > 0.18:
            quote_bias *= 0.60
        if harvest_mode:
            quote_bias *= 0.75

        size_mult = 0.88 + 0.24 * hedge_ratio
        if strip_mode == STEADY_PAIR_SCALP:
            size_mult *= 0.95
        if resid_compression > 0.010 or compression_from_peak > 0.18:
            size_mult *= 0.88
        if harvest_mode:
            size_mult *= 0.72
        size_mult = clamp(size_mult, 0.60, 1.20)
        same_side_bid_block = harvest_mode and position > final_target
        same_side_ask_block = harvest_mode and position < final_target

        return {
            "hedge_ratio": hedge_ratio,
            "vev_hedge_target": int(round(hedge_target)),
            "vev_alpha_target": int(round(alpha_target)),
            "vev_final_target": int(final_target),
            "quote_bias": float(quote_bias),
            "size_mult": float(size_mult),
            "strip_mode": strip_mode,
            "same_side_bid_block": bool(same_side_bid_block),
            "same_side_ask_block": bool(same_side_ask_block),
        }

    def _trade_voucher(self, product: str, state: TradingState, voucher_ctx: dict, risk_ctx: dict) -> List[Order]:
        od = state.order_depths[product]
        limit = LIMITS[product]
        mgr = OrderManager(product, state.position.get(product, 0), limit)

        fair = float(voucher_ctx["fair"])
        fair_bid = float(voucher_ctx.get("fair_bid", fair))
        fair_ask = float(voucher_ctx.get("fair_ask", fair))
        delta = float(voucher_ctx["delta"])
        vega_proxy = float(voucher_ctx["vega_proxy"])
        iv_residual = float(voucher_ctx["iv_residual"])
        hybrid_iv_fair = float(voucher_ctx.get("hybrid_iv_fair", voucher_ctx.get("sigma", 0.18)))
        fair_bid_iv = float(voucher_ctx.get("fair_bid_iv", hybrid_iv_fair))
        fair_ask_iv = float(voucher_ctx.get("fair_ask_iv", hybrid_iv_fair))
        market_bid_iv = voucher_ctx.get("market_bid_iv")
        market_ask_iv = voucher_ctx.get("market_ask_iv")
        bs_gap = float(voucher_ctx.get("bs_gap", 0.0))
        residual_rank = int(risk_ctx["residual_rank"].get(product, 0))
        pair_support = float(risk_ctx["pair_support"].get(product, 0.0))
        pair_target_bias = float(risk_ctx["pair_target_bias"].get(product, 0.0))
        harvest_mode = bool(risk_ctx.get("harvest_mode", False))
        strip_mode = str(risk_ctx.get("strip_mode", STEADY_PAIR_SCALP))
        activation_strength = float(risk_ctx.get("activation_strength", {}).get(product, 1.0))
        bb = best_bid(od)
        ba = best_ask(od)
        spread = (ba - bb) if bb is not None and ba is not None else 2.0

        middle_band = VOUCHER_STRIKES[product] in MIDDLE_STRIKE_SET
        pair_bias = int(clamp(float(risk_ctx["pair_bias"].get(product, 0)), -1.0, 1.0))
        pair_confirmed = abs(pair_support) >= 0.35 or pair_bias != 0 or abs(pair_target_bias) >= PAIR_PRIMARY_BIAS_THRESHOLD
        resid_threshold = float(risk_ctx["resid_threshold"])
        extreme_resid_threshold = float(risk_ctx["extreme_resid_threshold"])
        broad_dislocation = bool(risk_ctx["broad_dislocation"])
        cheap_signal = max(0.0, -iv_residual)
        rich_signal = max(0.0, iv_residual)
        pair_primary_long = pair_target_bias >= PAIR_PRIMARY_BIAS_THRESHOLD
        pair_primary_short = pair_target_bias <= -PAIR_PRIMARY_BIAS_THRESHOLD
        score = 1.05 * pair_target_bias + 0.45 * (-iv_residual / max(resid_threshold, 1e-6)) + 0.18 * pair_support + 0.10 * pair_bias
        if broad_dislocation and pair_confirmed:
            score += 0.12 * sign(score)
        neighbor_confirm = abs(pair_support) >= 0.28 or pair_bias != 0
        outright_long = cheap_signal >= extreme_resid_threshold and neighbor_confirm
        outright_short = rich_signal >= extreme_resid_threshold and neighbor_confirm
        buy_confirmed = pair_primary_long or (cheap_signal >= resid_threshold and neighbor_confirm) or outright_long
        sell_confirmed = pair_primary_short or (rich_signal >= resid_threshold and neighbor_confirm) or outright_short
        buy_extreme = cheap_signal >= extreme_resid_threshold
        sell_extreme = rich_signal >= extreme_resid_threshold
        delta_soft = abs(float(risk_ctx["strip_delta"])) > float(risk_ctx["total_delta_cap"])
        delta_hard = abs(float(risk_ctx["strip_delta"])) > STRIP_DELTA_HARD_CAP
        delta_block_buy = delta_hard and float(risk_ctx["strip_delta"]) > 0.0
        delta_block_sell = delta_hard and float(risk_ctx["strip_delta"]) < 0.0
        adjacent_block = (
            product in risk_ctx["adjacent_same_side_products"]
            and int(risk_ctx["adjacent_same_side_max"]) > int(risk_ctx["adjacent_cap"])
        )
        hedge_feasible_size_score = float(risk_ctx.get("hedge_feasible_size_score", 1.0))
        take_iv_edge = max(0.028, 0.75 * resid_threshold)
        if strip_mode == BROAD_SHOCK_SCALP and pair_confirmed:
            take_iv_edge *= 0.88
        take_edge = max(0.75, 0.35 * spread) + (0.30 if middle_band else 0.0) + (0.24 if not pair_confirmed else 0.0)
        if strip_mode == BROAD_SHOCK_SCALP and pair_confirmed:
            take_edge -= 0.18
        elif strip_mode == STEADY_PAIR_SCALP and not pair_confirmed:
            take_edge += 0.18
        clear_edge = max(0.35, 0.15 * spread)
        soft_limit = 85 if middle_band else 125
        per_strike_cap = int(risk_ctx["active_caps"].get(product, MIDDLE_STRIKE_CAP if middle_band else BASE_WORKING_VOUCHER_CAP))
        if middle_band and not pair_confirmed:
            per_strike_cap = min(per_strike_cap, UNCONFIRMED_OUTRIGHT_CAP)
        if strip_mode == BROAD_SHOCK_SCALP and middle_band and pair_confirmed:
            per_strike_cap = min(int(round(1.20 * per_strike_cap)), MIDDLE_STRIKE_CAP + 30)
        per_strike_cap = max(24, int(round(per_strike_cap * hedge_feasible_size_score)))
        take_max = 13 if pair_confirmed else (7 if middle_band else 10)
        if strip_mode == BROAD_SHOCK_SCALP and pair_confirmed:
            take_max += 4
        if activation_strength < 0.30:
            take_max = min(take_max, 4)

        target_scale = 0.78 + (0.34 if pair_confirmed else -0.20)
        if strip_mode == STEADY_PAIR_SCALP and not pair_confirmed:
            target_scale *= 0.58
        if strip_mode == BROAD_SHOCK_SCALP and pair_confirmed:
            target_scale += 0.22
        raw_target = int(round(per_strike_cap * clamp(math.tanh(0.95 * score), -1.0, 1.0) * target_scale))
        target = int(clamp(raw_target, -per_strike_cap, per_strike_cap))
        target = int(round(target * activation_strength))
        if not pair_confirmed and not (outright_long or outright_short):
            target = int(round(0.22 * target))
        if not pair_confirmed and abs(target) > int(risk_ctx["unconfirmed_outright_cap"]):
            target = int(
                clamp(
                    target,
                    -int(risk_ctx["unconfirmed_outright_cap"]),
                    int(risk_ctx["unconfirmed_outright_cap"]),
                )
            )
        worsens_delta = (target > mgr.projected() and float(risk_ctx["strip_delta"]) > 0.0) or (
            target < mgr.projected() and float(risk_ctx["strip_delta"]) < 0.0
        )
        if delta_soft and worsens_delta:
            target = int(round(0.65 * target + 0.35 * mgr.projected()))
        if harvest_mode:
            target = int(round(0.72 * target))
        if middle_band and risk_ctx["middle_abs"] > risk_ctx["middle_cap"] and sign(target) == sign(mgr.projected()) and abs(target) > abs(mgr.projected()):
            target = mgr.projected()
        if adjacent_block and sign(target) == sign(mgr.projected()) and abs(target) > abs(mgr.projected()):
            target = mgr.projected()
        harvest_bid_block = harvest_mode and mgr.projected() > target
        harvest_ask_block = harvest_mode and mgr.projected() < target

        if not harvest_bid_block:
            for ask, volume in sorted(od.sell_orders.items()):
                edge = fair - ask
                iv_ok = market_ask_iv is not None and float(market_ask_iv) <= fair_bid_iv - take_iv_edge
                px_ok = ask <= fair_bid - 0.25
                if pair_confirmed:
                    edge += 0.18
                if pair_primary_long:
                    edge += 0.24
                elif pair_bias > 0:
                    edge += 0.20
                if (
                    ((edge >= take_edge and buy_confirmed and (iv_ok or px_ok) and not delta_block_buy))
                    or (edge >= take_edge + 0.8 and buy_extreme and not delta_block_buy)
                ):
                    mgr.buy(ask, min(-volume, take_max))
                else:
                    break

        if not harvest_ask_block:
            for bid, volume in sorted(od.buy_orders.items(), reverse=True):
                edge = bid - fair
                iv_ok = market_bid_iv is not None and float(market_bid_iv) >= fair_ask_iv + take_iv_edge
                px_ok = bid >= fair_ask + 0.25
                if pair_confirmed:
                    edge += 0.18
                if pair_primary_short:
                    edge += 0.24
                elif pair_bias < 0:
                    edge += 0.20
                if (
                    ((edge >= take_edge and sell_confirmed and (iv_ok or px_ok) and not delta_block_sell))
                    or (edge >= take_edge + 0.8 and sell_extreme and not delta_block_sell)
                ):
                    mgr.sell(bid, min(volume, take_max))
                else:
                    break

        pos = mgr.projected()
        if pos - target > soft_limit and bb is not None and bb >= fair - clear_edge:
            mgr.sell(bb, min((pos - target) - soft_limit, 50))
        elif pos > 0 and not buy_confirmed and bb is not None and bb >= fair - (clear_edge + 0.15):
            mgr.sell(bb, min(pos, 28))
        elif target - pos > soft_limit and ba is not None and ba <= fair + clear_edge:
            mgr.buy(ba, min((target - pos) - soft_limit, 50))
        elif pos < 0 and not sell_confirmed and ba is not None and ba <= fair + (clear_edge + 0.15):
            mgr.buy(ba, min(-pos, 28))

        pos = mgr.projected()
        relative_pos = pos - target
        inv_ratio = relative_pos / limit
        inv_penalty = (0.02 * max(25.0, fair) + 2.0) * inv_ratio
        signal_shift = clamp(score, -1.7, 1.7)
        reservation = fair - inv_penalty + 0.30 * signal_shift + 0.12 * pair_bias + 0.16 * pair_target_bias + 0.08 * pair_support
        quote_edge = max(1.0, 0.45 * spread, 0.015 * max(20.0, fair))
        if middle_band:
            quote_edge += 0.40
        if not pair_confirmed:
            quote_edge += 0.28
        if not buy_confirmed and not sell_confirmed:
            quote_edge += 0.20
        if risk_ctx["middle_abs"] > risk_ctx["middle_cap"] and middle_band:
            quote_edge += 0.35
        if delta_soft:
            quote_edge += 0.15
        if delta_hard:
            quote_edge += 0.15
        if adjacent_block:
            quote_edge += 0.15
        if abs(bs_gap) > 1.0:
            quote_edge += 0.10
        if strip_mode == STEADY_PAIR_SCALP and not pair_confirmed:
            quote_edge += 0.22
        if strip_mode == BROAD_SHOCK_SCALP and pair_confirmed:
            quote_edge -= 0.10

        buy_px = round_down(reservation - quote_edge)
        sell_px = round_up(reservation + quote_edge)

        if bb is not None and ba is not None and bb < ba:
            if spread >= 3:
                buy_px = max(buy_px, bb + 1)
                sell_px = min(sell_px, ba - 1)
            else:
                buy_px = min(buy_px, bb)
                sell_px = max(sell_px, ba)
            buy_px = min(buy_px, ba - 1)
            sell_px = max(sell_px, bb + 1)

        size_scale = max(0.20, 1.0 - abs(inv_ratio))
        if middle_band:
            size_scale *= 0.45
        if not pair_confirmed:
            size_scale *= 0.62
        if abs(iv_residual) > 0.10:
            size_scale *= 0.85
        size_scale *= clamp(1.4 / (1.0 + 0.02 * vega_proxy), 0.35, 1.0)
        size_scale *= hedge_feasible_size_score
        if delta_soft:
            size_scale *= 0.82
        if delta_hard:
            size_scale *= 0.80
        if adjacent_block:
            size_scale *= 0.82
        if abs(residual_rank) >= 3:
            size_scale *= 0.90
        if abs(pair_target_bias) >= PAIR_PRIMARY_BIAS_THRESHOLD:
            size_scale *= 1.12
        if strip_mode == BROAD_SHOCK_SCALP and pair_confirmed:
            size_scale *= 1.08
        if strip_mode == STEADY_PAIR_SCALP and not pair_confirmed:
            size_scale *= 0.75
        size_scale *= clamp(0.45 + 0.55 * activation_strength, 0.20, 1.0)
        if harvest_mode:
            size_scale *= 0.78
        base_size = 9 if fair > 100.0 else 14
        quote_size = max(4, int(round(base_size * size_scale)))

        if fair >= 0.5:
            can_bid = mgr.buy_cap > 0 and pos < target and (buy_confirmed or pos < -int(0.35 * soft_limit))
            can_ask = mgr.sell_cap > 0 and pos > target and (sell_confirmed or pos > int(0.35 * soft_limit))
            if activation_strength <= 0.0 and pos == 0:
                can_bid = False
                can_ask = False
            if middle_band and risk_ctx["middle_abs"] > risk_ctx["middle_cap"]:
                if risk_ctx["middle_net"] >= 0:
                    can_bid = False
                if risk_ctx["middle_net"] <= 0:
                    can_ask = False
            if not pair_confirmed and pos >= risk_ctx["unconfirmed_outright_cap"]:
                can_bid = False
            if not pair_confirmed and pos <= -risk_ctx["unconfirmed_outright_cap"]:
                can_ask = False
            if delta_block_buy:
                can_bid = False
            if delta_block_sell:
                can_ask = False
            if harvest_bid_block:
                can_bid = False
            if harvest_ask_block:
                can_ask = False
            if adjacent_block:
                if pos >= int(0.7 * per_strike_cap) and sign(target) >= 0:
                    can_bid = False
                if pos <= -int(0.7 * per_strike_cap) and sign(target) <= 0:
                    can_ask = False
            if not pair_confirmed and not outright_long:
                can_bid = False
            if not pair_confirmed and not outright_short:
                can_ask = False

            if can_bid and (ba is None or buy_px < ba):
                mgr.buy(buy_px, quote_size)
            if can_ask and (bb is None or sell_px > bb):
                mgr.sell(sell_px, quote_size)

        return mgr.flush()

    def run(self, state: TradingState):
        memory = load_memory(state.traderData)
        memory.setdefault("engine_errors", {})
        try:
            self._reset_day_if_needed(memory, state.timestamp)
        except Exception as exc:
            memory["engine_errors"]["reset"] = type(exc).__name__

        result: Dict[str, List[Order]] = {}
        conversions = 0
        velvet_overlay_bias = 0.0
        try:
            velvet_overlay_bias = self._update_velvet_overlay(state, memory)
        except Exception as exc:
            memory["engine_errors"]["velvet_overlay"] = type(exc).__name__

        if HYDROGEL in state.order_depths:
            try:
                hydro_fair = self._underlying_fair(HYDROGEL, state.order_depths[HYDROGEL], 0.0)
                hydro_ctx = self._build_hydrogel_targets(state, hydro_fair, memory)
                memory["hydro_book"] = {
                    "mid": round(float(hydro_ctx["mid"]), 3),
                    "signal": round(float(hydro_ctx["signal"]), 3),
                    "regime_score": round(float(hydro_ctx["regime_score"]), 3),
                    "trend_score": round(float(hydro_ctx["trend_score"]), 3),
                    "anchor_score": round(float(hydro_ctx["anchor_score"]), 3),
                    "flow_score": round(float(hydro_ctx["flow_score"]), 3),
                    "confidence": str(hydro_ctx["confidence"]),
                    "entry_cap": int(hydro_ctx["entry_cap"]),
                    "hold_cap": int(hydro_ctx["hold_cap"]),
                    "entry_target": int(hydro_ctx["entry_target"]),
                    "hold_target": int(hydro_ctx["hold_target"]),
                    "target": int(hydro_ctx["target"]),
                    "good_book": bool(hydro_ctx["good_book"]),
                    "progress": round(float(hydro_ctx["progress"]), 3),
                    "extreme_hold_bars": int(hydro_ctx["extreme_hold_bars"]),
                    "flatten_before_flip": bool(hydro_ctx["flatten_before_flip"]),
                    "exit_mode": str(hydro_ctx["exit_mode"]),
                    "exit_age": int(hydro_ctx["exit_age"]),
                    "long_peak_score": round(float(hydro_ctx["long_peak_score"]), 3),
                    "short_peak_score": round(float(hydro_ctx["short_peak_score"]), 3),
                    "long_peak_trend": round(float(hydro_ctx["long_peak_trend"]), 3),
                    "short_peak_trend": round(float(hydro_ctx["short_peak_trend"]), 3),
                    "long_drawdown": round(float(hydro_ctx["long_drawdown"]), 3),
                    "short_drawup": round(float(hydro_ctx["short_drawup"]), 3),
                    "absolute_danger_long": bool(hydro_ctx["absolute_danger_long"]),
                    "absolute_danger_short": bool(hydro_ctx["absolute_danger_short"]),
                    "same_side_bid_block": bool(hydro_ctx["same_side_bid_block"]),
                    "same_side_ask_block": bool(hydro_ctx["same_side_ask_block"]),
                }
                result[HYDROGEL] = self._trade_hydrogel(state, hydro_fair, hydro_ctx)
            except Exception as exc:
                memory["engine_errors"]["hydrogel"] = type(exc).__name__

        velvet_fair = None
        if VELVET in state.order_depths:
            try:
                velvet_fair = self._underlying_fair(VELVET, state.order_depths[VELVET], velvet_overlay_bias)
            except Exception as exc:
                memory["engine_errors"]["velvet_fair"] = type(exc).__name__

        if velvet_fair is not None:
            try:
                voucher_surface = self._build_voucher_surface(state, velvet_fair, memory)
                risk_ctx = self._build_voucher_risk_context(state, voucher_surface, memory)
                velvet_plan = self._build_velvet_plan(state, velvet_fair, risk_ctx)
                surface_meta = voucher_surface.get("_meta", {})
                memory["strip_monitor"] = {
                    "strip_delta": round(float(risk_ctx["strip_delta"]), 3),
                    "strip_vega_proxy": round(float(risk_ctx["strip_vega_proxy"]), 3),
                    "avg_abs_iv_residual": round(float(risk_ctx["avg_abs_iv_residual"]), 4),
                    "pair_agreement_count": int(risk_ctx["pair_agreement_count"]),
                    "broad_dislocation": bool(risk_ctx["broad_dislocation"]),
                    "resid_compression": round(float(risk_ctx["resid_compression"]), 4),
                    "compression_from_peak": round(float(risk_ctx["compression_from_peak"]), 4),
                    "harvest_mode": bool(risk_ctx["harvest_mode"]),
                    "progress": round(float(risk_ctx["progress"]), 3),
                    "strip_mode": str(risk_ctx["strip_mode"]),
                    "smile_stability_score": round(float(risk_ctx["smile_stability_score"]), 4),
                    "usable_mid_points": int(risk_ctx["usable_mid_points"]),
                    "bid_fallback": bool(risk_ctx["bid_fallback"]),
                    "ask_fallback": bool(risk_ctx["ask_fallback"]),
                    "hedge_ratio": round(float(velvet_plan["hedge_ratio"]), 3),
                    "target_velvet_pos": int(risk_ctx["target_velvet_pos"]),
                    "vev_hedge_target": int(velvet_plan["vev_hedge_target"]),
                    "vev_alpha_target": int(velvet_plan["vev_alpha_target"]),
                    "vev_final_target": int(velvet_plan["vev_final_target"]),
                    "low_lane_bias": round(float(risk_ctx["low_lane_bias"]), 3),
                    "cheap_rich_balance": int(risk_ctx["cheap_rich_balance"]),
                    "hedge_feasible_size_score": round(float(risk_ctx["hedge_feasible_size_score"]), 3),
                    "pair_intensity": round(float(risk_ctx["pair_intensity"]), 3),
                    "active_products": list(risk_ctx["active_products"][:5]),
                    "richest_products": list(risk_ctx["richest_products"]),
                    "cheapest_products": list(risk_ctx["cheapest_products"]),
                    "middle_abs": int(risk_ctx["middle_abs"]),
                    "middle_net": int(risk_ctx["middle_net"]),
                    "middle_cap": int(risk_ctx["middle_cap"]),
                    "adjacent_same_side_max": int(risk_ctx["adjacent_same_side_max"]),
                    "adjacent_cap": int(risk_ctx["adjacent_cap"]),
                    "adjacent_same_side_products": list(risk_ctx["adjacent_same_side_products"]),
                    "low_wing_net": int(risk_ctx["low_wing_net"]),
                    "high_wing_net": int(risk_ctx["high_wing_net"]),
                    "surface_meta": {
                        "smile_stability_score": round(float(surface_meta.get("smile_stability_score", 0.0)), 4),
                        "mid_fit_error": round(float(surface_meta.get("mid_fit_error", 0.0)), 5),
                    },
                }
                result[VELVET] = self._trade_underlying(
                    VELVET,
                    state,
                    velvet_fair,
                    position_target=float(velvet_plan["vev_final_target"]),
                    quote_bias=float(velvet_plan["quote_bias"]),
                    size_mult=float(velvet_plan["size_mult"]),
                    same_side_bid_block=bool(velvet_plan["same_side_bid_block"]),
                    same_side_ask_block=bool(velvet_plan["same_side_ask_block"]),
                )
                for product in VOUCHER_STRIKES:
                    if product in state.order_depths:
                        voucher_orders = self._trade_voucher(product, state, voucher_surface[product], risk_ctx)
                        result[product] = voucher_orders
            except Exception as exc:
                memory["engine_errors"]["voucher_strip"] = type(exc).__name__

        return result, conversions, dump_memory(memory)