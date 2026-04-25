"""V14 = V4 PEPPER (best-in-class) + friend's OSMIUM (1,765 live!).

Combine: our PEPPER alpha (7,674 best) + their OSMIUM strategy (1,765 best).
Theoretical max ≈ 9,439.

OSMIUM mechanism (ported verbatim from friend):
- Fair = jump-filtered EMA of VWAP_mid (alpha=0.22, skip on |Δvwap| > 5.5)
- Multi-level sweep: take ALL ask levels < fair, all bid levels > fair
- Make: bid_q = min(best_bid+1, fair-1-skew); ask_q = max(best_ask-1, fair+1-skew)
- Inventory skew on quotes: skew = round(5 * pos / limit)
- SIZE_MAKE = 15, SIZE_MAKE_JUMP = 20
- Suppress make when |pos| >= 80 (full limit)

PEPPER mechanism = our V4 (7,674 best):
- Detrended-mid EMA fair, drift = 0.001
- Aggressive warmup (-10 width, t<=1000)
- Take asks <= fair-1 post-warmup
- Make bid+2 (max size), make ask-1 (max size)
"""
import json
from typing import List, Dict
from datamodel import OrderDepth, TradingState, Order


def vwap_mid(od):
    bb = sum(p*q for p,q in od.buy_orders.items()) / sum(od.buy_orders.values()) if od.buy_orders else None
    aa = sum(p*(-q) for p,q in od.sell_orders.items()) / sum(-q for q in od.sell_orders.values()) if od.sell_orders else None
    if bb is not None and aa is not None: return (bb+aa)/2.0
    return bb if bb is not None else aa


class Trader:
    PRODUCTS = ["INTARIAN_PEPPER_ROOT", "ASH_COATED_OSMIUM"]
    POSITION_LIMIT = 80

    # PEPPER (V4 sacred)
    P_TAKE_BUY_WIDTH = 1.0
    P_DRIFT = 0.001
    P_INTERCEPT_ALPHA = 2.0 / 101.0
    P_WARMUP_END = 1000
    P_AGGRESSIVE_WIDTH = -10
    P_MAKE_BID_OFFSET = 2

    # OSMIUM (from friend)
    O_ALPHA_FAIR = 0.30
    O_JUMP_CLIP = 5.5
    O_TAKE_BUFFER = 0
    O_SOFT_LIMIT = 80
    O_SIZE_MAKE = 15
    O_SIZE_MAKE_JUMP = 20
    O_SKEW_K = 7

    def bid(self):
        return 15

    def run(self, state: TradingState):
        td = {}
        if state.traderData:
            try:
                p = json.loads(state.traderData)
                if isinstance(p, dict): td = p
            except Exception: pass
        if not isinstance(td.get("ip"), (int, float)): td.pop("ip", None)
        if not isinstance(td.get("o_fair"), (int, float)): td.pop("o_fair", None)

        result: Dict[str, List[Order]] = {}

        # ========== PEPPER (V4) ==========
        product = "INTARIAN_PEPPER_ROOT"
        if product in state.order_depths:
            od = state.order_depths[product]
            if od.buy_orders and od.sell_orders:
                best_bid = max(od.buy_orders); best_ask = min(od.sell_orders)
                position = state.position.get(product, 0)
                orders: List[Order] = []
                buy_alloc = sell_alloc = 0

                mid = (best_bid + best_ask) / 2.0
                det = mid - self.P_DRIFT * state.timestamp
                intercept = (self.P_INTERCEPT_ALPHA * det + (1 - self.P_INTERCEPT_ALPHA) * td["ip"]) if "ip" in td else det
                td["ip"] = intercept
                fair = intercept + self.P_DRIFT * state.timestamp

                max_buy = max(self.POSITION_LIMIT - position, 0)
                max_sell = max(self.POSITION_LIMIT + position, 0)
                tw = self.P_AGGRESSIVE_WIDTH if state.timestamp <= self.P_WARMUP_END else self.P_TAKE_BUY_WIDTH

                for ask in sorted(od.sell_orders):
                    if ask <= fair - tw:
                        avol = -od.sell_orders[ask]; can = max_buy - buy_alloc
                        if can <= 0: break
                        q = min(avol, can)
                        if q > 0: orders.append(Order(product, ask, q)); buy_alloc += q
                    else: break

                make_bid = best_bid + self.P_MAKE_BID_OFFSET
                make_ask = best_ask - 1
                if make_bid < make_ask:
                    can = max_buy - buy_alloc
                    if can > 0: orders.append(Order(product, make_bid, can)); buy_alloc += can
                    can = max_sell - sell_alloc
                    if can > 0: orders.append(Order(product, make_ask, -can)); sell_alloc += can

                result[product] = orders

        # ========== OSMIUM (from friend's strategy) ==========
        product = "ASH_COATED_OSMIUM"
        if product in state.order_depths:
            od = state.order_depths[product]
            position = state.position.get(product, 0)
            orders: List[Order] = []
            best_bid = max(od.buy_orders) if od.buy_orders else None
            best_ask = min(od.sell_orders) if od.sell_orders else None
            if best_bid is None and best_ask is None:
                result[product] = orders
            else:
                vwap = vwap_mid(od)
                prev = td.get("o_prev_vwap")
                is_jump = (prev is not None and vwap is not None and abs(vwap - prev) > self.O_JUMP_CLIP)
                if vwap is not None and not is_jump:
                    if "o_fair" in td:
                        td["o_fair"] = self.O_ALPHA_FAIR * vwap + (1 - self.O_ALPHA_FAIR) * td["o_fair"]
                    else:
                        td["o_fair"] = vwap
                td["o_prev_vwap"] = vwap
                fair = round(td.get("o_fair", 10000))

                buy_h = self.POSITION_LIMIT - position
                sell_h = self.POSITION_LIMIT + position

                # Multi-level sweep takes
                for ask_price in sorted(od.sell_orders):
                    if ask_price >= fair - self.O_TAKE_BUFFER or buy_h <= 0:
                        break
                    qty = min(-od.sell_orders[ask_price], buy_h)
                    if qty > 0:
                        orders.append(Order(product, ask_price, qty)); buy_h -= qty
                for bid_price in sorted(od.buy_orders, reverse=True):
                    if bid_price <= fair + self.O_TAKE_BUFFER or sell_h <= 0:
                        break
                    qty = min(od.buy_orders[bid_price], sell_h)
                    if qty > 0:
                        orders.append(Order(product, bid_price, -qty)); sell_h -= qty

                # Make with quote skew
                skew = round(self.O_SKEW_K * position / self.POSITION_LIMIT)
                make_sz = self.O_SIZE_MAKE_JUMP if is_jump else self.O_SIZE_MAKE
                fb = 1 if is_jump else 6
                bid_q = min(best_bid + 1, fair - 1 - skew) if best_bid is not None else fair - fb - skew
                ask_q = max(best_ask - 1, fair + 1 - skew) if best_ask is not None else fair + fb - skew
                if buy_h > 0 and position < self.O_SOFT_LIMIT:
                    orders.append(Order(product, bid_q, min(make_sz, buy_h)))
                if sell_h > 0 and position > -self.O_SOFT_LIMIT:
                    orders.append(Order(product, ask_q, -min(make_sz, sell_h)))

                result[product] = orders

        return result, 0, json.dumps(td)