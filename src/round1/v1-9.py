from __future__ import annotations

import json
import math
from typing import Dict, List, Optional, Tuple

try:
    from datamodel import Order, OrderDepth, TradingState
except ModuleNotFoundError:
    from trader_factory.core.datamodel import Order, OrderDepth, TradingState


PRODUCT_LIMITS = {
    "ASH_COATED_OSMIUM": 80,
    "INTARIAN_PEPPER_ROOT": 80,
}


DEFAULT_ASH_PARAMS = {
    "ENABLED": True,
    "REFERENCE_PRICE": 10000.0,
    "ANCHOR_WEIGHT": 0.45,
    "STABLE_MID_WEIGHT": 0.55,
    "WALL_MID_BLEND": 0.25,
    "LOCAL_MICRO_WEIGHT": 0.30,
    "LOCAL_IMBALANCE_BIAS": 0.15,
    "DEPTH_IMPACT_SCALE": 30.0,
    "DEPTH_FLOOR": 8.0,
    "INVENTORY_SKEW": 0.07,
    "INVENTORY_CURVE": 2.50,
    "BASE_EDGE": -0.55,
    "JOIN_EDGE": 1.35,
    "FRONT_SIZE": 16,
    "BACK_SIZE": 5,
    "SOFT_LIMIT": 62,
    "TAKE_L1_EDGE": 0.95,
    "TAKE_L1_SIZE": 4,
    "TAKE_L2_EDGE": 1.45,
    "TAKE_L2_SIZE": 8,
    "TAKE_L3_EDGE": 3.60,
    "TAKE_L3_SIZE": 14,
    "MIN_QUOTE_EDGE": 1.95,
    "ADVERSE_IMBALANCE": 0.22,
    "STRONG_IMBALANCE": 0.16,
    "NORMAL_TAKE_EDGE": 1.10,
    "TOXIC_TAKE_EDGE": 1.85,
    "SPLIT_FAIR_STYLE": "guarded",
    "FAST_SIGNAL_CLIP": 2.00,
    "FAST_TAKE_WEIGHT": 0.80,
    "FAST_QUOTE_WEIGHT": 0.35,
    "REGIME_STYLE": "full",
    "CALM_DEPTH_MIN": 22.0,
    "CALM_SPREAD_MAX": 16.0,
    "CALM_IMBALANCE_MAX": 0.16,
    "DISLOCATION_EDGE": 2.20,
    "CLEAR_EDGE_LIMIT": 0.75,
    "CLEAR_BUFFER": 6,
    "SIZE_STYLE": "mild",
    "WIDE_SPREAD": 18.0,
    "ALLOW_JOIN": True,
    "VACUUM_GAP": 4,
    "VACUUM_SIZE": 2,
    "VACUUM_VISIBLE_EDGE": 2.5,
    "VACUUM_FAIR_BLEND": 0.65,
    "TIGHT_SPREAD_MAX": 16.0,
    "MICRO_IMBALANCE_FLOOR": 0.20,
    "STABLE_MAGNET_EDGE": 1.0,
    "STABLE_STRONG_EDGE": 1.25,
    "AGREE_SIGNAL_BONUS": 0.60,
    "MAGNET_SIGNAL_BONUS": 0.20,
    "DISAGREE_STABLE_DAMP": 0.00,
    "TRADE_CONFIRM_BONUS": 0.25,
    "USE_WALL_MID_BLEND": True,
    "USE_DEPTH_IMPACT": True,
    "USE_NONLINEAR_INVENTORY": True,
    "ENABLE_TAKE_LADDER": True,
}


DEFAULT_IPR_PARAMS = {
    "ENABLED": True,
    "DRIFT_PER_TIMESTAMP": 0.0026009226,
    "RESIDUAL_ALPHA": 0.10,
    "SPREAD_ALPHA": 0.08,
    "LOOKAHEAD_BONUS": 4.90,
    "BASE_CARRY": 7.70,
    "EARLY_LONG_BIAS": 43.20,
    "EDGE_TARGET_SCALE": 12.0,
    "ZSCORE_BUY_BONUS": 12.0,
    "ZSCORE_SELL_PENALTY": 8.0,
    "MAX_LONG_TARGET": 76.0,
    "MAX_SHORT_TARGET": 20,
    "EARLY_ACCUM_END": 0.42,
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
    "CHEAP_ACCUM_END": 0.56,
    "CHEAP_ACCUM_TAKE_PENALTY": 0.08,
    "CHEAP_ACCUM_QUOTE_EDGE_BONUS": 0.45,
    "CHEAP_ACCUM_FRONT_SIZE_BONUS": 1,
    "CHEAP_ACCUM_BACK_SIZE_BONUS": 1,
    "CHEAP_ACCUM_Z_RELAX": -0.55,
    "CHEAP_ACCUM_TARGET_BUFFER": 20,
}


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def ema(prev: Optional[float], current: float, alpha: float) -> float:
    if prev is None:
        return current
    return (1.0 - alpha) * prev + alpha * current


def sign(value: float, eps: float = 1e-9) -> int:
    if value > eps:
        return 1
    if value < -eps:
        return -1
    return 0


