from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:

    def run(self, state: TradingState):

        result = {}
        data = json.loads(state.traderData) if state.traderData else {}

        # -------------------------
        # HYDROGEL_PACK
        # -------------------------

        hydrogel = "HYDROGEL_PACK"

        if hydrogel in state.order_depths:
            order_depth: OrderDepth = state.order_depths[hydrogel]
            position = state.position.get(hydrogel, 0)

            result[hydrogel] = self.trade_hydrogel(
                product=hydrogel,
                order_depth=order_depth,
                position=position,
                data=data
            )
        else:
            result[hydrogel] = []

        # -------------------------
        # VELVETFRUIT_EXTRACT
        # -------------------------

        velvetfruit = "VELVETFRUIT_EXTRACT"

        if velvetfruit in state.order_depths:
            order_depth: OrderDepth = state.order_depths[velvetfruit]
            position = state.position.get(velvetfruit, 0)

            result[velvetfruit] = self.trade_velvetfruit(
                product=velvetfruit,
                order_depth=order_depth,
                position=position,
                data=data,
                timestamp=state.timestamp
            )
        else:
            result[velvetfruit] = []

        traderData = json.dumps(data)
        conversions = 0

        return result, conversions, traderData

    def trade_hydrogel(
        self,
        product: str,
        order_depth: OrderDepth,
        position: int,
        data: dict
    ) -> List[Order]:

        orders: List[Order] = []

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return orders

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        mid = (best_bid + best_ask) / 2

        # Parameters
        LIMIT = 200
        BASE_FAIR = 9990

        ALPHA = 0.015
        ANCHOR_WEIGHT = 0.02

        EDGE = 6
        ORDER_SIZE = 16
        INVENTORY_SKEW = 0.03

        # Fair value
        if "hydrogel_fair" not in data:
            data["hydrogel_fair"] = BASE_FAIR
        else:
            data["hydrogel_fair"] = (
                ALPHA * mid
                + (1 - ALPHA) * data["hydrogel_fair"]
            )

        fair = data["hydrogel_fair"]

        # Weak pull to long-run centre
        fair = (1 - ANCHOR_WEIGHT) * fair + ANCHOR_WEIGHT * BASE_FAIR
        data["hydrogel_fair"] = fair

        buy_room = LIMIT - position
        sell_room = LIMIT + position

        # Inventory skew
        adjusted_fair = fair - INVENTORY_SKEW * position

        # Passive market-making quotes
        bid_price = int(round(adjusted_fair - EDGE))
        ask_price = int(round(adjusted_fair + EDGE))

        # Avoid crossing too much
        bid_price = min(bid_price, best_bid + 1)
        ask_price = max(ask_price, best_ask - 1)

        if buy_room > 0:
            buy_qty = min(ORDER_SIZE, buy_room)
            orders.append(Order(product, bid_price, buy_qty))

        if sell_room > 0:
            sell_qty = min(ORDER_SIZE, sell_room)
            orders.append(Order(product, ask_price, -sell_qty))

        return orders

    def trade_velvetfruit(
        self,
        product: str,
        order_depth: OrderDepth,
        position: int,
        data: dict,
        timestamp: int
    ) -> List[Order]:

        orders: List[Order] = []

        if not order_depth.buy_orders or not order_depth.sell_orders:
            return orders

        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = -order_depth.sell_orders[best_ask]

        mid = (best_bid + best_ask) / 2

        LIMIT = 200

        BASE_FAIR = 5250
        ALPHA = 0.002

        PASSIVE_EDGE = 4
        PASSIVE_SIZE = 15

        TAKE_EDGE = 8
        TAKE_SIZE = 15

        INVENTORY_SKEW = 0.08
        MOMENTUM_SKEW = 0.1

        MOMENTUM_EMA_ALPHA = 0.20

        # -------------------------
        # Fair value
        # -------------------------

        if "fair" not in data:
            data["fair"] = BASE_FAIR

        fair = ALPHA * mid + (1 - ALPHA) * data["fair"]
        data["fair"] = fair

        # -------------------------
        # Momentum
        # -------------------------

        if "last_mid" not in data:
            data["last_mid"] = mid

        momentum = mid - data["last_mid"]
        data["last_mid"] = mid

        # -------------------------
        # Historical value: momentum_ema
        # -------------------------

        if "momentum_ema" not in data:
            data["momentum_ema"] = momentum
        else:
            data["momentum_ema"] = (
                MOMENTUM_EMA_ALPHA * momentum
                + (1 - MOMENTUM_EMA_ALPHA) * data["momentum_ema"]
            )

        momentum_ema = data["momentum_ema"]

        # Blend current momentum with smoothed historical momentum
        momentum_signal = 0.5 * momentum + 0.5 * momentum_ema

        # Warmup: update fair/momentum but do not trade yet
        WARMUP_TIME = 5000

        if timestamp < WARMUP_TIME:
            return orders

        buy_room = LIMIT - position
        sell_room = LIMIT + position

        adjusted_fair = (
            fair
            - INVENTORY_SKEW * position
            + MOMENTUM_SKEW * momentum_signal
        )

        # -------------------------
        # Passive market-making quotes
        # -------------------------

        bid_price = int(round(adjusted_fair - PASSIVE_EDGE))
        ask_price = int(round(adjusted_fair + PASSIVE_EDGE))

        # Do not cross the spread with passive orders
        bid_price = min(bid_price, best_ask - 1)
        ask_price = max(ask_price, best_bid + 1)

        if buy_room > 0:
            buy_qty = min(PASSIVE_SIZE, buy_room)
            orders.append(Order(product, bid_price, buy_qty))

        if sell_room > 0:
            sell_qty = min(PASSIVE_SIZE, sell_room)
            orders.append(Order(product, ask_price, -sell_qty))

        # -------------------------
        # Small aggressive fills
        # -------------------------

        if best_ask < adjusted_fair - TAKE_EDGE and buy_room > 0:
            qty = min(TAKE_SIZE, best_ask_volume, buy_room)
            if qty > 0:
                orders.append(Order(product, best_ask, qty))

        if best_bid > adjusted_fair + TAKE_EDGE and sell_room > 0:
            qty = min(TAKE_SIZE, best_bid_volume, sell_room)
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))

        return orders