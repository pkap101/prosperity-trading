# Snapshot: tutorial baseline
# The starter template with no real strategy - kept as a reference point.

from src.datamodel import OrderDepth, TradingState, Order
from typing import List


class Trader:

    def bid(self):
        return 15

    def run(self, state: TradingState):
        print("traderData: " + state.traderData)
        print("Observations: " + str(state.observations))

        result = {}

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []

            acceptable_price = 10  # placeholder

            if len(order_depth.sell_orders) != 0:
                best_ask, best_ask_amount = list(order_depth.sell_orders.items())[0]
                if int(best_ask) < acceptable_price:
                    orders.append(Order(product, best_ask, -best_ask_amount))

            if len(order_depth.buy_orders) != 0:
                best_bid, best_bid_amount = list(order_depth.buy_orders.items())[0]
                if int(best_bid) > acceptable_price:
                    orders.append(Order(product, best_bid, -best_bid_amount))

            result[product] = orders

        return result, 0, ""