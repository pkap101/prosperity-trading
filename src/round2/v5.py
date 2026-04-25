from __future__ import annotations

import json
import math
from typing import Dict, List, Optional, Tuple

try:
    from datamodel import Order, OrderDepth, Trade, TradingState
except ModuleNotFoundError:
    from trader_factory.core.datamodel import Order, OrderDepth, Trade, TradingState


PRODUCT_LIMITS = {
    "ASH_COATED_OSMIUM": 80,
    "INTARIAN_PEPPER_ROOT": 80,
}

ROUND2_MAF_BID = 25000


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def ema(prev: Optional[float], current: float, alpha: float) -> float:
    if prev is None:
        return current
    return (1.0 - alpha) * prev + alpha * current


def sign(value: float, threshold: float = 0.0) -> int:
    if value > threshold:
        return 1
    if value < -threshold:
        return -1
    return 0


class Book:
    def __init__(self, depth: Optional[OrderDepth]) -> None:
        self.buy_levels: List[Tuple[int, int]] = []
        self.sell_levels: List[Tuple[int, int]] = []
        self.has_bid = False
        self.has_ask = False
        self.valid = False
        self.best_bid = 0
        self.best_ask = 0
        self.best_bid_vol = 0
        self.best_ask_vol = 0
        self.mid = 0.0
        self.micro = 0.0
        self.spread = 0.0
        self.imbalance = 0.0

        if depth is None:
            return

        self.buy_levels = sorted(
            ((int(price), int(volume)) for price, volume in depth.buy_orders.items()),
            key=lambda level: level[0],
            reverse=True,
        )
        self.sell_levels = sorted(
            ((int(price), abs(int(volume))) for price, volume in depth.sell_orders.items()),
            key=lambda level: level[0],
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
            visible = self.best_bid if self.has_bid else self.best_ask
            self.mid = float(visible)
            self.micro = self.mid
            return
        if self.best_bid >= self.best_ask:
            return

        self.valid = True
        self.mid = (self.best_bid + self.best_ask) / 2.0
        self.spread = float(self.best_ask - self.best_bid)
        total = self.best_bid_vol + self.best_ask_vol
        if total > 0:
            self.micro = (
                self.best_ask * self.best_bid_vol + self.best_bid * self.best_ask_vol
            ) / total
            self.imbalance = (self.best_bid_vol - self.best_ask_vol) / total
        else:
            self.micro = self.mid

    def stable_mid(self, levels: int = 3) -> float:
        bids = self.buy_levels[:levels]
        asks = self.sell_levels[:levels]
        if not bids or not asks:
            return self.mid
        bid_vol = sum(volume for _, volume in bids)
        ask_vol = sum(volume for _, volume in asks)
        if bid_vol <= 0 or ask_vol <= 0:
            return self.mid
        bid_price = sum(price * volume for price, volume in bids) / bid_vol
        ask_price = sum(price * volume for price, volume in asks) / ask_vol
        return (bid_price + ask_price) / 2.0


class OrderManager:
    def __init__(self, product: str, position: int, limit: int) -> None:
        self.product = product
        self.position = int(position)
        self.limit = int(limit)
        self.buy_cap = max(0, limit - position)
        self.sell_cap = max(0, limit + position)
        self.orders: List[Order] = []

    def projected(self) -> int:
        return self.position + sum(order.quantity for order in self.orders)

    def buy(self, price: int, quantity: int) -> None:
        size = min(max(0, int(quantity)), self.buy_cap)
        if size <= 0:
            return
        self.orders.append(Order(self.product, int(price), size))
        self.buy_cap -= size

    def sell(self, price: int, quantity: int) -> None:
        size = min(max(0, int(quantity)), self.sell_cap)
        if size <= 0:
            return
        self.orders.append(Order(self.product, int(price), -size))
        self.sell_cap -= size


class PepperDriftTrader:
    LIMIT = PRODUCT_LIMITS["INTARIAN_PEPPER_ROOT"]
    DRIFT_PER_TIMESTAMP = 0.0026009226
    RESIDUAL_ALPHA = 0.10
    SPREAD_ALPHA = 0.08
    LOOKAHEAD_BONUS = 4.90
    BASE_CARRY = 7.70
    EARLY_LONG_BIAS = 43.20
    EDGE_TARGET_SCALE = 12.0
    ZSCORE_BUY_BONUS = 12.0
    ZSCORE_SELL_PENALTY = 8.0
    MAX_TARGET = 80
    MAX_SHORT_TARGET = 20
    EARLY_ACCUM_END = 0.42
    INVENTORY_SKEW = 0.08
    BASE_TAKE_EDGE = 2.75
    BASE_QUOTE_EDGE = 5.20
    FRONT_SIZE = 9
    BACK_SIZE = 6
    PASSIVE_SELL_BUFFER = 8
    OVEREXTENSION_Z = 1.05
    BULLISH_IMBALANCE = 0.05
    CHEAP_ACCUM_END = 0.56
    CHEAP_ACCUM_TAKE_PENALTY = 0.08
    CHEAP_ACCUM_QUOTE_EDGE_BONUS = 0.45
    CHEAP_ACCUM_FRONT_SIZE_BONUS = 1
    CHEAP_ACCUM_BACK_SIZE_BONUS = 1
    CHEAP_ACCUM_Z_RELAX = -0.55
    CHEAP_ACCUM_TARGET_BUFFER = 20
    EXIT_ZSCORE = 1.05
    EXIT_SELL_RELIEF = 0.18
    EXIT_FRONT_IMPROVE = 1
    LATE_TRIM_START = 0.88
    LATE_TRIM_RELIEF = 0.12
    VACUUM_SIZE = 3
    VACUUM_GAP = 4
    VACUUM_FAIR_BLEND = 0.60

    def _vacuum_fair(
        self,
        side: str,
        visible_price: int,
        frozen_fair: float,
        last_good_spread: float,
    ) -> float:
        half_spread = clamp(last_good_spread / 2.0, 6.0, 10.0)
        side_fair = visible_price + half_spread if side == "bid_only" else visible_price - half_spread
        return self.VACUUM_FAIR_BLEND * side_fair + (1.0 - self.VACUUM_FAIR_BLEND) * frozen_fair

    def build_orders(self, state: TradingState, memory: dict) -> Tuple[List[Order], dict]:
        book = Book(state.order_depths.get("INTARIAN_PEPPER_ROOT"))
        if not book.has_bid and not book.has_ask:
            return [], memory

        position = int(state.position.get("INTARIAN_PEPPER_ROOT", 0))
        mgr = OrderManager("INTARIAN_PEPPER_ROOT", position, self.LIMIT)
        timestamp = int(getattr(state, "timestamp", 0))
        progress = clamp(timestamp / 999900.0, 0.0, 1.0)

        pstate = memory.get("PEPPER", {})
        if not isinstance(pstate, dict):
            pstate = {}

        initialized = bool(pstate.get("initialized", False))
        anchor = float(pstate.get("anchor", 0.0))
        residual_ema_val = float(pstate.get("residual_ema", 0.0))
        spread_ema_val = float(pstate.get("spread_ema", 13.0))
        last_ts = float(pstate.get("last_ts", -1.0))
        last_good_fair = float(
            pstate.get(
                "last_good_fair",
                round((book.mid if (book.has_bid or book.has_ask) else 13000.0) / 1000.0) * 1000.0,
            )
        )
        last_good_spread = float(pstate.get("last_good_spread", 13.0))

        if last_ts >= 0 and timestamp < last_ts:
            initialized = False
            anchor = 0.0
            residual_ema_val = 0.0
            spread_ema_val = 13.0
            last_good_fair = round((book.mid if (book.has_bid or book.has_ask) else 13000.0) / 1000.0) * 1000.0
            last_good_spread = 13.0

        if not book.valid:
            vacuum_side = "bid_only" if book.has_bid and not book.has_ask else "ask_only"
            visible_px = book.best_bid if vacuum_side == "bid_only" else book.best_ask
            frozen_fair = 0.70 * last_good_fair + 0.30 * round(visible_px / 1000.0) * 1000.0
            vacuum_fair = self._vacuum_fair(vacuum_side, visible_px, frozen_fair, last_good_spread)

            if vacuum_side == "ask_only" and position > 0 and book.best_ask > 0:
                ask_px = max(book.best_ask, int(math.ceil(vacuum_fair + self.VACUUM_GAP)))
                mgr.sell(ask_px, min(self.VACUUM_SIZE, position))
            elif vacuum_side == "bid_only" and position < 0 and book.best_bid > 0:
                bid_px = min(book.best_bid, int(math.floor(vacuum_fair - self.VACUUM_GAP)))
                if bid_px > 0:
                    mgr.buy(bid_px, min(self.VACUUM_SIZE, -position))

            pstate["anchor"] = anchor
            pstate["residual_ema"] = residual_ema_val
            pstate["spread_ema"] = spread_ema_val
            pstate["last_ts"] = float(timestamp)
            pstate["initialized"] = initialized
            pstate["last_good_fair"] = round(last_good_fair, 4)
            pstate["last_good_spread"] = round(last_good_spread, 4)
            memory["PEPPER"] = pstate
            return mgr.orders, memory

        drift = self.DRIFT_PER_TIMESTAMP
        trend_line = anchor + drift * timestamp

        if not initialized:
            anchor = round(book.mid / 1000.0) * 1000.0
            trend_line = anchor
            residual_ema_val = 0.0
            spread_ema_val = float(book.spread)
            initialized = True
        else:
            spread_ema_val = ema(spread_ema_val, book.spread, self.SPREAD_ALPHA)

        residual = book.mid - trend_line
        residual_ema_val = ema(residual_ema_val, residual, self.RESIDUAL_ALPHA)

        half_spread = max(1.0, book.spread / 2.0)
        flow_fair = book.mid + book.imbalance * half_spread
        lookahead = self.LOOKAHEAD_BONUS * (1.0 - 0.65 * progress)
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
        target = self.BASE_CARRY
        early_factor = max(0.0, 1.0 - progress / 0.85)
        target += self.EARLY_LONG_BIAS * early_factor
        target += self.EDGE_TARGET_SCALE * edge

        if zscore < 0.0:
            target += self.ZSCORE_BUY_BONUS * min(1.0, abs(zscore) / 1.8)
        if zscore > 0.45:
            target -= self.ZSCORE_SELL_PENALTY * min(1.0, (zscore - 0.45) / 1.4)
        if book.imbalance < -0.18 and book.micro < book.mid:
            target -= 6.0

        bullish = (
            zscore < self.OVEREXTENSION_Z
            and book.imbalance >= self.BULLISH_IMBALANCE
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

        target = int(clamp(target, -self.MAX_SHORT_TARGET, float(self.MAX_TARGET)))

        reservation = fair - (mgr.projected() - target) * self.INVENTORY_SKEW

        base_take = self.BASE_TAKE_EDGE
        buy_te = base_take
        sell_te = base_take + 0.55
        pos = mgr.projected()
        if pos < target:
            buy_te -= 0.35
        if pos > target:
            sell_te -= 0.05
        if zscore < -0.45:
            buy_te -= 0.30
        elif zscore > 0.85:
            sell_te -= 0.15
        if bullish:
            buy_te -= 0.10
            sell_te += 0.90
        if progress < 0.55 and pos < target:
            sell_te += 0.25
        if pos < max(20, target - 10):
            sell_te += 0.55
        cheap_accum = (
            progress < self.CHEAP_ACCUM_END
            and pos < target
            and zscore > self.CHEAP_ACCUM_Z_RELAX
        )
        if cheap_accum:
            buy_te += self.CHEAP_ACCUM_TAKE_PENALTY
        strong_up_extension = zscore >= self.EXIT_ZSCORE and book.micro >= book.mid
        if strong_up_extension and pos > max(20, target - 6):
            sell_te -= self.EXIT_SELL_RELIEF
        if progress >= self.LATE_TRIM_START and pos > max(24, target - 4):
            sell_te -= self.LATE_TRIM_RELIEF
        buy_te = max(0.35, buy_te)
        sell_te = max(1.05, sell_te)

        if reservation - book.best_ask >= buy_te and mgr.buy_cap > 0 and mgr.projected() < target:
            qty = min(book.best_ask_vol, 16, max(0, target - mgr.projected()))
            mgr.buy(book.best_ask, qty)

        if book.best_bid - reservation >= sell_te and mgr.sell_cap > 0:
            pos = mgr.projected()
            qty = min(book.best_bid_vol, 16, max(0, pos - (target - 4)))
            if bullish and pos < max(26, target - 6):
                qty = 0
            elif bullish and pos > 0:
                qty = min(qty, 4)
            if strong_up_extension and pos > max(20, target - 2):
                qty = max(qty, min(book.best_bid_vol, 8, pos - max(20, target - 2)))
            mgr.sell(book.best_bid, qty)

        buy_qe = self.BASE_QUOTE_EDGE
        sell_qe = self.BASE_QUOTE_EDGE + 0.75
        pos = mgr.projected()
        if pos < target:
            buy_qe -= 0.55
        if pos > target:
            sell_qe -= 0.10
        if zscore < -0.55:
            buy_qe -= 0.30
        elif zscore > 1.00:
            sell_qe -= 0.15
        if cheap_accum:
            buy_qe -= self.CHEAP_ACCUM_QUOTE_EDGE_BONUS
        if strong_up_extension and pos > max(20, target - 2):
            sell_qe -= 0.12
        if progress >= self.LATE_TRIM_START and pos > max(24, target - 4):
            sell_qe -= 0.08

        front_buy = math.floor(reservation - buy_qe)
        front_sell = math.ceil(reservation + sell_qe)
        if bullish and pos < target:
            front_buy = max(front_buy, book.best_bid + 1)
        elif cheap_accum and pos < target:
            front_buy = max(front_buy, book.best_bid + 1)
        if bullish and pos > 0:
            front_sell += 2
        if strong_up_extension and pos > max(20, target - 2):
            front_sell = min(front_sell, max(book.best_bid + 1, book.best_ask - self.EXIT_FRONT_IMPROVE))

        front_buy = min(front_buy, book.best_ask - 1)
        front_sell = max(front_sell, book.best_bid + 1)
        back_buy = min(front_buy - 2, book.best_ask - 1)
        back_sell = max(front_sell + 2, book.best_bid + 1)

        allow_sell = True
        if progress < self.EARLY_ACCUM_END and pos < target - 6:
            allow_sell = False
        if bullish and pos < max(24, target - 4):
            allow_sell = False

        buy_front_sz = self.FRONT_SIZE + (self.CHEAP_ACCUM_FRONT_SIZE_BONUS if cheap_accum else 0)
        buy_back_sz = self.BACK_SIZE + (self.CHEAP_ACCUM_BACK_SIZE_BONUS if cheap_accum else 0)
        buy_cap_target = target

        quotes: List[Tuple[str, int, int]] = []
        if front_buy > 0 and front_buy < book.best_ask:
            quotes.append(("buy", front_buy, buy_front_sz))
            if back_buy > 0 and back_buy < book.best_ask:
                quotes.append(("buy", back_buy, buy_back_sz))
        if allow_sell and front_sell > book.best_bid:
            sell_front = max(3, self.FRONT_SIZE - (3 if bullish else 1))
            sell_back = max(2, self.BACK_SIZE - (2 if bullish else 1))
            quotes.append(("sell", front_sell, sell_front))
            if back_sell > book.best_bid:
                quotes.append(("sell", back_sell, sell_back))

        for side, price, size in quotes:
            pos = mgr.projected()
            if side == "buy" and pos < buy_cap_target:
                qty = min(size, mgr.buy_cap, max(0, buy_cap_target - pos))
                mgr.buy(price, qty)
            elif side == "sell" and pos > target - self.PASSIVE_SELL_BUFFER:
                qty = min(size, mgr.sell_cap, max(0, pos - (target - self.PASSIVE_SELL_BUFFER)))
                mgr.sell(price, qty)

        pstate["anchor"] = anchor
        pstate["residual_ema"] = residual_ema_val
        pstate["spread_ema"] = spread_ema_val
        pstate["last_ts"] = float(timestamp)
        pstate["initialized"] = True
        pstate["last_good_fair"] = fair
        pstate["last_good_spread"] = book.spread
        memory["PEPPER"] = pstate
        return mgr.orders, memory


class AshLocalFairTrader:
    LIMIT = PRODUCT_LIMITS["ASH_COATED_OSMIUM"]
    ANCHOR = 10000.0
    ANCHOR_WEIGHT = 0.25
    STABLE_WEIGHT = 0.50
    MICRO_WEIGHT = 0.25
    INVENTORY_SKEW = 0.08
    SOFT_LIMIT = 60
    TAKE_EDGE = 1.00
    QUOTE_EDGE = 1.90
    JOIN_EDGE = 1.30
    FRONT_SIZE = 16
    BACK_SIZE = 7
    TOXIC_SOFT_IMBALANCE = 0.18
    TOXIC_STRONG_IMBALANCE = 0.28
    TOXIC_WIDE_SPREAD = 18.0
    MARKOUT_ALPHA = 0.18
    SOFT_BAD_MARKOUT = -0.45
    MARKOUT_EDGE_PENALTY = 0.12
    MARKOUT_SIZE_PENALTY = 0.10
    VACUUM_SIZE = 3
    VACUUM_GAP = 4

    def _deep_micro_signal(self, book: Book) -> Tuple[float, float]:
        bids = book.buy_levels[:3]
        asks = book.sell_levels[:3]
        if not bids or not asks:
            return 0.0, 0.0
        bid_vol = sum(volume for _, volume in bids)
        ask_vol = sum(volume for _, volume in asks)
        if bid_vol <= 0 or ask_vol <= 0:
            return 0.0, 0.0
        bid_price = sum(price * volume for price, volume in bids) / bid_vol
        ask_price = sum(price * volume for price, volume in asks) / ask_vol
        deep_mid = (bid_price + ask_price) / 2.0
        deep_imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol)
        return deep_mid - book.mid, deep_imbalance

    def _raw_toxicity_levels(self, book: Book, pos: int) -> Tuple[int, int]:
        bid_level = 0
        if book.imbalance < -self.TOXIC_SOFT_IMBALANCE and book.micro < book.mid:
            bid_level = 1
            if (
                book.imbalance < -self.TOXIC_STRONG_IMBALANCE
                or (book.spread >= self.TOXIC_WIDE_SPREAD and pos > 0)
                or pos > max(10, self.SOFT_LIMIT - 8)
            ):
                bid_level = 2

        ask_level = 0
        if book.imbalance > self.TOXIC_SOFT_IMBALANCE and book.micro > book.mid:
            ask_level = 1
            if (
                book.imbalance > self.TOXIC_STRONG_IMBALANCE
                or (book.spread >= self.TOXIC_WIDE_SPREAD and pos < 0)
                or pos < -max(10, self.SOFT_LIMIT - 8)
            ):
                ask_level = 2

        return bid_level, ask_level

    def _smoothed_toxicity_levels(
        self,
        raw_bid_level: int,
        raw_ask_level: int,
        pos: int,
        astate: dict,
        timestamp: int,
    ) -> Tuple[int, int, dict]:
        last_ts = int(astate.get("last_toxic_ts", -1))
        if last_ts >= 0 and timestamp < last_ts:
            astate = {"last_good_fair": astate.get("last_good_fair", self.ANCHOR)}

        bid_score = float(astate.get("bid_toxic_score", 0.0))
        ask_score = float(astate.get("ask_toxic_score", 0.0))
        prev_bid_level = int(astate.get("bid_toxic_level", 0))
        prev_ask_level = int(astate.get("ask_toxic_level", 0))

        if raw_bid_level == 2:
            bid_score = min(4.0, bid_score * 0.72 + 1.10)
        elif raw_bid_level == 1:
            bid_score = min(4.0, bid_score * 0.76 + 0.55)
        else:
            if prev_bid_level == 2:
                bid_score = max(0.0, bid_score * 0.60 - 0.10)
            elif prev_bid_level == 1:
                bid_score = max(0.0, bid_score * 0.52 - 0.14)
            else:
                bid_score = max(0.0, bid_score * 0.45 - 0.18)

        if raw_ask_level == 2:
            ask_score = min(4.0, ask_score * 0.72 + 1.10)
        elif raw_ask_level == 1:
            ask_score = min(4.0, ask_score * 0.76 + 0.55)
        else:
            if prev_ask_level == 2:
                ask_score = max(0.0, ask_score * 0.60 - 0.10)
            elif prev_ask_level == 1:
                ask_score = max(0.0, ask_score * 0.52 - 0.14)
            else:
                ask_score = max(0.0, ask_score * 0.45 - 0.18)

        bid_level = 0
        if raw_bid_level >= 1 or bid_score >= 0.75 or (prev_bid_level >= 1 and bid_score >= 0.40):
            bid_level = 1
        if (
            (raw_bid_level == 2 and pos > max(10, self.SOFT_LIMIT - 8) and bid_score >= 1.60)
            or bid_score >= 2.60
            or (prev_bid_level == 2 and bid_score >= 1.75)
        ):
            bid_level = 2

        ask_level = 0
        if raw_ask_level >= 1 or ask_score >= 0.75 or (prev_ask_level >= 1 and ask_score >= 0.40):
            ask_level = 1
        if (
            (raw_ask_level == 2 and pos < -max(10, self.SOFT_LIMIT - 8) and ask_score >= 1.60)
            or ask_score >= 2.60
            or (prev_ask_level == 2 and ask_score >= 1.75)
        ):
            ask_level = 2

        astate["bid_toxic_score"] = round(bid_score, 4)
        astate["ask_toxic_score"] = round(ask_score, 4)
        astate["bid_toxic_level"] = int(bid_level)
        astate["ask_toxic_level"] = int(ask_level)
        astate["last_toxic_ts"] = int(timestamp)
        return bid_level, ask_level, astate

    def _infer_markout_quality(
        self,
        book: Book,
        position: int,
        astate: dict,
    ) -> Tuple[float, float]:
        buy_markout = float(astate.get("buy_markout_ema", 0.0))
        sell_markout = float(astate.get("sell_markout_ema", 0.0))
        last_position = int(astate.get("last_position", position))
        prev_mid = astate.get("prev_mid")
        if prev_mid is not None:
            delta = position - last_position
            move = book.mid - float(prev_mid)
            if delta > 0:
                buy_markout = ema(buy_markout, move, self.MARKOUT_ALPHA)
            elif delta < 0:
                sell_markout = ema(sell_markout, -move, self.MARKOUT_ALPHA)
        return buy_markout, sell_markout

    def build_orders(self, state: TradingState, memory: dict) -> Tuple[List[Order], dict]:
        book = Book(state.order_depths.get("ASH_COATED_OSMIUM"))
        if not book.has_bid and not book.has_ask:
            return [], memory

        position = int(state.position.get("ASH_COATED_OSMIUM", 0))
        mgr = OrderManager("ASH_COATED_OSMIUM", position, self.LIMIT)
        timestamp = int(getattr(state, "timestamp", 0))

        astate = memory.get("ASH", {})
        if not isinstance(astate, dict):
            astate = {}
        last_good_fair = float(astate.get("last_good_fair", self.ANCHOR))
        last_buy_fill_ts = int(astate.get("last_buy_fill_ts", -1))
        last_sell_fill_ts = int(astate.get("last_sell_fill_ts", -1))
        own_ash_trades = state.own_trades.get("ASH_COATED_OSMIUM", [])
        for trade in own_ash_trades:
            tr_ts = int(getattr(trade, "timestamp", timestamp))
            if getattr(trade, "buyer", "") == "SUBMISSION":
                last_buy_fill_ts = max(last_buy_fill_ts, tr_ts)
            if getattr(trade, "seller", "") == "SUBMISSION":
                last_sell_fill_ts = max(last_sell_fill_ts, tr_ts)

        bars_since_buy_fill = (
            max(0, (timestamp - last_buy_fill_ts) // 100) if last_buy_fill_ts >= 0 else 0
        )
        bars_since_sell_fill = (
            max(0, (timestamp - last_sell_fill_ts) // 100) if last_sell_fill_ts >= 0 else 0
        )
        fill_gaps = []
        if last_buy_fill_ts >= 0:
            fill_gaps.append(bars_since_buy_fill)
        if last_sell_fill_ts >= 0:
            fill_gaps.append(bars_since_sell_fill)
        bars_since_fill = min(fill_gaps) if fill_gaps else 0

        if not book.valid:
            if book.has_ask and position > 0:
                fair = 0.65 * last_good_fair + 0.35 * (book.best_ask - 8.0)
                ask_price = max(book.best_ask, int(round(fair + self.VACUUM_GAP)))
                mgr.sell(ask_price, min(self.VACUUM_SIZE, position))
            elif book.has_bid and position < 0:
                fair = 0.65 * last_good_fair + 0.35 * (book.best_bid + 8.0)
                bid_price = min(book.best_bid, int(round(fair - self.VACUUM_GAP)))
                if bid_price > 0:
                    mgr.buy(bid_price, min(self.VACUUM_SIZE, -position))

            astate["last_good_fair"] = last_good_fair
            astate["last_buy_fill_ts"] = int(last_buy_fill_ts)
            astate["last_sell_fill_ts"] = int(last_sell_fill_ts)
            astate["bars_since_buy_fill"] = int(bars_since_buy_fill)
            astate["bars_since_sell_fill"] = int(bars_since_sell_fill)
            astate["bars_since_fill"] = int(bars_since_fill)
            astate["last_position"] = int(position)
            astate["prev_mid"] = float(book.mid)
            memory["ASH"] = astate
            return mgr.orders, memory

        stable_mid = book.stable_mid()
        local_fair = (
            self.ANCHOR_WEIGHT * self.ANCHOR
            + self.STABLE_WEIGHT * stable_mid
            + self.MICRO_WEIGHT * book.micro
        )
        stable_gap = stable_mid - book.mid
        micro_gap = book.micro - book.mid
        deep_micro_gap, deep_imbalance = self._deep_micro_signal(book)
        half_spread = max(1.0, book.spread / 2.0)
        imbalance_gap = half_spread * book.imbalance

        take_alpha = (
            0.50 * micro_gap
            + 0.25 * stable_gap
            + 0.15 * deep_micro_gap
            + 0.10 * imbalance_gap
        )
        quote_alpha = (
            0.30 * micro_gap
            + 0.35 * stable_gap
            + 0.05 * deep_micro_gap
            + 0.05 * imbalance_gap
        )
        stable_sign = sign(stable_gap, 0.20)
        imbalance_sign = sign(imbalance_gap + 0.35 * deep_imbalance, 0.10)
        if stable_sign != 0 and stable_sign == imbalance_sign:
            take_alpha += 0.05 * stable_gap
            quote_alpha += 0.03 * stable_gap
        elif stable_sign != 0 and imbalance_sign != 0 and stable_sign != imbalance_sign:
            quote_alpha *= 0.90

        buy_markout, sell_markout = self._infer_markout_quality(book, position, astate)
        reservation = local_fair - mgr.projected() * self.INVENTORY_SKEW
        take_fair = reservation + take_alpha
        quote_mid = reservation + quote_alpha
        raw_bid_level, raw_ask_level = self._raw_toxicity_levels(book, mgr.projected())
        bid_level, ask_level, astate = self._smoothed_toxicity_levels(
            raw_bid_level,
            raw_ask_level,
            mgr.projected(),
            astate,
            timestamp,
        )

        buy_need = self.TAKE_EDGE
        sell_need = self.TAKE_EDGE
        can_take_buy = True
        can_take_sell = True

        if bid_level == 1:
            buy_need += 0.20
        elif bid_level == 2:
            buy_need += 0.55
            if mgr.projected() > 10:
                can_take_buy = False

        if ask_level == 1:
            sell_need += 0.20
        elif ask_level == 2:
            sell_need += 0.55
            if mgr.projected() < -10:
                can_take_sell = False

        stale_side_base = (
            abs(mgr.projected()) <= max(8, self.SOFT_LIMIT - 8)
            and book.spread <= 16.0
            and max(bid_level, ask_level) <= 1
        )
        buy_reactivation = (
            stale_side_base
            and quote_alpha > 0.10
            and bid_level <= 1
            and bars_since_buy_fill >= 6
        )
        sell_reactivation = (
            stale_side_base
            and quote_alpha < -0.10
            and ask_level <= 1
            and bars_since_sell_fill >= 6
        )
        neutral_drip = (
            bars_since_fill >= 8
            and max(bid_level, ask_level) == 0
            and abs(mgr.projected()) <= 8
            and abs(quote_alpha) < 0.10
            and book.spread <= 16.0
        )
        micro_nibble = False
        if buy_reactivation and abs(quote_alpha) >= 0.28:
            micro_nibble = True
            if can_take_buy and take_fair - book.best_ask >= max(0.80, buy_need - 0.25):
                mgr.buy(book.best_ask, min(2, book.best_ask_vol))
        elif sell_reactivation and abs(quote_alpha) >= 0.28:
            micro_nibble = True
            if can_take_sell and book.best_bid - take_fair >= max(0.80, sell_need - 0.25):
                mgr.sell(book.best_bid, min(2, book.best_bid_vol))

        if can_take_buy and mgr.projected() < self.LIMIT and book.best_ask <= take_fair - buy_need:
            edge = take_fair - book.best_ask
            size = 4 if edge < 2.0 else 8
            if mgr.projected() >= self.SOFT_LIMIT:
                size = max(2, size - 3)
            if bid_level == 1:
                size = max(2, size - 2)
            mgr.buy(book.best_ask, min(size, book.best_ask_vol))

        if can_take_sell and mgr.projected() > -self.LIMIT and book.best_bid >= take_fair + sell_need:
            edge = book.best_bid - take_fair
            size = 4 if edge < 2.0 else 8
            if mgr.projected() <= -self.SOFT_LIMIT:
                size = max(2, size - 3)
            if ask_level == 1:
                size = max(2, size - 2)
            mgr.sell(book.best_bid, min(size, book.best_bid_vol))

        pos = mgr.projected()
        buy_edge = self.QUOTE_EDGE
        sell_edge = self.QUOTE_EDGE
        buy_join_edge = self.JOIN_EDGE
        sell_join_edge = self.JOIN_EDGE

        if book.spread >= 18.0:
            buy_edge += 0.50
            sell_edge += 0.50
        if book.imbalance > 0.18:
            buy_edge -= 0.20
            sell_edge += 0.15
        elif book.imbalance < -0.18:
            buy_edge += 0.15
            sell_edge -= 0.20
        if pos >= self.SOFT_LIMIT:
            buy_edge += 0.90
            sell_edge -= 0.20
        elif pos <= -self.SOFT_LIMIT:
            buy_edge -= 0.20
            sell_edge += 0.90
        if bid_level == 1:
            buy_edge += 0.35
            buy_join_edge += 0.30
        elif bid_level == 2:
            buy_edge += 0.85
            buy_join_edge += 0.70
        if ask_level == 1:
            sell_edge += 0.35
            sell_join_edge += 0.30
        elif ask_level == 2:
            sell_edge += 0.85
            sell_join_edge += 0.70
        if buy_reactivation:
            extra = min(0.30, 0.05 * max(0, bars_since_buy_fill - 6))
            buy_edge -= 0.15 + extra
            buy_join_edge += 0.20 + (0.05 if micro_nibble else 0.0)
            if micro_nibble:
                buy_edge -= 0.05
        elif sell_reactivation:
            extra = min(0.30, 0.05 * max(0, bars_since_sell_fill - 6))
            sell_edge -= 0.15 + extra
            sell_join_edge += 0.20 + (0.05 if micro_nibble else 0.0)
            if micro_nibble:
                sell_edge -= 0.05
        if neutral_drip:
            buy_edge -= 0.10
            sell_edge -= 0.10
            buy_join_edge += 0.10
            sell_join_edge += 0.10
        if buy_markout < self.SOFT_BAD_MARKOUT and book.imbalance <= 0.0:
            buy_edge += self.MARKOUT_EDGE_PENALTY
        if sell_markout < self.SOFT_BAD_MARKOUT and book.imbalance >= 0.0:
            sell_edge += self.MARKOUT_EDGE_PENALTY
        buy_edge = max(1.20, buy_edge)
        sell_edge = max(1.20, sell_edge)

        front_buy = int(round(quote_mid - buy_edge))
        front_sell = int(round(quote_mid + sell_edge))

        if book.best_bid > 0 and (quote_mid - book.best_bid) <= buy_join_edge:
            front_buy = max(front_buy, book.best_bid)
        elif book.best_bid + 1 < book.best_ask and (quote_mid - book.best_bid) > buy_join_edge:
            front_buy = max(front_buy, book.best_bid + 1)

        if book.best_ask > 0 and (book.best_ask - quote_mid) <= sell_join_edge:
            front_sell = min(front_sell, book.best_ask)
        elif book.best_ask - 1 > book.best_bid and (book.best_ask - quote_mid) > sell_join_edge:
            front_sell = min(front_sell, book.best_ask - 1)
        if buy_reactivation:
            if book.best_bid + 1 < book.best_ask:
                front_buy = max(front_buy, book.best_bid + 1)
            else:
                front_buy = max(front_buy, book.best_bid)
        elif sell_reactivation:
            if book.best_ask - 1 > book.best_bid:
                front_sell = min(front_sell, book.best_ask - 1)
            else:
                front_sell = min(front_sell, book.best_ask)
        if neutral_drip:
            front_buy = max(front_buy, book.best_bid)
            front_sell = min(front_sell, book.best_ask)

        front_buy = min(front_buy, book.best_ask - 1)
        front_sell = max(front_sell, book.best_bid + 1)
        back_buy = max(1, front_buy - 2)
        back_sell = front_sell + 2

        pos = mgr.projected()
        buy_size = self.FRONT_SIZE
        sell_size = self.FRONT_SIZE
        if book.imbalance < -0.22:
            buy_size = max(4, buy_size - 4)
        if book.imbalance > 0.22:
            sell_size = max(4, sell_size - 4)
        if bid_level == 1:
            buy_size = max(4, buy_size - 3)
        elif bid_level == 2:
            buy_size = max(2, buy_size - 7)
        if ask_level == 1:
            sell_size = max(4, sell_size - 3)
        elif ask_level == 2:
            sell_size = max(2, sell_size - 7)
        if pos >= self.SOFT_LIMIT:
            buy_size = max(2, buy_size - 6)
            sell_size += 2
        elif pos <= -self.SOFT_LIMIT:
            sell_size = max(2, sell_size - 6)
            buy_size += 2
        if buy_reactivation:
            buy_size += 1 + int(bars_since_buy_fill >= 10)
            if micro_nibble:
                buy_size += 1
        elif sell_reactivation:
            sell_size += 1 + int(bars_since_sell_fill >= 10)
            if micro_nibble:
                sell_size += 1
        if neutral_drip:
            buy_size = max(buy_size, 6)
            sell_size = max(sell_size, 6)
        if buy_markout < self.SOFT_BAD_MARKOUT and book.imbalance <= 0.0:
            buy_size = max(2, int(round(buy_size * (1.0 - self.MARKOUT_SIZE_PENALTY))))
        if sell_markout < self.SOFT_BAD_MARKOUT and book.imbalance >= 0.0:
            sell_size = max(2, int(round(sell_size * (1.0 - self.MARKOUT_SIZE_PENALTY))))

        pos = mgr.projected()
        allow_bid = pos < self.SOFT_LIMIT + 10 and not (bid_level >= 2 and pos > 8)
        allow_ask = pos > -(self.SOFT_LIMIT + 10) and not (ask_level >= 2 and pos < -8)

        if allow_bid and 0 < front_buy < book.best_ask:
            mgr.buy(front_buy, buy_size)
            if back_buy < book.best_ask and mgr.projected() < self.SOFT_LIMIT + 12:
                mgr.buy(back_buy, self.BACK_SIZE)
        if allow_ask and front_sell > book.best_bid:
            mgr.sell(front_sell, sell_size)
            if back_sell > book.best_bid and mgr.projected() > -(self.SOFT_LIMIT + 12):
                mgr.sell(back_sell, self.BACK_SIZE)

        astate["last_good_fair"] = float(local_fair)
        astate["last_buy_fill_ts"] = int(last_buy_fill_ts)
        astate["last_sell_fill_ts"] = int(last_sell_fill_ts)
        astate["bars_since_buy_fill"] = int(bars_since_buy_fill)
        astate["bars_since_sell_fill"] = int(bars_since_sell_fill)
        astate["bars_since_fill"] = int(bars_since_fill)
        astate["buy_markout_ema"] = round(buy_markout, 4)
        astate["sell_markout_ema"] = round(sell_markout, 4)
        astate["last_position"] = int(position)
        astate["prev_mid"] = float(book.mid)
        memory["ASH"] = astate
        return mgr.orders, memory


class Trader:
    def __init__(self) -> None:
        self.pepper = PepperDriftTrader()
        self.ash = AshLocalFairTrader()

    def bid(self):
        return ROUND2_MAF_BID

    def run(self, state: TradingState):
        try:
            memory = json.loads(state.traderData) if state.traderData else {}
            if not isinstance(memory, dict):
                memory = {}
        except Exception:
            memory = {}

        last_ts = int(memory.get("_last_ts", -1))
        if last_ts >= 0 and state.timestamp < last_ts:
            memory = {}

        result: Dict[str, List[Order]] = {}

        pepper_orders, memory = self.pepper.build_orders(state, memory)
        ash_orders, memory = self.ash.build_orders(state, memory)

        result["INTARIAN_PEPPER_ROOT"] = pepper_orders
        result["ASH_COATED_OSMIUM"] = ash_orders

        memory["_last_ts"] = int(state.timestamp)
        trader_data = json.dumps(memory, separators=(",", ":"))
        return result, 0, trader_data