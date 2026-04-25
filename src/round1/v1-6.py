from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List, Optional, Tuple
import json
# https://github.com/nikhiljoseph2004/ANAIprosperity/blob/main/round_1/round1.py
class Trader:

    POSITION_LIMITS = {
        "ASH_COATED_OSMIUM": 80,
        "INTARIAN_PEPPER_ROOT": 80,
    }

    PEPPER_TARGET_LONG = 80
    PEPPER_BASE_DAILY_DRIFT = 1000.0
    OSMIUM_FAIR_VALUE = 10000
    OSMIUM_TRADE_CLIP = 20
    OSMIUM_EDGE = 2

    def _load_state(self, raw: str) -> Dict[str, float]:
        default_state = {
            "pepper_last_mid": 12000.0,
            "pepper_slope_per_ts": self.PEPPER_BASE_DAILY_DRIFT / 1_000_000.0,
            "pepper_last_ts": 0.0,
        }
        if not raw:
            return default_state
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                return default_state
            default_state.update(
                {
                    "pepper_last_mid": float(payload.get("pepper_last_mid", default_state["pepper_last_mid"])),
                    "pepper_slope_per_ts": float(payload.get("pepper_slope_per_ts", default_state["pepper_slope_per_ts"])),
                    "pepper_last_ts": float(payload.get("pepper_last_ts", default_state["pepper_last_ts"])),
                }
            )
            return default_state
        except Exception:
            return default_state

    def _best_bid_ask(self, depth: OrderDepth) -> Tuple[Optional[int], Optional[int]]:
        best_bid = max(depth.buy_orders.keys()) if depth.buy_orders else None
        best_ask = min(depth.sell_orders.keys()) if depth.sell_orders else None
        return best_bid, best_ask

    def _mid_price(self, depth: OrderDepth, fallback: float) -> float:
        best_bid, best_ask = self._best_bid_ask(depth)
        if best_bid is not None and best_ask is not None:
            return (best_bid + best_ask) / 2.0
        if best_bid is not None:
            return float(best_bid)
        if best_ask is not None:
            return float(best_ask)
        return fallback

    def _position_after(self, position: int, orders: List[Order]) -> int:
        return position + sum(order.quantity for order in orders)

    def _buy_capacity(self, limit: int, effective_position: int) -> int:
        return max(0, limit - effective_position)

    def _sell_capacity(self, limit: int, effective_position: int) -> int:
        return max(0, limit + effective_position)

    def _append_buy(self, orders: List[Order], product: str, price: int, quantity: int, position: int) -> None:
        if quantity <= 0:
            return
        limit = self.POSITION_LIMITS[product]
        effective_position = self._position_after(position, orders)
        cap = self._buy_capacity(limit, effective_position)
        qty = min(quantity, cap)
        if qty > 0:
            orders.append(Order(product, int(price), int(qty)))

    def _append_sell(self, orders: List[Order], product: str, price: int, quantity: int, position: int) -> None:
        if quantity <= 0:
            return
        limit = self.POSITION_LIMITS[product]
        effective_position = self._position_after(position, orders)
        cap = self._sell_capacity(limit, effective_position)
        qty = min(quantity, cap)
        if qty > 0:
            orders.append(Order(product, int(price), int(-qty)))

    def _trade_pepper(
        self,
        product: str,
        depth: OrderDepth,
        position: int,
        target_long: int,
    ) -> List[Order]:
        orders: List[Order] = []

        asks = sorted(depth.sell_orders.items())
        best_bid, best_ask = self._best_bid_ask(depth)

        # Aggressive buys: take ALL available asks until inventory reaches target.
        # The +1000/day trend makes every buy profitable; speed to max long is key.
        for ask_price, ask_volume in asks:
            remaining = target_long - self._position_after(position, orders)
            if remaining <= 0:
                break
            ask_qty = max(0, -ask_volume)
            self._append_buy(orders, product, ask_price, min(ask_qty, remaining), position)

        # Passive bid to refill if we drift below target (from end-of-day mark etc).
        live_position = self._position_after(position, orders)
        if live_position < target_long and best_bid is not None:
            passive_bid = best_bid + 1
            top_up = min(20, target_long - live_position)
            self._append_buy(orders, product, passive_bid, top_up, position)

        return orders

    def _trade_osmium(self, product: str, depth: OrderDepth, position: int) -> List[Order]:
        orders: List[Order] = []
        best_bid, best_ask = self._best_bid_ask(depth)
        if best_bid is None and best_ask is None:
            return orders

        fair = self.OSMIUM_FAIR_VALUE

        # Adaptive edge: tighten when holding a larger position to unwind faster.
        buy_edge = self.OSMIUM_EDGE
        sell_edge = self.OSMIUM_EDGE
        # Position-adjusted edge: lower the edge on the unwinding side.
        # When long → sell more eagerly. When short → buy more eagerly.
        buy_edge = self.OSMIUM_EDGE
        sell_edge = self.OSMIUM_EDGE
        if position > 25:
            sell_edge = 0
        elif position > 8:
            sell_edge = 1
        if position < -25:
            buy_edge = 0
        elif position < -8:
            buy_edge = 1

        # Lightweight mean-reversion around a near-fixed fair value.
        for ask_px, ask_vol in sorted(depth.sell_orders.items()):
            if ask_px > fair - buy_edge:
                break
            self._append_buy(orders, product, ask_px, min(self.OSMIUM_TRADE_CLIP, max(0, -ask_vol)), position)

        for bid_px, bid_vol in sorted(depth.buy_orders.items(), reverse=True):
            if bid_px < fair + sell_edge:
                break
            self._append_sell(orders, product, bid_px, min(self.OSMIUM_TRADE_CLIP, max(0, bid_vol)), position)

        # Passive market-making: post quotes inside the spread to earn half-spread.
        live_position = self._position_after(position, orders)
        if best_bid is not None and best_ask is not None:
            spread = best_ask - best_bid
            if spread >= 4:
                # Position-skewed pricing: shade quote toward the unwinding side.
                skew = max(-3, min(3, live_position // 12))
                passive_bid = min(best_bid + 1, fair - 1 - skew)
                passive_ask = max(best_ask - 1, fair + 1 - skew)

                # Scale qty: lean larger on the side that moves us toward 0.
                bid_qty = min(20, max(0, 20 - live_position // 4))
                ask_qty = min(20, max(0, 20 + live_position // 4))

                if passive_bid < passive_ask:
                    self._append_buy(orders, product, passive_bid, bid_qty, position)
                    live_position = self._position_after(position, orders)
                    self._append_sell(orders, product, passive_ask, ask_qty, position)

        return orders

    def bid(self):
        return 15
    
    def run(self, state: TradingState):
        """Only method required. It takes all buy and sell orders for all
        symbols as an input, and outputs a list of orders to be sent."""

        state_data = self._load_state(state.traderData)
        result: Dict[str, List[Order]] = {}

        pepper_depth = state.order_depths.get("INTARIAN_PEPPER_ROOT")
        if pepper_depth is not None:
            pepper_position = state.position.get("INTARIAN_PEPPER_ROOT", 0)
            pepper_orders = self._trade_pepper(
                product="INTARIAN_PEPPER_ROOT",
                depth=pepper_depth,
                position=pepper_position,
                target_long=self.PEPPER_TARGET_LONG,
            )
            result["INTARIAN_PEPPER_ROOT"] = pepper_orders

        osmium_depth = state.order_depths.get("ASH_COATED_OSMIUM")
        if osmium_depth is not None:
            osmium_position = state.position.get("ASH_COATED_OSMIUM", 0)
            result["ASH_COATED_OSMIUM"] = self._trade_osmium(
                product="ASH_COATED_OSMIUM",
                depth=osmium_depth,
                position=osmium_position,
            )

        # Ensure output contains all observed products, even if no trade is sent.
        for product in state.order_depths:
            result.setdefault(product, [])

        traderData = json.dumps(state_data)
        conversions = 0
        return result, conversions, traderData