class Book:
    def __init__(self, depth: Optional[OrderDepth]) -> None:
        self.valid = False
        self.has_bid = False
        self.has_ask = False
        self.buy_levels: List[Tuple[int, int]] = []
        self.sell_levels: List[Tuple[int, int]] = []
        self.best_bid = self.best_ask = 0
        self.best_bid_vol = self.best_ask_vol = 0
        self.mid = self.micro = self.spread_val = self.imbalance = 0.0

        if depth is None:
            return
        self.buy_levels = sorted(
            ((int(p), int(v)) for p, v in depth.buy_orders.items()),
            key=lambda x: x[0],
            reverse=True,
        )
        self.sell_levels = sorted(
            ((int(p), abs(int(v))) for p, v in depth.sell_orders.items()),
            key=lambda x: x[0],
        )
        if self.buy_levels:
            self.has_bid = True
            self.best_bid, self.best_bid_vol = self.buy_levels[0]
        if self.sell_levels:
            self.has_ask = True
            self.best_ask, self.best_ask_vol = self.sell_levels[0]
        if not self.has_bid and not self.has_ask:
            return
        if not (self.has_bid and self.has_ask):
            visible_px = self.best_bid if self.has_bid else self.best_ask
            self.mid = float(visible_px)
            self.micro = self.mid
            self.spread_val = 0.0
            self.imbalance = 0.0
            return
        if self.best_bid >= self.best_ask:
            return
        self.mid = (self.best_bid + self.best_ask) / 2.0
        self.spread_val = float(self.best_ask - self.best_bid)
        total = self.best_bid_vol + self.best_ask_vol
        if total > 0:
            self.micro = (
                self.best_ask * self.best_bid_vol + self.best_bid * self.best_ask_vol
            ) / total
            self.imbalance = (self.best_bid_vol - self.best_ask_vol) / total
        else:
            self.micro = self.mid
        self.valid = True


class Manager:
    def __init__(self, product: str, position: int, limit: int) -> None:
        self.product = product
        self.position = int(position)
        self.limit = int(limit)
        self.buy_cap = max(0, limit - position)
        self.sell_cap = max(0, limit + position)
        self.orders: List[Order] = []

    def projected(self) -> int:
        return self.position + sum(order.quantity for order in self.orders)

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


