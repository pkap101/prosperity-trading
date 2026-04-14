from datamodel import OrderDepth, TradingState, Order
from typing import List
import jsonpickle


class Product:
    EMERALDS = "EMERALDS"
    TOMATOES = "TOMATOES"


PARAMS = {
    Product.EMERALDS: {
        "fair_value": 10000,
        "position_limit": 80,
    },
    Product.TOMATOES: {
        "ma_window": 3,        # shortest window had best MAE
        "take_width": 2,       # take if price deviates > 2 from fair
        "make_edge": 4,        # post quotes 4 away from fair value
        "position_limit": 80,
    },
}


class Trader:

    def __init__(self):
        self.tom_price_history: List[float] = []

    def run(self, state: TradingState):

        # Restore state
        trader_obj = {}
        if state.traderData and state.traderData != "":
            trader_obj = jsonpickle.decode(state.traderData)
        self.tom_price_history = trader_obj.get("tom_prices", [])

        result = {}

        if Product.EMERALDS in state.order_depths:
            result[Product.EMERALDS] = self.trade_emeralds(
                state.order_depths[Product.EMERALDS],
                state.position.get(Product.EMERALDS, 0),
            )

        if Product.TOMATOES in state.order_depths:
            result[Product.TOMATOES] = self.trade_tomatoes(
                state.order_depths[Product.TOMATOES],
                state.position.get(Product.TOMATOES, 0),
            )

        # Persist state
        trader_obj["tom_prices"] = self.tom_price_history
        trader_data = jsonpickle.encode(trader_obj)

        return result, 0, trader_data

    # ------------------------------------------------------------------
    # EMERALDS — pure market making at bot quote levels
    # ------------------------------------------------------------------
    def trade_emeralds(self, order_depth: OrderDepth, position: int) -> List[Order]:
        orders = []
        limit = PARAMS[Product.EMERALDS]["position_limit"]
        fair  = PARAMS[Product.EMERALDS]["fair_value"]

        best_ask = min(order_depth.sell_orders.keys())
        best_bid = max(order_depth.buy_orders.keys())

        # Take any ask at or below fair value (special ticks where ask=10000)
        for ask_price in sorted(order_depth.sell_orders.keys()):
            if ask_price <= fair:
                available = -order_depth.sell_orders[ask_price]
                qty = min(available, limit - position)
                if qty > 0:
                    orders.append(Order(Product.EMERALDS, ask_price, qty))
                    position += qty

        # Take any bid at or above fair value (special ticks where bid=10000)
        for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
            if bid_price >= fair:
                available = order_depth.buy_orders[bid_price]
                qty = min(available, limit + position)
                if qty > 0:
                    orders.append(Order(Product.EMERALDS, bid_price, -qty))
                    position -= qty

        # Post resting orders at the bot quote levels to collect the spread
        # Buy at 9992 — bots will hit this when they sell aggressively
        buy_qty = limit - position
        if buy_qty > 0:
            orders.append(Order(Product.EMERALDS, best_bid, buy_qty))

        # Sell at 10008 — bots will hit this when they buy aggressively
        sell_qty = limit + position
        if sell_qty > 0:
            orders.append(Order(Product.EMERALDS, best_ask, -sell_qty))

        return orders

    # ------------------------------------------------------------------
    # TOMATOES — mean reversion around MA(3) fair value
    # ------------------------------------------------------------------
    def trade_tomatoes(self, order_depth: OrderDepth, position: int) -> List[Order]:
        orders = []
        params = PARAMS[Product.TOMATOES]
        limit  = params["position_limit"]

        # Update price history with current mid price
        if order_depth.buy_orders and order_depth.sell_orders:
            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            mid = (best_bid + best_ask) / 2
        else:
            return orders

        self.tom_price_history.append(mid)
        window = params["ma_window"]
        if len(self.tom_price_history) > window * 2:
            # Trim to avoid unbounded growth (traderData size limit)
            self.tom_price_history = self.tom_price_history[-window * 2:]

        if len(self.tom_price_history) < window:
            return orders  # not enough history yet

        fair = sum(self.tom_price_history[-window:]) / window
        take_width = params["take_width"]
        make_edge  = params["make_edge"]

        # Take orders — aggressive fills when price has deviated from fair
        # Price below fair (mean reversion: expect bounce up) → buy
        for ask_price in sorted(order_depth.sell_orders.keys()):
            if ask_price <= fair - take_width:
                available = -order_depth.sell_orders[ask_price]
                qty = min(available, limit - position)
                if qty > 0:
                    orders.append(Order(Product.TOMATOES, ask_price, qty))
                    position += qty

        # Price above fair (mean reversion: expect drop) → sell
        for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
            if bid_price >= fair + take_width:
                available = order_depth.buy_orders[bid_price]
                qty = min(available, limit + position)
                if qty > 0:
                    orders.append(Order(Product.TOMATOES, bid_price, -qty))
                    position -= qty

        # Post resting quotes around fair value to earn spread passively
        buy_qty  = limit - position
        sell_qty = limit + position

        if buy_qty > 0:
            orders.append(Order(Product.TOMATOES, round(fair - make_edge), buy_qty))
        if sell_qty > 0:
            orders.append(Order(Product.TOMATOES, round(fair + make_edge), -sell_qty))

        return orders