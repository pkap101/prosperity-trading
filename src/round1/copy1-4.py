from __future__ import annotations
# https://github.com/Xa4-wi/Prosperity/blob/main/Bots/Round1/TradervR1_47.py
import json
import math
from typing import Dict, List, Optional, Tuple

try:
    from datamodel import Order, OrderDepth, TradingState
except ModuleNotFoundError:
    from trader_factory.core.datamodel import Order, OrderDepth, TradingState

# ── Position limits (official Round 1 limits are 80) ──────────────────────────
PRODUCT_LIMITS = {
    "ASH_COATED_OSMIUM": 80,
    "INTARIAN_PEPPER_ROOT": 80,
}

# ── ASH_COATED_OSMIUM params ───────────────────────────────────────────────────
# Archetype: anchored_mm with tiered takes, join logic, two-level passive ladder
DEFAULT_ASH_PARAMS = {
    "ENABLED": True,
    "REFERENCE_PRICE": 10000.0,
    "ANCHOR_WEIGHT": 0.42,
    "STABLE_MID_WEIGHT": 0.58,
    "WALL_MID_BLEND": 0.32,
    "LOCAL_MICRO_WEIGHT": 0.42,
    "LOCAL_IMBALANCE_BIAS": 0.16,
    "DEPTH_IMPACT_SCALE": 58.0,
    "DEPTH_FLOOR": 8.0,
    "INVENTORY_SKEW": 0.104,
    "INVENTORY_CURVE": 2.2,
    "BASE_EDGE": -1.0,          # strongest Osmium aggression tested so far
    "JOIN_EDGE": 2.0,           # snap quote to existing order when within this
    "FRONT_SIZE": 17.52842512,
    "BACK_SIZE": 5,
    "SOFT_LIMIT": 70.0,           # reduce aggressiveness above this inventory
    # Tiered take: [(min_edge, qty_clip), ...]
    "TAKE_L1_EDGE": -1.0,
    "TAKE_L1_SIZE": 6,
    "TAKE_L2_EDGE": 1.5,
    "TAKE_L2_SIZE": 10,
    "TAKE_L3_EDGE": 4.5,
    "MIN_QUOTE_EDGE": 1.8,
    "TAKE_L3_SIZE": 16,
    # Toxic-book thresholds
    "ADVERSE_IMBALANCE": 0.20,
    "STRONG_IMBALANCE": 0.16,
}

# ── INTARIAN_PEPPER_ROOT params ────────────────────────────────────────────────
# Archetype: directional_mm with state-based trend + residual tracking
# Key fix: passive quotes anchored to mid (not drift-adjusted fair), so they
# actually land inside the spread and can fill.
DEFAULT_IPR_PARAMS = {
    "ENABLED": True,
    # Trend model
    "DRIFT_PER_TIMESTAMP": 0.0026009226,   # +1 tick / 1000 timestamps → +1000/day
    "RESIDUAL_ALPHA": 0.10,          # EMA alpha for residual tracking
    "SPREAD_ALPHA": 0.08,            # EMA alpha for spread tracking
    "LOOKAHEAD_BONUS": 4.8849030549,          # constant upward bias in fair value
    # Position targeting
    "BASE_CARRY": 7.7045484383,              # always want at least this many units
    "EARLY_LONG_BIAS": 43.1941331644,         # extra target early in day (fades to 0 by 85%)
    "EDGE_TARGET_SCALE": 12.0,       # target += scale * (fair - mid)
    "ZSCORE_BUY_BONUS": 12.0,
    "ZSCORE_SELL_PENALTY": 8.0,
    "MAX_LONG_TARGET": 76.0,
    "MAX_SHORT_TARGET": 20,
    "EARLY_ACCUM_END": 0.42,         # fraction of day where early accumulation ends
    # Execution
    "INVENTORY_SKEW": 0.078,
    "BASE_TAKE_EDGE": 2.7678379562,
    "BASE_QUOTE_EDGE": 5.351603402,
    "SOFT_LIMIT": 52,
    "PASSIVE_FRONT_SIZE": 9,
    "PASSIVE_BACK_SIZE": 6,
    "PASSIVE_BUY_BUFFER": 18,
    "PASSIVE_SELL_BUFFER": 8,
    "OVEREXTENSION_Z": 1.05,
    "BULLISH_IMBALANCE": 0.05,
    # Cheaper accumulation overlay
    "CHEAP_ACCUM_END": 0.56,
    "CHEAP_ACCUM_TAKE_PENALTY": 0.08,
    "CHEAP_ACCUM_QUOTE_EDGE_BONUS": 0.45,
    "CHEAP_ACCUM_FRONT_SIZE_BONUS": 1,
    "CHEAP_ACCUM_BACK_SIZE_BONUS": 1,
    "CHEAP_ACCUM_Z_RELAX": -0.55,
    "CHEAP_ACCUM_TARGET_BUFFER": 20,
}