class AshCoatedOsmiumTrader:
    def __init__(self, params: dict) -> None:
        self.p = params

    def _stable_mid(self, book: Book) -> float:
        bid_levels = book.buy_levels[:3]
        ask_levels = book.sell_levels[:3]
        bid_vol = sum(vol for _, vol in bid_levels)
        ask_vol = sum(vol for _, vol in ask_levels)
        if bid_vol <= 0 or ask_vol <= 0:
            return book.mid

        popular_bid = sum(px * vol for px, vol in bid_levels) / bid_vol
        popular_ask = sum(px * vol for px, vol in ask_levels) / ask_vol
        popular_mid = (popular_bid + popular_ask) / 2.0

        if not self.p.get("USE_WALL_MID_BLEND", True):
            return popular_mid

        wall_bid = max(bid_levels, key=lambda x: (x[1], x[0]))[0]
        wall_ask = min(ask_levels, key=lambda x: (-x[1], x[0]))[0]
        wall_mid = (wall_bid + wall_ask) / 2.0
        blend = float(self.p["WALL_MID_BLEND"])
        return (1.0 - blend) * popular_mid + blend * wall_mid

    def _slow_fair(self, book: Book) -> float:
        stable_mid = self._stable_mid(book)
        return (
            float(self.p["ANCHOR_WEIGHT"]) * float(self.p["REFERENCE_PRICE"])
            + float(self.p["STABLE_MID_WEIGHT"]) * stable_mid
        )

    def _trade_confirmation(self, state: TradingState, book: Book) -> float:
        flow = 0.0
        for trade in state.market_trades.get("ASH_COATED_OSMIUM", []):
            price = int(trade.price)
            qty = abs(int(trade.quantity))
            trade_sign = 0
            if price >= book.best_ask:
                trade_sign = 1
            elif price <= book.best_bid:
                trade_sign = -1
            elif price > book.mid:
                trade_sign = 1
            elif price < book.mid:
                trade_sign = -1
            flow += trade_sign * qty
        return clamp(flow / 20.0, -1.0, 1.0)

    def _signal_components(
        self,
        state: TradingState,
        book: Book,
    ) -> Tuple[float, float, float, float]:
        slow_fair = self._slow_fair(book)
        stable_mid = self._stable_mid(book)
        stable_gap = stable_mid - book.mid
        micro_gap = book.micro - book.mid
        half_spread = clamp(book.spread_val / 2.0, 6.0, 10.0)
        imbalance_gap = half_spread * book.imbalance
        depth = max(float(self.p["DEPTH_FLOOR"]), float(book.best_bid_vol + book.best_ask_vol))
        depth_beta = (
            float(self.p["DEPTH_IMPACT_SCALE"]) / depth
            if self.p.get("USE_DEPTH_IMPACT", True)
            else 0.0
        )
        imbalance_signal = imbalance_gap + depth_beta * book.imbalance
        tight_book = book.spread_val <= float(self.p["TIGHT_SPREAD_MAX"])
        base_signal = (
            0.95 * imbalance_signal
            + float(self.p["LOCAL_MICRO_WEIGHT"]) * micro_gap
        )
        if tight_book and abs(micro_gap) >= float(self.p["MICRO_IMBALANCE_FLOOR"]):
            # In the common tight-book regime, nonzero micro carries most of the
            # next-step information, so let it dominate the fast signal.
            base_signal = 1.15 * micro_gap + 0.85 * imbalance_signal

        stable_sign = sign(stable_gap, 0.20)
        imbalance_sign = sign(imbalance_signal, 0.12)
        agree = (
            stable_sign != 0
            and stable_sign == imbalance_sign
            and abs(stable_gap) >= 0.50
        )
        disagree = (
            stable_sign != 0
            and imbalance_sign != 0
            and stable_sign != imbalance_sign
            and abs(stable_gap) >= 0.75
        )

        fast_signal = base_signal
        conviction = 0.0
        if agree:
            fast_signal += float(self.p["AGREE_SIGNAL_BONUS"]) * stable_gap
            conviction += 0.40
            if abs(stable_gap) >= float(self.p["STABLE_MAGNET_EDGE"]):
                fast_signal += float(self.p["MAGNET_SIGNAL_BONUS"]) * stable_gap
                conviction += 0.30
            if abs(stable_gap) >= float(self.p["STABLE_STRONG_EDGE"]):
                conviction += 0.20
        elif disagree:
            fast_signal += float(self.p["DISAGREE_STABLE_DAMP"]) * stable_gap
            conviction += 0.15
        elif abs(stable_gap) >= float(self.p["STABLE_MAGNET_EDGE"]):
            fast_signal += 0.30 * stable_gap
            conviction += 0.20

        trade_confirm = self._trade_confirmation(state, book)
        if trade_confirm != 0.0 and sign(trade_confirm, 0.05) == imbalance_sign:
            fast_signal += float(self.p["TRADE_CONFIRM_BONUS"]) * trade_confirm
            conviction += 0.15

        clipped = clamp(fast_signal, -float(self.p["FAST_SIGNAL_CLIP"]), float(self.p["FAST_SIGNAL_CLIP"]))
        style = self.p.get("SPLIT_FAIR_STYLE", "guarded")
        if style == "blend":
            take_signal = float(self.p["FAST_TAKE_WEIGHT"]) * clipped
            quote_signal = float(self.p["FAST_QUOTE_WEIGHT"]) * clipped
        elif style == "guarded":
            take_signal = float(self.p["FAST_TAKE_WEIGHT"]) * clipped
            quote_signal = float(self.p["FAST_QUOTE_WEIGHT"]) * clipped
        else:
            take_signal = 0.0
            quote_signal = 0.0
        return slow_fair, take_signal, quote_signal, clamp(conviction, 0.0, 1.20)

    def _reservation(self, slow_fair: float, projected_pos: int) -> float:
        inv_shift = float(self.p["INVENTORY_SKEW"]) * projected_pos
        if self.p.get("USE_NONLINEAR_INVENTORY", True):
            inv_ratio = projected_pos / float(PRODUCT_LIMITS["ASH_COATED_OSMIUM"])
            inv_shift += float(self.p["INVENTORY_CURVE"]) * (inv_ratio ** 3)
        return slow_fair - inv_shift

    def _mode(
        self,
        book: Book,
        pos: int,
        soft: int,
        bid_toxic: bool,
        ask_toxic: bool,
        buy_edge: float,
        sell_edge: float,
        take_signal: float,
    ) -> str:
        if self.p.get("REGIME_STYLE", "none") == "none":
            return "normal"

        clear_buffer = int(self.p["CLEAR_BUFFER"])
        if abs(pos) >= soft + clear_buffer and max(buy_edge, sell_edge) <= float(self.p["CLEAR_EDGE_LIMIT"]):
            return "inventory_clear"

        return "normal"

    def _toxicity_levels(self, book: Book, pos: int, soft: int) -> Tuple[int, int]:
        adverse = float(self.p["ADVERSE_IMBALANCE"])
        wide_spread = book.spread_val >= float(self.p["WIDE_SPREAD"])

        bid_level = 0
        if book.imbalance < -adverse and book.micro < book.mid:
            bid_level = 1
            if (
                book.imbalance < -(adverse + 0.10)
                or (wide_spread and pos > 0)
                or pos > max(8, soft - 10)
            ):
                bid_level = 2

        ask_level = 0
        if book.imbalance > adverse and book.micro > book.mid:
            ask_level = 1
            if (
                book.imbalance > (adverse + 0.10)
                or (wide_spread and pos < 0)
                or pos < -max(8, soft - 10)
            ):
                ask_level = 2

        return bid_level, ask_level

    def _smoothed_toxicity_levels(
        self,
        raw_bid_level: int,
        raw_ask_level: int,
        pos: int,
        soft: int,
        memory: dict,
        timestamp: int,
        quiet_non_toxic_ticks: int = 0,
    ) -> Tuple[int, int, dict]:
        ash_state = memory.get("ASH_STATE", {})
        if not isinstance(ash_state, dict):
            ash_state = {}

        last_ts = int(ash_state.get("last_ts", -1))
        if last_ts >= 0 and timestamp < last_ts:
            ash_state = {}

        bid_score = float(ash_state.get("bid_toxic_score", 0.0))
        ask_score = float(ash_state.get("ask_toxic_score", 0.0))
        prev_bid_level = int(ash_state.get("bid_toxic_level", 0))
        prev_ask_level = int(ash_state.get("ask_toxic_level", 0))

        if raw_bid_level == 2:
            bid_score = min(4.0, bid_score * 0.74 + 1.30)
        elif raw_bid_level == 1:
            bid_score = min(4.0, bid_score * 0.78 + 0.68)
        else:
            if prev_bid_level == 2:
                bid_score = max(0.0, bid_score * 0.62 - 0.10)
            elif prev_bid_level == 1:
                bid_score = max(0.0, bid_score * 0.54 - 0.16)
            else:
                bid_score = max(0.0, bid_score * 0.48 - 0.20)

        if raw_ask_level == 2:
            ask_score = min(4.0, ask_score * 0.74 + 1.30)
        elif raw_ask_level == 1:
            ask_score = min(4.0, ask_score * 0.78 + 0.68)
        else:
            if prev_ask_level == 2:
                ask_score = max(0.0, ask_score * 0.62 - 0.10)
            elif prev_ask_level == 1:
                ask_score = max(0.0, ask_score * 0.54 - 0.16)
            else:
                ask_score = max(0.0, ask_score * 0.48 - 0.20)

        if raw_bid_level == 0 and raw_ask_level == 0 and quiet_non_toxic_ticks >= 6:
            bid_score = max(0.0, bid_score * 0.72 - 0.22)
            ask_score = max(0.0, ask_score * 0.72 - 0.22)

        bid_level = 0
        if raw_bid_level >= 1 or bid_score >= 0.85 or (prev_bid_level >= 1 and bid_score >= 0.45):
            bid_level = 1
        if (
            (raw_bid_level == 2 and pos > max(10, soft - 8) and bid_score >= 1.90)
            or bid_score >= 2.95
            or (prev_bid_level == 2 and bid_score >= 1.95)
        ):
            bid_level = 2

        ask_level = 0
        if raw_ask_level >= 1 or ask_score >= 0.85 or (prev_ask_level >= 1 and ask_score >= 0.45):
            ask_level = 1
        if (
            (raw_ask_level == 2 and pos < -max(10, soft - 8) and ask_score >= 1.90)
            or ask_score >= 2.95
            or (prev_ask_level == 2 and ask_score >= 1.95)
        ):
            ask_level = 2

        ash_state["bid_toxic_score"] = round(bid_score, 4)
        ash_state["ask_toxic_score"] = round(ask_score, 4)
        ash_state["bid_toxic_level"] = int(bid_level)
        ash_state["ask_toxic_level"] = int(ask_level)
        ash_state["last_ts"] = int(timestamp)
        memory["ASH_STATE"] = ash_state
        return bid_level, ask_level, memory

    def _size_mult(
        self,
        side: str,
        book: Book,
        pos: int,
        soft: int,
        bid_level: int,
        ask_level: int,
        mode: str,
    ) -> float:
        style = self.p.get("SIZE_STYLE", "none")
        if style == "none":
            return 1.0

        mult = 1.0
        if book.spread_val >= float(self.p["WIDE_SPREAD"]):
            mult -= 0.12
        if side == "buy" and book.imbalance < -float(self.p["ADVERSE_IMBALANCE"]):
            mult -= 0.12
        if side == "sell" and book.imbalance > float(self.p["ADVERSE_IMBALANCE"]):
            mult -= 0.12
        if side == "buy" and bid_level == 1:
            mult -= 0.12
        if side == "buy" and bid_level == 2:
            mult -= 0.26
        if side == "sell" and ask_level == 1:
            mult -= 0.12
        if side == "sell" and ask_level == 2:
            mult -= 0.26
        if side == "buy" and pos >= soft:
            mult -= 0.18
        if side == "sell" and pos <= -soft:
            mult -= 0.18
        if mode == "normal":
            mult += 0.08
        elif mode == "inventory_clear":
            if side == "buy" and pos > 0:
                mult -= 0.20
            if side == "sell" and pos < 0:
                mult -= 0.20
        return clamp(mult, 0.45, 1.30)

    def _attack_factor(
        self,
        book: Book,
        pos: int,
        soft: int,
        bid_level: int,
        ask_level: int,
        mode: str,
    ) -> float:
        if mode == "inventory_clear":
            return 0.0

        score = 0.0
        if book.spread_val <= 15.0:
            score += 1.0
        if (book.best_bid_vol + book.best_ask_vol) >= 26.0:
            score += 1.0
        if abs(book.imbalance) <= 0.18:
            score += 1.0
        if max(bid_level, ask_level) == 0:
            score += 1.0
        elif max(bid_level, ask_level) == 1:
            score += 0.5
        if abs(pos) <= max(8, soft - 10):
            score += 1.0
        return clamp((score - 2.0) / 4.0, 0.0, 1.0)

    def _execution_profile(self, mode: str, attack: float) -> Tuple[str, float, float, float, float]:
        if mode == "inventory_clear":
            return "defend", 0.0, 0.0, 1.0, 0.0
        if attack >= 0.75:
            return "attack", 0.40, 0.40, 1.22, 0.35
        if attack >= 0.40:
            return "press", 0.20, 0.20, 1.12, 0.18
        return "balanced", 0.08, 0.08, 1.05, 0.08

    def _vacuum_fair(
        self,
        side: str,
        visible_price: int,
        frozen_fair: float,
        last_good_spread: float,
    ) -> float:
        half_spread = clamp(last_good_spread / 2.0, 6.0, 10.0)
        side_fair = visible_price + half_spread if side == "bid_only" else visible_price - half_spread
        blend = float(self.p["VACUUM_FAIR_BLEND"])
        return blend * side_fair + (1.0 - blend) * frozen_fair

    def build_orders(self, state: TradingState, memory: dict) -> Tuple[List[Order], dict]:
        if not self.p.get("ENABLED", True):
            return [], memory

        book = Book(state.order_depths.get("ASH_COATED_OSMIUM"))
        position = int(state.position.get("ASH_COATED_OSMIUM", 0))
        mgr = Manager("ASH_COATED_OSMIUM", position, PRODUCT_LIMITS["ASH_COATED_OSMIUM"])
        timestamp = int(getattr(state, "timestamp", 0))
        ash_state = memory.get("ASH_STATE", {})
        if not isinstance(ash_state, dict):
            ash_state = {}

        last_fill_ts = int(ash_state.get("last_fill_ts", -1))
        own_ash_trades = state.own_trades.get("ASH_COATED_OSMIUM", [])
        if own_ash_trades:
            last_fill_ts = max(last_fill_ts, max(int(tr.timestamp) for tr in own_ash_trades))
        no_fill_ticks = max(0, timestamp - last_fill_ts) if last_fill_ts >= 0 else 0

        if not book.has_bid and not book.has_ask:
            ash_state["last_fill_ts"] = int(last_fill_ts)
            ash_state["no_fill_ticks"] = int(no_fill_ticks)
            memory["ASH_STATE"] = ash_state
            return [], memory

        reference_price = float(self.p["REFERENCE_PRICE"])
        last_good_fair = float(ash_state.get("last_good_fair", reference_price))
        last_good_spread = float(ash_state.get("last_good_spread", 16.0))
        frozen_fair = 0.70 * last_good_fair + 0.30 * reference_price
        prev_vacuum_side = ash_state.get("vacuum_side")
        prev_vacuum_ticks = int(ash_state.get("vacuum_ticks", 0))
        prev_vacuum_fair = float(ash_state.get("vacuum_fair", frozen_fair))

        if not book.valid:
            vacuum_side = "bid_only" if book.has_bid and not book.has_ask else "ask_only"
            visible_px = book.best_bid if vacuum_side == "bid_only" else book.best_ask
            vacuum_fair = self._vacuum_fair(vacuum_side, visible_px, frozen_fair, last_good_spread)
            ash_state["vacuum_side"] = vacuum_side
            ash_state["vacuum_ticks"] = prev_vacuum_ticks + 1
            ash_state["vacuum_fair"] = round(vacuum_fair, 4)
            ash_state["last_fill_ts"] = int(last_fill_ts)
            ash_state["no_fill_ticks"] = int(no_fill_ticks)
            ash_state["last_ts"] = int(timestamp)
            memory["ASH_STATE"] = ash_state

            pos = mgr.projected()
            quote_gap = int(self.p["VACUUM_GAP"])
            quote_size = int(self.p["VACUUM_SIZE"])
            visible_edge = float(self.p["VACUUM_VISIBLE_EDGE"])

            # Quote the visible side lightly when the refill edge is strong enough, and
            # keep the missing-side flattening quote for exposed inventory.
            if vacuum_side == "ask_only" and pos < 0 and book.best_ask > 0:
                bid_px = min(book.best_ask - quote_gap, int(round(frozen_fair - quote_gap)))
                if bid_px > 0 and bid_px < book.best_ask:
                    mgr.buy(bid_px, min(quote_size, -pos))
            elif vacuum_side == "bid_only" and pos > 0 and book.best_bid > 0:
                ask_px = max(book.best_bid + quote_gap, int(round(frozen_fair + quote_gap)))
                if ask_px > book.best_bid:
                    mgr.sell(ask_px, min(quote_size, pos))

            if vacuum_side == "bid_only" and book.best_bid > 0 and (vacuum_fair - book.best_bid) >= visible_edge and pos < 18:
                bid_px = int(min(book.best_bid + 1, math.floor(vacuum_fair - 1.5)))
                if bid_px > 0:
                    mgr.buy(bid_px, min(quote_size, max(0, 18 - pos)))
            elif vacuum_side == "ask_only" and book.best_ask > 0 and (book.best_ask - vacuum_fair) >= visible_edge and pos > -18:
                ask_px = int(max(book.best_ask - 1, math.ceil(vacuum_fair + 1.5)))
                if ask_px > 0:
                    mgr.sell(ask_px, min(quote_size, max(0, pos + 18)))

            return mgr.orders, memory

        slow_fair, take_signal, quote_signal, signal_conviction = self._signal_components(state, book)
        if prev_vacuum_side in ("bid_only", "ask_only") and prev_vacuum_ticks > 0:
            slow_fair = 0.50 * slow_fair + 0.50 * prev_vacuum_fair
            if prev_vacuum_side == "ask_only":
                quote_signal = min(quote_signal, 0.0)
                take_signal = min(take_signal, 0.10)
            else:
                quote_signal = max(quote_signal, 0.0)
                take_signal = max(take_signal, -0.10)
        reservation = self._reservation(slow_fair, mgr.projected())

        adverse = float(self.p["ADVERSE_IMBALANCE"])
        strong = float(self.p["STRONG_IMBALANCE"])
        bid_toxic = book.imbalance < -adverse and book.micro < book.mid
        ask_toxic = book.imbalance > adverse and book.micro > book.mid

        take_reservation = reservation + take_signal
        buy_edge = take_reservation - book.best_ask
        sell_edge = book.best_bid - take_reservation
        soft = int(self.p["SOFT_LIMIT"])
        pos = mgr.projected()
        mode = self._mode(book, pos, soft, bid_toxic, ask_toxic, buy_edge, sell_edge, take_signal)
        raw_bid_level, raw_ask_level = self._toxicity_levels(book, pos, soft)
        bid_level, ask_level, memory = self._smoothed_toxicity_levels(
            raw_bid_level,
            raw_ask_level,
            pos,
            soft,
            memory,
            timestamp,
            quiet_non_toxic_ticks=no_fill_ticks if raw_bid_level == 0 and raw_ask_level == 0 else 0,
        )
        attack = clamp(
            self._attack_factor(book, pos, soft, bid_level, ask_level, mode) + 0.25 * signal_conviction,
            0.0,
            1.0,
        )
        profile, take_bonus, edge_bonus, size_bonus, join_bonus = self._execution_profile(mode, attack)

        take_levels = [
            (float(self.p["TAKE_L1_EDGE"]), int(self.p["TAKE_L1_SIZE"])),
            (float(self.p["TAKE_L2_EDGE"]), int(self.p["TAKE_L2_SIZE"])),
            (float(self.p["TAKE_L3_EDGE"]), int(self.p["TAKE_L3_SIZE"])),
        ]

        can_take_buy = True
        can_take_sell = True
        buy_need = float(self.p["NORMAL_TAKE_EDGE"])
        sell_need = float(self.p["NORMAL_TAKE_EDGE"])

        if bid_level == 1:
            buy_need = max(buy_need, float(self.p["TOXIC_TAKE_EDGE"]) - 0.20)
        elif bid_level == 2:
            buy_need = max(buy_need, float(self.p["TOXIC_TAKE_EDGE"]) + 0.05)
        if ask_level == 1:
            sell_need = max(sell_need, float(self.p["TOXIC_TAKE_EDGE"]) - 0.20)
        elif ask_level == 2:
            sell_need = max(sell_need, float(self.p["TOXIC_TAKE_EDGE"]) + 0.05)

        if mode == "normal":
            buy_need = max(0.90, buy_need - 0.15)
            sell_need = max(0.90, sell_need - 0.15)
        elif mode == "inventory_clear":
            if pos > 0:
                can_take_buy = False
            elif pos < 0:
                can_take_sell = False
        if bid_level == 2 and pos > 6:
            can_take_buy = False
        if ask_level == 2 and pos < -6:
            can_take_sell = False

        if profile != "defend":
            scaled_take_bonus = take_bonus * max(0.5, attack if profile != "balanced" else 1.0)
            buy_need = max(0.70, buy_need - scaled_take_bonus)
            sell_need = max(0.70, sell_need - scaled_take_bonus)
        if signal_conviction > 0.0:
            if take_signal > 0.0:
                buy_need = max(0.70, buy_need - 0.15 * signal_conviction)
            elif take_signal < 0.0:
                sell_need = max(0.70, sell_need - 0.15 * signal_conviction)

        reactivation = (
            no_fill_ticks >= 10
            and mode == "normal"
            and max(bid_level, ask_level) == 0
            and abs(pos) <= max(8, soft - 8)
            and prev_vacuum_side not in ("bid_only", "ask_only")
            and book.spread_val <= 16
        )
        react_side = sign(quote_signal, 0.10)
        micro_nibble = (
            reactivation
            and react_side != 0
            and abs(quote_signal) >= 0.28
            and signal_conviction >= 0.35
        )
        if micro_nibble:
            if react_side > 0 and can_take_buy and buy_edge >= max(0.80, buy_need - 0.25):
                mgr.buy(book.best_ask, min(book.best_ask_vol, 2))
            elif react_side < 0 and can_take_sell and sell_edge >= max(0.80, sell_need - 0.25):
                mgr.sell(book.best_bid, min(book.best_bid_vol, 2))

        if self.p.get("ENABLE_TAKE_LADDER", True) and can_take_buy:
            take_buy = 0
            for edge_thr, clip in take_levels:
                if buy_edge >= max(edge_thr, buy_need):
                    take_buy = clip
            if take_buy > 0:
                if pos >= soft:
                    take_buy = max(0, take_buy - 3)
                mgr.buy(book.best_ask, min(book.best_ask_vol, take_buy))

        if self.p.get("ENABLE_TAKE_LADDER", True) and can_take_sell:
            take_sell = 0
            for edge_thr, clip in take_levels:
                if sell_edge >= max(edge_thr, sell_need):
                    take_sell = clip
            if take_sell > 0:
                if pos <= -soft:
                    take_sell = max(0, take_sell - 3)
                mgr.sell(book.best_bid, min(book.best_bid_vol, take_sell))

        buy_qe = float(self.p["BASE_EDGE"])
        sell_qe = float(self.p["BASE_EDGE"])
        if book.spread_val <= 14:
            buy_qe -= 0.65
            sell_qe -= 0.65
        elif book.spread_val >= 18:
            buy_qe += 0.70
            sell_qe += 0.70
        if book.imbalance > strong:
            buy_qe -= 0.35
            sell_qe += 0.20
        elif book.imbalance < -strong:
            buy_qe += 0.20
            sell_qe -= 0.35
        if bid_level == 1:
            buy_qe += 0.55
        elif bid_level == 2:
            buy_qe += 1.15
        if ask_level == 1:
            sell_qe += 0.55
        elif ask_level == 2:
            sell_qe += 1.15
        if pos >= soft:
            buy_qe += 1.20
            sell_qe -= 0.55
        elif pos <= -soft:
            buy_qe -= 0.55
            sell_qe += 1.20

        if mode == "normal":
            buy_qe -= 0.20
            sell_qe -= 0.20
            if pos > 6 and bid_level >= 1:
                sell_qe -= 0.10
            elif pos < -6 and ask_level >= 1:
                buy_qe -= 0.10
        elif mode == "inventory_clear":
            if pos > 0:
                buy_qe += 0.90
                sell_qe -= 0.25
            elif pos < 0:
                buy_qe -= 0.25
                sell_qe += 0.90

        if profile != "defend":
            scaled_edge_bonus = edge_bonus * max(0.5, attack if profile != "balanced" else 1.0)
            buy_qe -= scaled_edge_bonus
            sell_qe -= scaled_edge_bonus
        if signal_conviction > 0.0:
            if quote_signal > 0.0:
                buy_qe -= 0.10 * signal_conviction
            elif quote_signal < 0.0:
                sell_qe -= 0.10 * signal_conviction

        if reactivation:
            extra = min(0.30, 0.05 * (no_fill_ticks - 8))
            if react_side > 0:
                buy_qe -= 0.15 + extra
                if micro_nibble:
                    buy_qe -= 0.05
            elif react_side < 0:
                sell_qe -= 0.15 + extra
                if micro_nibble:
                    sell_qe -= 0.05

        buy_qe = max(float(self.p["MIN_QUOTE_EDGE"]), buy_qe)
        sell_qe = max(float(self.p["MIN_QUOTE_EDGE"]), sell_qe)

        quote_mid = reservation + quote_signal
        join_edge = float(self.p["JOIN_EDGE"])
        if mode == "normal":
            join_edge += 0.10
        if profile != "defend":
            join_edge += join_bonus
        front_buy = int(round(quote_mid - buy_qe))
        front_sell = int(round(quote_mid + sell_qe))

        if self.p.get("ALLOW_JOIN", True):
            for price, _ in book.buy_levels[:2]:
                if quote_mid - price < buy_qe:
                    continue
                if mode == "inventory_clear" or bid_level >= 2:
                    break
                front_buy = price if quote_mid - price <= join_edge else price + 1
                break
            for price, _ in book.sell_levels[:2]:
                if price - quote_mid < sell_qe:
                    continue
                if mode == "inventory_clear" or ask_level >= 2:
                    break
                front_sell = price if price - quote_mid <= join_edge else price - 1
                break

        if profile == "attack":
            front_buy = max(front_buy, book.best_bid + 1)
            front_sell = min(front_sell, book.best_ask - 1)
        elif profile == "press":
            front_buy = max(front_buy, book.best_bid)
            front_sell = min(front_sell, book.best_ask)

        front_buy = min(front_buy, book.best_ask - 1)
        front_sell = max(front_sell, book.best_bid + 1)
        back_buy = min(front_buy - 2, book.best_ask - 1)
        back_sell = max(front_sell + 2, book.best_bid + 1)

        allow_bid = pos < soft + 6
        allow_ask = pos > -(soft + 6)
        if mode == "inventory_clear":
            if pos > 0:
                allow_bid = False
            elif pos < 0:
                allow_ask = False
        if bid_level >= 2 and pos > 8:
            allow_bid = False
        if ask_level >= 2 and pos < -8:
            allow_ask = False

        buy_mult = self._size_mult("buy", book, pos, soft, bid_level, ask_level, mode)
        sell_mult = self._size_mult("sell", book, pos, soft, bid_level, ask_level, mode)
        buy_mult *= size_bonus
        sell_mult *= size_bonus
        front_sz = int(self.p["FRONT_SIZE"])
        back_sz = int(self.p["BACK_SIZE"])
        buy_front_sz = max(2, int(round(front_sz * buy_mult)))
        sell_front_sz = max(2, int(round(front_sz * sell_mult)))
        buy_back_sz = max(1, int(round(back_sz * buy_mult)))
        sell_back_sz = max(1, int(round(back_sz * sell_mult)))
        if profile == "attack":
            buy_front_sz += 3
            sell_front_sz += 3
        elif profile == "press":
            buy_front_sz += 2
            sell_front_sz += 2
        else:
            buy_front_sz += 1
            sell_front_sz += 1
        if signal_conviction >= 0.95:
            if quote_signal > 0.0:
                buy_front_sz += 1
            elif quote_signal < 0.0:
                sell_front_sz += 1
        if reactivation:
            if react_side > 0:
                buy_front_sz += 1 + int(no_fill_ticks >= 12)
                if micro_nibble:
                    buy_front_sz += 1
            elif react_side < 0:
                sell_front_sz += 1 + int(no_fill_ticks >= 12)
                if micro_nibble:
                    sell_front_sz += 1
        if pos > 6 and bid_level >= 1:
            sell_front_sz += 1
        elif pos < -6 and ask_level >= 1:
            buy_front_sz += 1

        if allow_bid and front_buy > 0 and front_buy < book.best_ask:
            mgr.buy(front_buy, buy_front_sz)
            if back_buy > 0 and back_buy < book.best_ask:
                mgr.buy(back_buy, buy_back_sz)
        if allow_ask and front_sell > book.best_bid:
            mgr.sell(front_sell, sell_front_sz)
            if back_sell > book.best_bid:
                mgr.sell(back_sell, sell_back_sz)

        ash_state = memory.get("ASH_STATE", {})
        if not isinstance(ash_state, dict):
            ash_state = {}
        ash_state["last_good_fair"] = round(slow_fair, 4)
        ash_state["last_good_bid"] = int(book.best_bid)
        ash_state["last_good_ask"] = int(book.best_ask)
        ash_state["last_good_mid"] = round(book.mid, 4)
        ash_state["last_good_spread"] = round(book.spread_val, 4)
        ash_state["last_fill_ts"] = int(last_fill_ts)
        ash_state["no_fill_ticks"] = int(no_fill_ticks)
        if prev_vacuum_side in ("bid_only", "ask_only") and prev_vacuum_ticks > 0:
            remaining = max(0, prev_vacuum_ticks - 1)
            if remaining == 0:
                ash_state.pop("vacuum_side", None)
                ash_state.pop("vacuum_fair", None)
                ash_state["vacuum_ticks"] = 0
            else:
                ash_state["vacuum_side"] = prev_vacuum_side
                ash_state["vacuum_fair"] = round(prev_vacuum_fair, 4)
                ash_state["vacuum_ticks"] = remaining
        else:
            ash_state.pop("vacuum_side", None)
            ash_state.pop("vacuum_fair", None)
            ash_state["vacuum_ticks"] = 0
        memory["ASH_STATE"] = ash_state

        return mgr.orders, memory


