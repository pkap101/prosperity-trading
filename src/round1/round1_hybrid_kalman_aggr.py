
from __future__ import annotations

from datamodel import Order, OrderDepth, TradingState
import json
from typing import Dict, List, Optional, Tuple

PEPPER = "INTARIAN_PEPPER_ROOT"
OSMIUM = "ASH_COATED_OSMIUM"
LIMIT = 80


class Book:
    def __init__(self, depth: Optional[OrderDepth]) -> None:
        self.valid = False
        self.buy_levels: List[Tuple[int, int]] = []
        self.sell_levels: List[Tuple[int, int]] = []
        self.best_bid = self.best_ask = 0
        self.best_bid_vol = self.best_ask_vol = 0
        self.mid = self.micro = self.spread = self.imbalance = 0.0
        if depth is None:
            return
        self.buy_levels = sorted(((int(p), int(v)) for p, v in depth.buy_orders.items()), key=lambda x: x[0], reverse=True)
        self.sell_levels = sorted(((int(p), abs(int(v))) for p, v in depth.sell_orders.items()), key=lambda x: x[0])
        if not self.buy_levels or not self.sell_levels:
            return
        self.best_bid, self.best_bid_vol = self.buy_levels[0]
        self.best_ask, self.best_ask_vol = self.sell_levels[0]
        if self.best_bid >= self.best_ask:
            return
        self.mid = (self.best_bid + self.best_ask) / 2.0
        self.spread = float(self.best_ask - self.best_bid)
        total = self.best_bid_vol + self.best_ask_vol
        if total > 0:
            self.micro = (self.best_ask * self.best_bid_vol + self.best_bid * self.best_ask_vol) / total
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