# ── Shared helpers ─────────────────────────────────────────────────────────────

def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def ema(prev: Optional[float], current: float, alpha: float) -> float:
    if prev is None:
        return current
    return (1.0 - alpha) * prev + alpha * current


class Book:
    """Parsed order book snapshot."""

    def __init__(self, depth: Optional[OrderDepth]) -> None:
        self.valid = False
        self.buy_levels: List[Tuple[int, int]] = []
        self.sell_levels: List[Tuple[int, int]] = []
        self.best_bid = self.best_ask = 0
        self.best_bid_vol = self.best_ask_vol = 0
        self.mid = self.micro = self.spread_val = self.imbalance = 0.0

        if depth is None:
            return
        self.buy_levels = sorted(
            ((int(p), int(v)) for p, v in depth.buy_orders.items()),
            key=lambda x: x[0], reverse=True,
        )
        self.sell_levels = sorted(
            ((int(p), abs(int(v))) for p, v in depth.sell_orders.items()),
            key=lambda x: x[0],
        )
        if not self.buy_levels or not self.sell_levels:
            return
        self.best_bid, self.best_bid_vol = self.buy_levels[0]
        self.best_ask, self.best_ask_vol = self.sell_levels[0]
        if self.best_bid >= self.best_ask:
            return
        self.mid = (self.best_bid + self.best_ask) / 2.0
        self.spread_val = float(self.best_ask - self.best_bid)
        total = self.best_bid_vol + self.best_ask_vol
        if total > 0:
            self.micro = (self.best_ask * self.best_bid_vol + self.best_bid * self.best_ask_vol) / total
            self.imbalance = (self.best_bid_vol - self.best_ask_vol) / total
        else:
            self.micro = self.mid
        self.valid = True


class Manager:
    """Capacity-tracking order builder."""

    def __init__(self, product: str, position: int, limit: int) -> None:
        self.product = product
        self.position = int(position)
        self.limit = int(limit)
        self.buy_cap = max(0, limit - position)
        self.sell_cap = max(0, limit + position)
        self.orders: List[Order] = []

    def projected(self) -> int:
        return self.position + sum(o.quantity for o in self.orders)

    def buy(self, price: int, qty: int) -> None:
        size = min(max(0, int(qty)), self.buy_cap)
        if size > 0:
            self.orders.append(Order(self.product, int(price), size))
            self.buy_cap -= size

    def sell(self, price: int, qty: int) -> None:
        size = min(max(0, int(qty)), self.sell_cap)
        if size > 0:
            self.orders.append(Order(self.product, int(price), -size))
            self.sell_cap -= size


# ── ASH_COATED_OSMIUM trader ───────────────────────────────────────────────────

