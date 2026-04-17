from __future__ import annotations

from datamodel import Order, OrderDepth, TradingState

import json
from typing import Dict, List, Optional, Tuple


PEPPER = "INTARIAN_PEPPER_ROOT"
OSMIUM = "ASH_COATED_OSMIUM"


class Trader:
    POSITION_LIMITS = {
        PEPPER: 80,
        OSMIUM: 80,
    }

    PEPPER_REG_WINDOW = 100
    PEPPER_MIN_HISTORY = 30
    PEPPER_TAKE_THRESHOLD = 3.0
    PEPPER_MAKE_EDGE = 2.0
    PEPPER_MAX_POST_SIZE = 24
    PEPPER_MAX_TAKE_SIZE = 24

    OSMIUM_FAIR_VALUE = 10000.0
    OSMIUM_TAKE_EDGE = 2.0
    OSMIUM_STRONG_TAKE_EDGE = 0.0
    OSMIUM_MAX_POST_SIZE = 20
    OSMIUM_MAX_TAKE_SIZE = 20

    def __init__(self) -> None:
        self.pepper_mid_history: List[float] = []

    def run(self, state: TradingState):
        stored = self._load_state(state.traderData)
        self.pepper_mid_history = stored.get("pepper_mid_history", [])

        result: Dict[str, List[Order]] = {product: [] for product in state.order_depths}

        pepper_depth = state.order_depths.get(PEPPER)
        if pepper_depth is not None:
            pepper_position = state.position.get(PEPPER, 0)
            result[PEPPER] = self._trade_pepper(pepper_depth, pepper_position)

        osmium_depth = state.order_depths.get(OSMIUM)
        if osmium_depth is not None:
            osmium_position = state.position.get(OSMIUM, 0)
            result[OSMIUM] = self._trade_osmium(osmium_depth, osmium_position)

        trader_data = json.dumps(
            {
                "pepper_mid_history": self.pepper_mid_history[-self.PEPPER_REG_WINDOW :],
            },
            separators=(",", ":"),
        )
        return result, 0, trader_data

    def _load_state(self, raw: str) -> Dict[str, List[float]]:
        default = {"pepper_mid_history": []}
        if not raw:
            return default
        try:
            parsed = json.loads(raw)
        except Exception:
            return default
        if not isinstance(parsed, dict):
            return default
        history = parsed.get("pepper_mid_history", [])
        if not isinstance(history, list):
            history = []
        clean_history = []
        for value in history[-self.PEPPER_REG_WINDOW :]:
            try:
                clean_history.append(float(value))
            except Exception:
                continue
        return {"pepper_mid_history": clean_history}

    def _trade_pepper(self, depth: OrderDepth, position: int) -> List[Order]:
        orders: List[Order] = []
        mid = self._mid_price(depth)
        if mid is None:
            return orders

        self.pepper_mid_history.append(mid)
        self.pepper_mid_history = self.pepper_mid_history[-self.PEPPER_REG_WINDOW :]

        fair_value = self._rolling_regression_fair(self.pepper_mid_history)
        if fair_value is None:
            return orders

        residual = mid - fair_value
        buy_limit = self._buy_capacity(PEPPER, position, orders)
        sell_limit = self._sell_capacity(PEPPER, position, orders)

        for ask_price, ask_volume in sorted(depth.sell_orders.items()):
            ask_qty = max(0, -ask_volume)
            if ask_qty <= 0 or buy_limit <= 0:
                continue
            if ask_price <= fair_value - self.PEPPER_TAKE_THRESHOLD:
                trade_qty = min(ask_qty, buy_limit, self.PEPPER_MAX_TAKE_SIZE)
                if trade_qty > 0:
                    self._append_buy(orders, PEPPER, ask_price, trade_qty, position)
                    buy_limit = self._buy_capacity(PEPPER, position, orders)

        for bid_price, bid_volume in sorted(depth.buy_orders.items(), reverse=True):
            bid_qty = max(0, bid_volume)
            if bid_qty <= 0 or sell_limit <= 0:
                continue
            if bid_price >= fair_value + self.PEPPER_TAKE_THRESHOLD:
                trade_qty = min(bid_qty, sell_limit, self.PEPPER_MAX_TAKE_SIZE)
                if trade_qty > 0:
                    self._append_sell(orders, PEPPER, bid_price, trade_qty, position)
                    sell_limit = self._sell_capacity(PEPPER, position, orders)

        best_bid, best_ask = self._best_bid_ask(depth)
        if best_bid is None or best_ask is None:
            return orders

        live_position = self._effective_position(position, orders)
        inventory_skew = max(-3, min(3, int(round(live_position / 20))))
        residual_skew = max(-2, min(2, int(round(residual / 2.5))))
        total_skew = inventory_skew + residual_skew

        bid_quote = min(best_bid + 1, int(fair_value - self.PEPPER_MAKE_EDGE - total_skew))
        ask_quote = max(best_ask - 1, int(fair_value + self.PEPPER_MAKE_EDGE - total_skew))

        if bid_quote < ask_quote:
            buy_size = min(self.PEPPER_MAX_POST_SIZE, self._buy_capacity(PEPPER, position, orders))
            sell_size = min(self.PEPPER_MAX_POST_SIZE, self._sell_capacity(PEPPER, position, orders))
            if buy_size > 0:
                self._append_buy(orders, PEPPER, bid_quote, buy_size, position)
            if sell_size > 0:
                self._append_sell(orders, PEPPER, ask_quote, sell_size, position)

        return orders

    def _trade_osmium(self, depth: OrderDepth, position: int) -> List[Order]:
        orders: List[Order] = []
        best_bid, best_ask = self._best_bid_ask(depth)
        if best_bid is None or best_ask is None:
            return orders
        fair_value = self.OSMIUM_FAIR_VALUE

        for ask_price, ask_volume in sorted(depth.sell_orders.items()):
            ask_qty = max(0, -ask_volume)
            if ask_qty <= 0:
                continue
            buy_edge = self.OSMIUM_STRONG_TAKE_EDGE if position < -30 else self.OSMIUM_TAKE_EDGE
            if ask_price <= fair_value - buy_edge:
                trade_qty = min(ask_qty, self._buy_capacity(OSMIUM, position, orders), self.OSMIUM_MAX_TAKE_SIZE)
                if trade_qty > 0:
                    self._append_buy(orders, OSMIUM, ask_price, trade_qty, position)

        for bid_price, bid_volume in sorted(depth.buy_orders.items(), reverse=True):
            bid_qty = max(0, bid_volume)
            if bid_qty <= 0:
                continue
            sell_edge = self.OSMIUM_STRONG_TAKE_EDGE if position > 30 else self.OSMIUM_TAKE_EDGE
            if bid_price >= fair_value + sell_edge:
                trade_qty = min(bid_qty, self._sell_capacity(OSMIUM, position, orders), self.OSMIUM_MAX_TAKE_SIZE)
                if trade_qty > 0:
                    self._append_sell(orders, OSMIUM, bid_price, trade_qty, position)

        live_position = self._effective_position(position, orders)
        skew = max(-3, min(3, int(round(live_position / 16))))
        target_bid = int(fair_value - 1 - skew)
        target_ask = int(fair_value + 1 - skew)

        bid_quote = min(best_bid + 1, target_bid)
        ask_quote = max(best_ask - 1, target_ask)

        if bid_quote < ask_quote:
            buy_size = min(self.OSMIUM_MAX_POST_SIZE, self._buy_capacity(OSMIUM, position, orders))
            sell_size = min(self.OSMIUM_MAX_POST_SIZE, self._sell_capacity(OSMIUM, position, orders))
            if buy_size > 0:
                self._append_buy(orders, OSMIUM, bid_quote, buy_size, position)
            if sell_size > 0:
                self._append_sell(orders, OSMIUM, ask_quote, sell_size, position)

        return orders

    def _rolling_regression_fair(self, history: List[float]) -> Optional[float]:
        n = len(history)
        if n < self.PEPPER_MIN_HISTORY:
            return None
        x_mean = (n - 1) / 2.0
        y_mean = sum(history) / n

        cov = 0.0
        var = 0.0
        for i, price in enumerate(history):
            dx = i - x_mean
            cov += dx * (price - y_mean)
            var += dx * dx
        if var == 0:
            return history[-1]

        slope = cov / var
        intercept = y_mean - slope * x_mean
        return intercept + slope * (n - 1)

    def _mid_price(self, depth: OrderDepth) -> Optional[float]:
        best_bid, best_ask = self._best_bid_ask(depth)
        if best_bid is not None and best_ask is not None:
            return (best_bid + best_ask) / 2.0
        if best_bid is not None:
            return float(best_bid)
        if best_ask is not None:
            return float(best_ask)
        return None

    def _best_bid_ask(self, depth: OrderDepth) -> Tuple[Optional[int], Optional[int]]:
        best_bid = max(depth.buy_orders) if depth.buy_orders else None
        best_ask = min(depth.sell_orders) if depth.sell_orders else None
        return best_bid, best_ask

    def _effective_position(self, position: int, orders: List[Order]) -> int:
        return position + sum(order.quantity for order in orders)

    def _buy_capacity(self, product: str, position: int, orders: List[Order]) -> int:
        limit = self.POSITION_LIMITS[product]
        return max(0, limit - self._effective_position(position, orders))

    def _sell_capacity(self, product: str, position: int, orders: List[Order]) -> int:
        limit = self.POSITION_LIMITS[product]
        return max(0, limit + self._effective_position(position, orders))

    def _append_buy(self, orders: List[Order], product: str, price: int, quantity: int, position: int) -> None:
        if quantity <= 0:
            return
        qty = min(quantity, self._buy_capacity(product, position, orders))
        if qty > 0:
            orders.append(Order(product, int(price), int(qty)))

    def _append_sell(self, orders: List[Order], product: str, price: int, quantity: int, position: int) -> None:
        if quantity <= 0:
            return
        qty = min(quantity, self._sell_capacity(product, position, orders))
        if qty > 0:
            orders.append(Order(product, int(price), int(-qty)))