class Trader:
    LIMITS = {PEPPER: LIMIT, OSMIUM: LIMIT}

    PEP_TARGET = 80
    PEP_DRIFT = 0.100188
    PEP_CALIB_TICKS = 10
    PEP_ENTRY_TAKE = 7
    PEP_ENTRY_TIMEOUT = 200
    PEP_BID_FLOOR = -6
    PEP_BID_CEIL = 5

    OSM_STATIC = 10000.0
    OSM_LATENT_VAR = 0.141
    OSM_OBS_VAR = 6.656
    OSM_ANCHOR_WEIGHT = 0.60
    OSM_INV_SKEW = 0.09
    OSM_INV_CURVE = 0.4
    OSM_FRONT_SIZE = 20
    OSM_BACK_SIZE = 0
    OSM_JOIN_EDGE = 2.0
    OSM_TAKE_1 = 1.5
    OSM_TAKE_2 = 3.5
    OSM_TAKE_3 = 5.5
    OSM_SIZE_1 = 6
    OSM_SIZE_2 = 10
    OSM_SIZE_3 = 14
    OSM_CLEAR_WIDTH = 2.0
    OSM_MIN_QUOTE_EDGE = 1.35
    OSM_BASE_QUOTE_EDGE = 1.50
    OSM_SOFT_LIMIT = 70
    OSM_IMB_WEIGHT = 0.0
    OSM_MICRO_WEIGHT = 0.10
    OSM_STABLE_WEIGHT = 0.00
    OSM_WALL_BLEND = 0.0
    OSM_USE_TOXIC = False
    OSM_USE_CLEAR = True

    def run(self, state: TradingState):
        td = self._load_state(state.traderData)
        result: Dict[str, List[Order]] = {product: [] for product in state.order_depths}
        if PEPPER in state.order_depths:
            result[PEPPER] = self._trade_pepper(state.order_depths[PEPPER], state.position.get(PEPPER, 0), state.timestamp, td)
        if OSMIUM in state.order_depths:
            result[OSMIUM] = self._trade_osmium(state.order_depths[OSMIUM], state.position.get(OSMIUM, 0), td)
        return result, 0, json.dumps(td, separators=(",", ":"))

    def _load_state(self, raw: str) -> Dict:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _trade_pepper(self, depth: OrderDepth, position: int, timestamp: int, td: Dict) -> List[Order]:
        book = Book(depth)
        if not book.valid:
            return []
        orders: List[Order] = []
        tick = timestamp // 100
        samples = td.get('pep_samples', [])
        if tick < self.PEP_CALIB_TICKS:
            samples.append(book.mid - self.PEP_DRIFT * tick)
            td['pep_samples'] = samples[-self.PEP_CALIB_TICKS:]
        intercept = sum(samples) / len(samples) if samples else book.mid
        fair = intercept + self.PEP_DRIFT * tick
        need = self.PEP_TARGET - position
        if need <= 0:
            return []
        to_buy = min(need, LIMIT - position)
        bought = 0
        selective = tick < self.PEP_ENTRY_TIMEOUT
        if selective:
            for ask, vol in book.sell_levels:
                if bought >= to_buy:
                    break
                if ask <= fair + self.PEP_ENTRY_TAKE:
                    qty = min(vol, to_buy - bought)
                    if qty > 0:
                        orders.append(Order(PEPPER, ask, qty))
                        bought += qty
            remaining = to_buy - bought
            if remaining > 0:
                competing = book.best_bid
                offset = competing + 1 - int(round(fair))
                offset = max(self.PEP_BID_FLOOR, min(self.PEP_BID_CEIL, offset))
                bid_price = int(round(fair)) + offset
                orders.append(Order(PEPPER, bid_price, remaining))
        else:
            for ask, vol in book.sell_levels:
                if bought >= to_buy:
                    break
                qty = min(vol, to_buy - bought)
                if qty > 0:
                    orders.append(Order(PEPPER, ask, qty))
                    bought += qty
        return orders

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
        return (1.0 - self.OSM_WALL_BLEND) * popular_mid + self.OSM_WALL_BLEND * wall_mid

    def _kalman_fair(self, book: Book, td: Dict) -> float:
        obs = book.micro
        kf = td.get('osm_kf')
        if not isinstance(kf, dict):
            kf = {'fair': obs, 'var': self.OSM_OBS_VAR}
        else:
            pred_var = float(kf['var']) + self.OSM_LATENT_VAR
            K = pred_var / (pred_var + self.OSM_OBS_VAR)
            kf['fair'] = float(kf['fair']) + K * (obs - float(kf['fair']))
            kf['var'] = (1.0 - K) * pred_var
        td['osm_kf'] = kf
        return float(kf['fair'])

    def _osmium_fair(self, book: Book, td: Dict) -> float:
        kfair = self._kalman_fair(book, td)
        stable_mid = self._stable_mid(book)
        fair = self.OSM_ANCHOR_WEIGHT * self.OSM_STATIC
        fair += self.OSM_STABLE_WEIGHT * stable_mid
        fair += (1.0 - self.OSM_ANCHOR_WEIGHT - self.OSM_STABLE_WEIGHT) * kfair
        fair += self.OSM_MICRO_WEIGHT * (book.micro - book.mid)
        fair += self.OSM_IMB_WEIGHT * book.imbalance
        return fair

    def _reservation(self, fair: float, pos: int) -> float:
        ratio = pos / LIMIT
        return fair - self.OSM_INV_SKEW * pos - self.OSM_INV_CURVE * (ratio ** 3)

    def _trade_osmium(self, depth: OrderDepth, position: int, td: Dict) -> List[Order]:
        book = Book(depth)
        if not book.valid:
            return []
        mgr = Manager(OSMIUM, position, LIMIT)
        fair = self._osmium_fair(book, td)
        reservation = self._reservation(fair, mgr.projected())

        bid_toxic = ask_toxic = False
        if self.OSM_USE_TOXIC:
            bid_toxic = book.imbalance < -0.20 and book.micro < book.mid
            ask_toxic = book.imbalance > 0.20 and book.micro > book.mid
        buy_edge_needed = 1.8 if bid_toxic else 1.1
        sell_edge_needed = 1.8 if ask_toxic else 1.1

        buy_edge = reservation - book.best_ask
        take_buy = 0
        for edge_thr, clip in [(self.OSM_TAKE_1, self.OSM_SIZE_1), (self.OSM_TAKE_2, self.OSM_SIZE_2), (self.OSM_TAKE_3, self.OSM_SIZE_3)]:
            if buy_edge >= max(edge_thr, buy_edge_needed):
                take_buy = clip
        if take_buy > 0:
            pos = mgr.projected()
            if pos >= self.OSM_SOFT_LIMIT:
                take_buy = max(0, take_buy - 4)
            mgr.buy(book.best_ask, min(book.best_ask_vol, take_buy))

        sell_edge = book.best_bid - reservation
        take_sell = 0
        for edge_thr, clip in [(self.OSM_TAKE_1, self.OSM_SIZE_1), (self.OSM_TAKE_2, self.OSM_SIZE_2), (self.OSM_TAKE_3, self.OSM_SIZE_3)]:
            if sell_edge >= max(edge_thr, sell_edge_needed):
                take_sell = clip
        if take_sell > 0:
            pos = mgr.projected()
            if pos <= -self.OSM_SOFT_LIMIT:
                take_sell = max(0, take_sell - 4)
            mgr.sell(book.best_bid, min(book.best_bid_vol, take_sell))

        if self.OSM_USE_CLEAR:
            pos_after = mgr.projected()
            clear_bid = int(round(fair - self.OSM_CLEAR_WIDTH))
            clear_ask = int(round(fair + self.OSM_CLEAR_WIDTH))
            if pos_after > 0:
                clear_qty = sum(v for p, v in depth.buy_orders.items() if p >= clear_ask)
                clear_qty = min(clear_qty, pos_after, mgr.sell_cap)
                if clear_qty > 0:
                    mgr.sell(clear_ask, clear_qty)
            elif pos_after < 0:
                clear_qty = sum(abs(v) for p, v in depth.sell_orders.items() if p <= clear_bid)
                clear_qty = min(clear_qty, -pos_after, mgr.buy_cap)
                if clear_qty > 0:
                    mgr.buy(clear_bid, clear_qty)

        pos = mgr.projected()
        reservation = self._reservation(fair, pos)
        base_edge = self.OSM_BASE_QUOTE_EDGE
        buy_qe = base_edge
        sell_qe = base_edge
        if book.spread <= 14:
            buy_qe -= 0.4; sell_qe -= 0.4
        elif book.spread >= 18:
            buy_qe += 0.4; sell_qe += 0.4
        if pos >= self.OSM_SOFT_LIMIT:
            buy_qe += 1.0; sell_qe -= 0.8
        elif pos <= -self.OSM_SOFT_LIMIT:
            buy_qe -= 0.8; sell_qe += 1.0
        buy_qe = max(self.OSM_MIN_QUOTE_EDGE, buy_qe)
        sell_qe = max(self.OSM_MIN_QUOTE_EDGE, sell_qe)

        front_buy = int(round(reservation - buy_qe))
        front_sell = int(round(reservation + sell_qe))
        for price, _ in book.buy_levels[:2]:
            if reservation - price >= buy_qe:
                front_buy = price if reservation - price <= self.OSM_JOIN_EDGE else price + 1
                break
        for price, _ in book.sell_levels[:2]:
            if price - reservation >= sell_qe:
                front_sell = price if price - reservation <= self.OSM_JOIN_EDGE else price - 1
                break
        front_buy = min(front_buy, book.best_ask - 1)
        front_sell = max(front_sell, book.best_bid + 1)
        back_buy = min(front_buy - 2, book.best_ask - 1)
        back_sell = max(front_sell + 2, book.best_bid + 1)

        allow_bid = not (bid_toxic and pos > 8) and pos < self.OSM_SOFT_LIMIT + 6
        allow_ask = not (ask_toxic and pos < -8) and pos > -(self.OSM_SOFT_LIMIT + 6)
        if allow_bid and front_buy > 0 and front_buy < book.best_ask:
            mgr.buy(front_buy, self.OSM_FRONT_SIZE)
            if self.OSM_BACK_SIZE > 0 and back_buy > 0 and back_buy < book.best_ask:
                mgr.buy(back_buy, self.OSM_BACK_SIZE)
        if allow_ask and front_sell > book.best_bid:
            mgr.sell(front_sell, self.OSM_FRONT_SIZE)
            if self.OSM_BACK_SIZE > 0 and back_sell > book.best_bid:
                mgr.sell(back_sell, self.OSM_BACK_SIZE)

        return mgr.orders
