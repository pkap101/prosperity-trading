import json
from typing import Dict, List

from datamodel import Order, TradingState


class Trader:
    """
    Product-level hybrid:
    - Pepper Root from v1
    - Ash-Coated Osmium from v3

    The local backtester ignores bid(), so the MAF choice here is only a
    placeholder for actual Round 2 submission logic.
    """

    PRODUCTS = ["INTARIAN_PEPPER_ROOT", "ASH_COATED_OSMIUM"]
    POSITION_LIMIT = 80

    # Pepper Root (ported from v1)
    P_TAKE_BUY_WIDTH = 1.0
    P_DRIFT = 0.001
    P_INTERCEPT_ALPHA = 2.0 / 101.0
    P_WARMUP_END = 1000
    P_AGGRESSIVE_WIDTH = -10
    P_MAKE_BID_OFFSET = 2

    # Osmium (ported from v3)
    OSM_K_SS = 0.1353
    OSM_FAIR_STATIC = 10001
    OSM_TAKE_WIDTH = 2
    OSM_CLEAR_WIDTH = 2
    OSM_VOLUME_LIMIT = 30
    OSM_MAKE_EDGE = 1
    OSM_SKEW_UNIT = 12

    def bid(self) -> int:
        return 2304

    def run(self, state: TradingState):
        try:
            td = json.loads(state.traderData) if state.traderData else {}
            if not isinstance(td, dict):
                td = {}
        except Exception:
            td = {}

        result: Dict[str, List[Order]] = {}

        pepper = "INTARIAN_PEPPER_ROOT"
        if pepper in state.order_depths:
            result[pepper] = self._pepper(
                state.order_depths[pepper],
                state.position.get(pepper, 0),
                state.timestamp,
                td,
            )

        osmium = "ASH_COATED_OSMIUM"
        if osmium in state.order_depths:
            result[osmium] = self._osmium(
                state.order_depths[osmium],
                state.position.get(osmium, 0),
                td,
            )

        return result, 0, json.dumps(td)

    def _pepper(self, od, position: int, timestamp: int, td: dict) -> List[Order]:
        if not od.buy_orders or not od.sell_orders:
            return []

        best_bid = max(od.buy_orders)
        best_ask = min(od.sell_orders)
        orders: List[Order] = []
        buy_alloc = 0
        sell_alloc = 0

        mid = (best_bid + best_ask) / 2.0
        det = mid - self.P_DRIFT * timestamp
        intercept = (
            self.P_INTERCEPT_ALPHA * det + (1 - self.P_INTERCEPT_ALPHA) * td["ip"]
            if "ip" in td
            else det
        )
        td["ip"] = intercept
        fair = intercept + self.P_DRIFT * timestamp

        max_buy = max(self.POSITION_LIMIT - position, 0)
        max_sell = max(self.POSITION_LIMIT + position, 0)
        take_width = self.P_AGGRESSIVE_WIDTH if timestamp <= self.P_WARMUP_END else self.P_TAKE_BUY_WIDTH

        for ask in sorted(od.sell_orders):
            if ask <= fair - take_width:
                ask_vol = -od.sell_orders[ask]
                can_buy = max_buy - buy_alloc
                if can_buy <= 0:
                    break
                qty = min(ask_vol, can_buy)
                if qty > 0:
                    orders.append(Order("INTARIAN_PEPPER_ROOT", ask, qty))
                    buy_alloc += qty
            else:
                break

        make_bid = best_bid + self.P_MAKE_BID_OFFSET
        make_ask = best_ask - 1
        if make_bid < make_ask:
            can_buy = max_buy - buy_alloc
            if can_buy > 0:
                orders.append(Order("INTARIAN_PEPPER_ROOT", make_bid, can_buy))
                buy_alloc += can_buy

            can_sell = max_sell - sell_alloc
            if can_sell > 0:
                orders.append(Order("INTARIAN_PEPPER_ROOT", make_ask, -can_sell))
                sell_alloc += can_sell

        return orders

    def _osmium(self, depth, pos: int, td: dict) -> List[Order]:
        if not depth.buy_orders or not depth.sell_orders:
            return []

        bb = max(depth.buy_orders)
        ba = min(depth.sell_orders)
        bv_tob = depth.buy_orders[bb]
        av_tob = -depth.sell_orders[ba]
        total = bv_tob + av_tob
        micro = (bb * av_tob + ba * bv_tob) / total if total > 0 else (bb + ba) / 2.0

        fair = td.get("_osm_f", micro)
        innovation = micro - fair
        err_ema = td.get("_osm_err", abs(innovation))
        err_ema += self.OSM_K_SS * (abs(innovation) - err_ema)
        td["_osm_err"] = err_ema
        fair += (self.OSM_K_SS / (1.0 + err_ema)) * innovation
        td["_osm_f"] = fair

        static = self.OSM_FAIR_STATIC
        clear_width = self.OSM_CLEAR_WIDTH
        orders: List[Order] = []
        buy_vol = 0
        sell_vol = 0

        skew = round(pos / self.OSM_SKEW_UNIT)
        ask_limit = max(static, fair) - max(0, self.OSM_TAKE_WIDTH + skew)
        bid_limit = min(static, fair) + max(0, self.OSM_TAKE_WIDTH - skew)

        for ask in sorted(depth.sell_orders):
            if ask > ask_limit:
                break
            qty = min(-depth.sell_orders[ask], self.POSITION_LIMIT - pos - buy_vol)
            if qty > 0:
                orders.append(Order("ASH_COATED_OSMIUM", ask, qty))
                buy_vol += qty

        for bid in sorted(depth.buy_orders, reverse=True):
            if bid < bid_limit:
                break
            qty = min(depth.buy_orders[bid], self.POSITION_LIMIT + pos - sell_vol)
            if qty > 0:
                orders.append(Order("ASH_COATED_OSMIUM", bid, -qty))
                sell_vol += qty

        pos_after = pos + buy_vol - sell_vol
        fair_bid = int(round(fair - clear_width))
        fair_ask = int(round(fair + clear_width))
        long_favorable = fair < static
        short_favorable = fair > static

        if pos_after > 0 and not long_favorable:
            clear_qty = min(pos_after, sum(v for p, v in depth.buy_orders.items() if p >= fair_ask))
            sent = min(self.POSITION_LIMIT + pos - sell_vol, clear_qty)
            if sent > 0:
                orders.append(Order("ASH_COATED_OSMIUM", fair_ask, -sent))
                sell_vol += sent
        elif pos_after < 0 and not short_favorable:
            clear_qty = min(-pos_after, sum(-v for p, v in depth.sell_orders.items() if p <= fair_bid))
            sent = min(self.POSITION_LIMIT - pos - buy_vol, clear_qty)
            if sent > 0:
                orders.append(Order("ASH_COATED_OSMIUM", fair_bid, sent))
                buy_vol += sent

        favorable_inventory = (pos > 0 and long_favorable) or (pos < 0 and short_favorable)
        if favorable_inventory:
            bid_edge = ask_edge = max(1, self.OSM_MAKE_EDGE)
        else:
            bid_edge = max(1, self.OSM_MAKE_EDGE + skew)
            ask_edge = max(1, self.OSM_MAKE_EDGE - skew)

        best_ask_above_fair = min((p for p in depth.sell_orders if p > fair + ask_edge - 1), default=None)
        best_bid_below_fair = max((p for p in depth.buy_orders if p < fair - bid_edge + 1), default=None)

        if best_ask_above_fair is not None and best_bid_below_fair is not None:
            if best_ask_above_fair <= fair + ask_edge and pos <= self.OSM_VOLUME_LIMIT:
                best_ask_above_fair = int(round(fair + ask_edge + 1))
            if best_bid_below_fair >= fair - bid_edge and pos >= -self.OSM_VOLUME_LIMIT:
                best_bid_below_fair = int(round(fair - bid_edge - 1))

            buy_qty = self.POSITION_LIMIT - pos - buy_vol
            if buy_qty > 0:
                orders.append(Order("ASH_COATED_OSMIUM", best_bid_below_fair + 1, buy_qty))

            sell_qty = self.POSITION_LIMIT + pos - sell_vol
            if sell_qty > 0:
                orders.append(Order("ASH_COATED_OSMIUM", best_ask_above_fair - 1, -sell_qty))

        return orders