class IntarianPepperRootTrader:
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

        ps = memory.get("IPR_STATE", {})
        if not isinstance(ps, dict):
            ps = {}

        initialized = bool(ps.get("initialized", False))
        anchor = float(ps.get("anchor", 0.0))
        residual_ema_val = float(ps.get("residual_ema", 0.0))
        spread_ema_val = float(ps.get("spread_ema", 13.0))
        last_ts = float(ps.get("last_ts", -1.0))

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

        spread_scale = max(4.0, spread_ema_val * 0.45)
        zscore = residual / spread_scale

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

        target_int = int(clamp(target, -int(self.p["MAX_SHORT_TARGET"]), int(self.p["MAX_LONG_TARGET"])))
        reservation = fair - (mgr.projected() - target_int) * float(self.p["INVENTORY_SKEW"])

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

        if reservation - book.best_ask >= buy_te and mgr.buy_cap > 0:
            qty = min(book.best_ask_vol, 16, max(0, target_int + 16 - mgr.projected()))
            mgr.buy(book.best_ask, qty)

        if book.best_bid - reservation >= sell_te and mgr.sell_cap > 0:
            pos = mgr.projected()
            qty = min(book.best_bid_vol, 16, max(0, pos - (target_int - 4)))
            if bullish and pos < max(26, target_int - 6):
                qty = 0
            elif bullish and pos > 0:
                qty = min(qty, 4)
            mgr.sell(book.best_bid, qty)

        buy_qe = float(self.p["BASE_QUOTE_EDGE"])
        sell_qe = float(self.p["BASE_QUOTE_EDGE"]) + 0.75
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

        allow_sell = True
        if progress < float(self.p["EARLY_ACCUM_END"]) and pos < target_int - 6:
            allow_sell = False
        if bullish and pos < max(24, target_int - 4):
            allow_sell = False

        buy_front_sz = int(self.p["PASSIVE_FRONT_SIZE"]) + (int(self.p["CHEAP_ACCUM_FRONT_SIZE_BONUS"]) if cheap_accum else 0)
        buy_back_sz = int(self.p["PASSIVE_BACK_SIZE"]) + (int(self.p["CHEAP_ACCUM_BACK_SIZE_BONUS"]) if cheap_accum else 0)
        buy_cap_target = target_int + (
            int(self.p["CHEAP_ACCUM_TARGET_BUFFER"]) if cheap_accum else int(self.p["PASSIVE_BUY_BUFFER"])
        )

        quotes: List[Tuple[str, int, int]] = []
        if front_buy > 0 and front_buy < book.best_ask:
            quotes.append(("buy", front_buy, buy_front_sz))
            if back_buy > 0 and back_buy < book.best_ask:
                quotes.append(("buy", back_buy, buy_back_sz))
        if allow_sell and front_sell > book.best_bid:
            sell_front = max(3, int(self.p["PASSIVE_FRONT_SIZE"]) - (3 if bullish else 1))
            sell_back = max(2, int(self.p["PASSIVE_BACK_SIZE"]) - (2 if bullish else 1))
            quotes.append(("sell", front_sell, sell_front))
            if back_sell > book.best_bid:
                quotes.append(("sell", back_sell, sell_back))

        for side, price, size in quotes:
            pos = mgr.projected()
            if side == "buy" and pos < buy_cap_target:
                qty = min(size, mgr.buy_cap, max(0, buy_cap_target - pos))
                mgr.buy(price, qty)
            elif side == "sell" and pos > target_int - int(self.p["PASSIVE_SELL_BUFFER"]):
                qty = min(size, mgr.sell_cap, max(0, pos - (target_int - int(self.p["PASSIVE_SELL_BUFFER"]))))
                mgr.sell(price, qty)

        memory["IPR_STATE"] = {
            "anchor": anchor,
            "residual_ema": residual_ema_val,
            "spread_ema": spread_ema_val,
            "last_ts": float(timestamp),
            "initialized": True,
        }
        return mgr.orders, memory


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
            ash_orders, memory = self.ash.build_orders(state, memory)
            result["ASH_COATED_OSMIUM"] = ash_orders

        if "INTARIAN_PEPPER_ROOT" in state.order_depths:
            ipr_orders, memory = self.ipr.build_orders(state, memory)
            result["INTARIAN_PEPPER_ROOT"] = ipr_orders

        trader_data = json.dumps(memory, separators=(",", ":"))
        return result, 0, trader_data