class AshCoatedOsmiumTrader:
    """
    Trunk execution with a stronger local-fair layer.
    This keeps the simple, high-capture Osmium engine, but replaces the pure
    fixed-anchor fair with a stable-book / wall-mid style local fair and a
    slightly nonlinear reservation price.
    """

    def __init__(self, params: dict) -> None:
        self.p = params

    def _stable_mid(self, book: Book) -> float:
        bid_levels = book.buy_levels[:3]
        ask_levels = book.sell_levels[:3]
        bid_vol = sum(v for _, v in bid_levels)
        ask_vol = sum(v for _, v in ask_levels)
        if bid_vol <= 0 or ask_vol <= 0:
            return book.mid
        popular_bid = sum(px * vol for px, vol in bid_levels) / bid_vol
        popular_ask = sum(px * vol for px, vol in ask_levels) / ask_vol
        wall_bid = max(bid_levels, key=lambda x: (x[1], x[0]))[0]
        wall_ask = min(ask_levels, key=lambda x: (-x[1], x[0]))[0]
        popular_mid = (popular_bid + popular_ask) / 2.0
        wall_mid = (wall_bid + wall_ask) / 2.0
        return (
            (1.0 - float(self.p["WALL_MID_BLEND"])) * popular_mid
            + float(self.p["WALL_MID_BLEND"]) * wall_mid
        )

    def _fair_value(self, book: Book) -> float:
        stable_mid = self._stable_mid(book)
        depth = max(float(self.p["DEPTH_FLOOR"]), float(book.best_bid_vol + book.best_ask_vol))
        beta = float(self.p["DEPTH_IMPACT_SCALE"]) / depth
        return (
            float(self.p["ANCHOR_WEIGHT"]) * float(self.p["REFERENCE_PRICE"])
            + float(self.p["STABLE_MID_WEIGHT"]) * stable_mid
            + float(self.p["LOCAL_MICRO_WEIGHT"]) * (book.micro - book.mid)
            + (beta + float(self.p["LOCAL_IMBALANCE_BIAS"])) * book.imbalance
        )

    def _reservation(self, fair: float, projected_pos: int) -> float:
        inv_ratio = projected_pos / float(PRODUCT_LIMITS["ASH_COATED_OSMIUM"])
        inv_shift = float(self.p["INVENTORY_SKEW"]) * projected_pos
        inv_shift += float(self.p["INVENTORY_CURVE"]) * (inv_ratio ** 3)
        return fair - inv_shift

    def build_orders(self, state: TradingState) -> List[Order]:
        if not self.p.get("ENABLED", True):
            return []
        book = Book(state.order_depths.get("ASH_COATED_OSMIUM"))
        if not book.valid:
            return []
        position = int(state.position.get("ASH_COATED_OSMIUM", 0))
        mgr = Manager("ASH_COATED_OSMIUM", position, PRODUCT_LIMITS["ASH_COATED_OSMIUM"])

        fair = self._fair_value(book)
        reservation = self._reservation(fair, mgr.projected())

        # Toxic book detection
        adverse = float(self.p["ADVERSE_IMBALANCE"])
        strong = float(self.p["STRONG_IMBALANCE"])
        bid_toxic = book.imbalance < -adverse and book.micro < book.mid
        ask_toxic = book.imbalance > adverse and book.micro > book.mid
        buy_edge_needed = 1.8 if bid_toxic else 1.3
        sell_edge_needed = 1.8 if ask_toxic else 1.3

        # Tiered takes
        buy_edge = reservation - book.best_ask
        take_buy = 0
        for edge_thr, clip in [
            (self.p["TAKE_L1_EDGE"], self.p["TAKE_L1_SIZE"]),
            (self.p["TAKE_L2_EDGE"], self.p["TAKE_L2_SIZE"]),
            (self.p["TAKE_L3_EDGE"], self.p["TAKE_L3_SIZE"]),
        ]:
            if buy_edge >= max(float(edge_thr), buy_edge_needed):
                take_buy = int(clip)
        if take_buy > 0:
            pos = mgr.projected()
            if pos >= self.p["SOFT_LIMIT"]:
                take_buy = max(0, take_buy - 4)
            mgr.buy(book.best_ask, min(book.best_ask_vol, take_buy))

        sell_edge = book.best_bid - reservation
        take_sell = 0
        for edge_thr, clip in [
            (self.p["TAKE_L1_EDGE"], self.p["TAKE_L1_SIZE"]),
            (self.p["TAKE_L2_EDGE"], self.p["TAKE_L2_SIZE"]),
            (self.p["TAKE_L3_EDGE"], self.p["TAKE_L3_SIZE"]),
        ]:
            if sell_edge >= max(float(edge_thr), sell_edge_needed):
                take_sell = int(clip)
        if take_sell > 0:
            pos = mgr.projected()
            if pos <= -self.p["SOFT_LIMIT"]:
                take_sell = max(0, take_sell - 4)
            mgr.sell(book.best_bid, min(book.best_bid_vol, take_sell))

        # Dynamic quote edges (spread + imbalance + toxicity adjustments)
        base_edge = float(self.p["BASE_EDGE"])
        buy_qe = sell_qe = base_edge
        if book.spread_val <= 14:
            buy_qe -= 0.7; sell_qe -= 0.7
        elif book.spread_val >= 18:
            buy_qe += 0.7; sell_qe += 0.7
        if book.imbalance > strong:
            buy_qe -= 0.4; sell_qe += 0.2
        elif book.imbalance < -strong:
            buy_qe += 0.2; sell_qe -= 0.4
        if bid_toxic:
            buy_qe += 1.0
        if ask_toxic:
            sell_qe += 1.0
        pos = mgr.projected()
        soft = int(self.p["SOFT_LIMIT"])
        if pos >= soft:
            buy_qe += 1.2; sell_qe -= 0.8
        elif pos <= -soft:
            buy_qe -= 0.8; sell_qe += 1.2
        buy_qe = max(float(self.p["MIN_QUOTE_EDGE"]), buy_qe)
        sell_qe = max(float(self.p["MIN_QUOTE_EDGE"]), sell_qe)

        join_edge = float(self.p["JOIN_EDGE"])
        front_buy = int(round(reservation - buy_qe))
        front_sell = int(round(reservation + sell_qe))

        # Market-join: snap to existing resting order if it's at a good edge
        for price, _ in book.buy_levels[:2]:
            if reservation - price >= buy_qe:
                front_buy = price if reservation - price <= join_edge else price + 1
                break
        for price, _ in book.sell_levels[:2]:
            if price - reservation >= sell_qe:
                front_sell = price if price - reservation <= join_edge else price - 1
                break

        front_buy = min(front_buy, book.best_ask - 1)
        front_sell = max(front_sell, book.best_bid + 1)
        back_buy = min(front_buy - 2, book.best_ask - 1)
        back_sell = max(front_sell + 2, book.best_bid + 1)

        allow_bid = not (bid_toxic and pos > 8) and pos < soft + 6
        allow_ask = not (ask_toxic and pos < -8) and pos > -(soft + 6)

        front_sz = int(self.p["FRONT_SIZE"])
        back_sz = int(self.p["BACK_SIZE"])
        if allow_bid and front_buy < book.best_ask and front_buy > 0:
            mgr.buy(front_buy, front_sz)
            if back_buy > 0 and back_buy < book.best_ask:
                mgr.buy(back_buy, back_sz)
        if allow_ask and front_sell > book.best_bid:
            mgr.sell(front_sell, front_sz)
            if back_sell > book.best_bid:
                mgr.sell(back_sell, back_sz)

        return mgr.orders


# ── INTARIAN_PEPPER_ROOT trader ────────────────────────────────────────────────

class IntarianPepperRootTrader:
    """
    Directional MM for strongly trending asset (+1000 ticks/day).
    - State: anchor price + residual EMA persisted in traderData
    - Fair value: weighted blend of trend-line, mid, micro, flow + lookahead bonus
    - Position target: BASE_CARRY + early long bias (fades) + edge/zscore signals
    - Passive quotes anchored to RESERVATION (near mid), NOT to drift-adjusted fair
      → quotes land inside the spread and actually fill
    - Sell suppression in bullish state to stay long through the trend
    """

    def __init__(self, params: dict) -> None:
        self.p = params

    def build_orders(self, state: TradingState, memory: dict) -> Tuple[List[Order], dict]:
        if not self.p.get("ENABLED", True):
            return [], memory

        book = Book(state.order_depths.get("INTARIAN_PEPPER_ROOT"))
        if not book.valid:
            return [], memory

        position = int(state.position.get("INTARIAN_PEPPER_ROOT", 0))
        mgr = Manager("INTARIAN_PEPPER_ROOT", position, PRODUCT_LIMITS["INTARIAN_PEPPER_ROOT"])
        timestamp = int(getattr(state, "timestamp", 0))
        progress = clamp(timestamp / 999900.0, 0.0, 1.0)

        # ── Load / init persistent state ──────────────────────────────────────
        ps = memory.get("IPR_STATE", {})
        if not isinstance(ps, dict):
            ps = {}

        initialized = bool(ps.get("initialized", False))
        anchor = float(ps.get("anchor", 0.0))
        residual_ema_val = float(ps.get("residual_ema", 0.0))
        spread_ema_val = float(ps.get("spread_ema", 13.0))
        last_ts = float(ps.get("last_ts", -1.0))

        # Day reset
        if last_ts >= 0 and timestamp < last_ts:
            initialized = False
            anchor = 0.0
            residual_ema_val = 0.0
            spread_ema_val = 13.0

        drift = float(self.p["DRIFT_PER_TIMESTAMP"])
        trend_line = anchor + drift * timestamp

        if not initialized:
            anchor = round(book.mid / 1000.0) * 1000.0
            trend_line = anchor
            residual_ema_val = 0.0
            spread_ema_val = float(book.spread_val)
            initialized = True
        else:
            spread_ema_val = ema(spread_ema_val, book.spread_val, float(self.p["SPREAD_ALPHA"]))

        residual = book.mid - trend_line
        residual_ema_val = ema(residual_ema_val, residual, float(self.p["RESIDUAL_ALPHA"]))

        # ── Fair value ────────────────────────────────────────────────────────
        half_spread = max(1.0, book.spread_val / 2.0)
        flow_fair = book.mid + book.imbalance * half_spread
        lookahead = float(self.p["LOOKAHEAD_BONUS"]) * (1.0 - 0.65 * progress)
        fair = (
            0.60 * trend_line
            + 0.12 * book.mid
            + 0.10 * book.micro
            + 0.10 * flow_fair
            + 0.08 * (trend_line + residual)
            + lookahead
        )

        # ── z-score of residual ───────────────────────────────────────────────
        spread_scale = max(4.0, spread_ema_val * 0.45)
        zscore = residual / spread_scale

        # ── Target position ───────────────────────────────────────────────────
        edge = fair - book.mid
        target = float(self.p["BASE_CARRY"])
        early_factor = max(0.0, 1.0 - progress / 0.85)
        target += float(self.p["EARLY_LONG_BIAS"]) * early_factor
        target += float(self.p["EDGE_TARGET_SCALE"]) * edge

        if zscore < 0.0:
            target += float(self.p["ZSCORE_BUY_BONUS"]) * min(1.0, abs(zscore) / 1.8)
        if zscore > 0.45:
            target -= float(self.p["ZSCORE_SELL_PENALTY"]) * min(1.0, (zscore - 0.45) / 1.4)
        if book.imbalance < -0.18 and book.micro < book.mid:
            target -= 6.0

        bullish = (
            zscore < float(self.p["OVEREXTENSION_Z"])
            and book.imbalance >= float(self.p["BULLISH_IMBALANCE"])
            and book.micro >= book.mid
        )
        if bullish:
            target += 8.0

        if progress < 0.18 and zscore <= 0.45:
            target = max(target, 32.0)
        elif progress < 0.35 and zscore <= 0.25:
            target = max(target, 24.0)
        if progress > 0.85 and zscore > 1.25:
            target -= 8.0

        max_long = int(self.p["MAX_LONG_TARGET"])
        max_short = int(self.p["MAX_SHORT_TARGET"])
        target_int = int(clamp(target, -max_short, max_long))

        # ── Reservation price ─────────────────────────────────────────────────
        skew = float(self.p["INVENTORY_SKEW"])
        reservation = fair - (mgr.projected() - target_int) * skew

        # ── Take orders ───────────────────────────────────────────────────────
        base_take = float(self.p["BASE_TAKE_EDGE"])
        buy_te = base_take
        sell_te = base_take + 0.55
        pos = mgr.projected()
        if pos < target_int:
            buy_te -= 0.35
        if pos > target_int:
            sell_te -= 0.05
        if zscore < -0.45:
            buy_te -= 0.30
        elif zscore > 0.85:
            sell_te -= 0.15
        if bullish:
            buy_te -= 0.10
            sell_te += 0.90
        if progress < 0.55 and pos < target_int:
            sell_te += 0.25
        if pos < max(20, target_int - 10):
            sell_te += 0.55
        if (
            progress < float(self.p["CHEAP_ACCUM_END"])
            and pos < target_int
            and zscore > float(self.p["CHEAP_ACCUM_Z_RELAX"])
        ):
            buy_te += float(self.p["CHEAP_ACCUM_TAKE_PENALTY"])
        buy_te = max(0.35, buy_te)
        sell_te = max(1.05, sell_te)

        buy_edge_avail = reservation - book.best_ask
        if buy_edge_avail >= buy_te and mgr.buy_cap > 0:
            qty = min(book.best_ask_vol, 16, max(0, target_int + 16 - mgr.projected()))
            mgr.buy(book.best_ask, qty)

        sell_edge_avail = book.best_bid - reservation
        if sell_edge_avail >= sell_te and mgr.sell_cap > 0:
            pos = mgr.projected()
            qty = min(book.best_bid_vol, 16, max(0, pos - (target_int - 4)))
            if bullish and pos < max(26, target_int - 6):
                qty = 0
            elif bullish and pos > 0:
                qty = min(qty, 4)
            mgr.sell(book.best_bid, qty)

        # ── Passive quotes ────────────────────────────────────────────────────
        # Anchored to RESERVATION (near actual mid), NOT to drift-adjusted fair.
        # This places quotes inside the spread where they can actually fill.
        base_qe = float(self.p["BASE_QUOTE_EDGE"])
        buy_qe = base_qe
        sell_qe = base_qe + 0.75
        pos = mgr.projected()
        if pos < target_int:
            buy_qe -= 0.55
        if pos > target_int:
            sell_qe -= 0.10
        if zscore < -0.55:
            buy_qe -= 0.30
        elif zscore > 1.00:
            sell_qe -= 0.15
        cheap_accum = (
            progress < float(self.p["CHEAP_ACCUM_END"])
            and pos < target_int
            and zscore > float(self.p["CHEAP_ACCUM_Z_RELAX"])
        )
        if cheap_accum:
            buy_qe -= float(self.p["CHEAP_ACCUM_QUOTE_EDGE_BONUS"])

        front_buy = math.floor(reservation - buy_qe)
        front_sell = math.ceil(reservation + sell_qe)

        if bullish and pos < target_int:
            front_buy = max(front_buy, book.best_bid + 1)
        elif cheap_accum and pos < target_int:
            front_buy = max(front_buy, book.best_bid + 1)
        if bullish and pos > 0:
            front_sell += 2

        front_buy = min(front_buy, book.best_ask - 1)
        front_sell = max(front_sell, book.best_bid + 1)
        back_buy = min(front_buy - 2, book.best_ask - 1)
        back_sell = max(front_sell + 2, book.best_bid + 1)

        # Sell suppression: don't sell when accumulating / bullish
        early_accum = float(self.p["EARLY_ACCUM_END"])
        allow_sell = True
        if progress < early_accum and pos < target_int - 6:
            allow_sell = False
        if bullish and pos < max(24, target_int - 4):
            allow_sell = False

        front_sz = int(self.p["PASSIVE_FRONT_SIZE"])
        back_sz = int(self.p["PASSIVE_BACK_SIZE"])
        buy_buf = int(self.p["PASSIVE_BUY_BUFFER"])
        sell_buf = int(self.p["PASSIVE_SELL_BUFFER"])
        buy_front_sz = front_sz + (int(self.p["CHEAP_ACCUM_FRONT_SIZE_BONUS"]) if cheap_accum else 0)
        buy_back_sz = back_sz + (int(self.p["CHEAP_ACCUM_BACK_SIZE_BONUS"]) if cheap_accum else 0)
        buy_cap_target = target_int + (
            int(self.p["CHEAP_ACCUM_TARGET_BUFFER"]) if cheap_accum else buy_buf
        )

        quotes: List[Tuple[str, int, int]] = []
        if front_buy > 0 and front_buy < book.best_ask:
            quotes.append(("buy", front_buy, buy_front_sz))
            if back_buy > 0 and back_buy < book.best_ask:
                quotes.append(("buy", back_buy, buy_back_sz))
        if allow_sell and front_sell > book.best_bid:
            sell_front = max(3, front_sz - (3 if bullish else 1))
            sell_back = max(2, back_sz - (2 if bullish else 1))
            quotes.append(("sell", front_sell, sell_front))
            if back_sell > book.best_bid:
                quotes.append(("sell", back_sell, sell_back))

        for side, price, size in quotes:
            pos = mgr.projected()
            if side == "buy" and pos < buy_cap_target:
                qty = min(size, mgr.buy_cap, max(0, buy_cap_target - pos))
                mgr.buy(price, qty)
            elif side == "sell" and pos > target_int - sell_buf:
                qty = min(size, mgr.sell_cap, max(0, pos - (target_int - sell_buf)))
                mgr.sell(price, qty)

        # ── Save state ────────────────────────────────────────────────────────
        memory["IPR_STATE"] = {
            "anchor": anchor,
            "residual_ema": residual_ema_val,
            "spread_ema": spread_ema_val,
            "last_ts": float(timestamp),
            "initialized": True,
        }

        return mgr.orders, memory


# ── Top-level Trader ───────────────────────────────────────────────────────────

class Trader:
    def __init__(self) -> None:
        self.ash = AshCoatedOsmiumTrader(DEFAULT_ASH_PARAMS)
        self.ipr = IntarianPepperRootTrader(DEFAULT_IPR_PARAMS)

    def _load_memory(self, trader_data: str) -> dict:
        if not trader_data:
            return {}
        try:
            parsed = json.loads(trader_data)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    def run(self, state: TradingState):
        memory = self._load_memory(state.traderData if hasattr(state, "traderData") else "")
        result: Dict[str, List[Order]] = {}

        if "ASH_COATED_OSMIUM" in state.order_depths:
            result["ASH_COATED_OSMIUM"] = self.ash.build_orders(state)

        if "INTARIAN_PEPPER_ROOT" in state.order_depths:
            ipr_orders, memory = self.ipr.build_orders(state, memory)
            result["INTARIAN_PEPPER_ROOT"] = ipr_orders

        trader_data = json.dumps(memory, separators=(",", ":"))
        return result, 0, trader_data