from datamodel import Order, TradingState
import json

IPR = "INTARIAN_PEPPER_ROOT"
ACO = "ASH_COATED_OSMIUM"
LIMITS = {IPR: 80, ACO: 80}

CONFIG = {
    "bot_id": "R2-CAND-02-IPR-RESIDUAL-EXTREME-EXECUTION",
    "inventory_soft": 32,
    "ipr_clip": 6,
    "ipr_extreme_threshold": 2.0,
    "ipr_slope_alpha": 0.05,
    "ipr_warmup": 20,
    "log": True,
    "maf_bid": 0,
    "modes": [
        "ipr_extreme"
    ],
    "role": "ipr_residual_extreme",
    "spread_max": 3
}


class Trader:
    def bid(self):
        return int(CONFIG.get("maf_bid", 0))

    def _load_memory(self, trader_data):
        if not trader_data:
            return {}
        try:
            data = json.loads(trader_data)
            if isinstance(data, dict):
                return data
        except Exception:
            return {}
        return {}

    def _dump_memory(self, memory):
        memory["bot"] = CONFIG["bot_id"]
        try:
            return json.dumps(memory, separators=(",", ":"), sort_keys=True)[:48000]
        except Exception:
            return json.dumps({"bot": CONFIG["bot_id"]}, separators=(",", ":"))

    def _book(self, state, product):
        depth = (getattr(state, "order_depths", {}) or {}).get(product)
        if depth is None:
            return None
        buys = getattr(depth, "buy_orders", {}) or {}
        sells = getattr(depth, "sell_orders", {}) or {}
        if not buys or not sells:
            return None
        best_bid = max(buys)
        best_ask = min(sells)
        bid_vol = max(0, int(buys.get(best_bid, 0)))
        ask_vol = abs(int(sells.get(best_ask, 0)))
        total_bid = sum(max(0, int(v)) for v in buys.values())
        total_ask = sum(abs(int(v)) for v in sells.values())
        return {
            "best_bid": int(best_bid),
            "best_ask": int(best_ask),
            "bid_vol": int(bid_vol),
            "ask_vol": int(ask_vol),
            "total_bid": int(total_bid),
            "total_ask": int(total_ask),
            "mid": (best_bid + best_ask) / 2.0,
            "spread": int(best_ask - best_bid),
        }

    def _position(self, state, product):
        return int((getattr(state, "position", {}) or {}).get(product, 0))

    def _capacities(self, state):
        caps = {}
        for product, limit in LIMITS.items():
            pos = self._position(state, product)
            caps[product] = {"buy": max(0, limit - pos), "sell": max(0, limit + pos)}
        return caps

    def _spread_multiplier(self, book):
        if not CONFIG.get("spread_overlay"):
            max_spread = CONFIG.get("spread_max", 4)
            return 1.0 if book["spread"] <= max_spread else 0.0
        if book["spread"] <= CONFIG.get("spread_normal", 4):
            return 1.0
        if book["spread"] <= CONFIG.get("spread_defensive", 6):
            return CONFIG.get("defensive_size_multiplier", 0.5)
        return 0.0

    def _add_order(self, orders, caps, product, price, qty):
        if qty == 0:
            return 0
        if qty > 0:
            allowed = min(int(qty), int(caps[product]["buy"]))
            if allowed <= 0:
                return 0
            caps[product]["buy"] -= allowed
            orders.setdefault(product, []).append(Order(product, int(price), int(allowed)))
            return allowed
        allowed = min(int(-qty), int(caps[product]["sell"]))
        if allowed <= 0:
            return 0
        caps[product]["sell"] -= allowed
        orders.setdefault(product, []).append(Order(product, int(price), -int(allowed)))
        return -allowed

    def _clip_for_inventory(self, base_clip, position, side):
        soft = int(CONFIG.get("inventory_soft", 40))
        if side > 0 and position > soft:
            return max(1, base_clip // 2)
        if side < 0 and position < -soft:
            return max(1, base_clip // 2)
        return base_clip

    def _trade_ipr(self, state, memory, orders, caps, features, extreme=False):
        book = self._book(state, IPR)
        if book is None:
            features["ipr_status"] = "missing_book"
            return
        ts = int(getattr(state, "timestamp", 0) or 0)
        last_mid = memory.get("ipr_last_mid")
        last_ts = memory.get("ipr_last_ts")
        slope = float(memory.get("ipr_slope", 0.0))
        count = int(memory.get("ipr_count", 0))
        fair = book["mid"]
        if last_mid is not None and last_ts is not None:
            dt = max(1, ts - int(last_ts))
            fair = float(last_mid) + slope * dt
            observed_slope = (book["mid"] - float(last_mid)) / dt
            alpha = float(CONFIG.get("ipr_slope_alpha", 0.05))
            slope = observed_slope if count <= 1 else slope + alpha * (observed_slope - slope)
        count += 1
        memory["ipr_last_mid"] = book["mid"]
        memory["ipr_last_ts"] = ts
        memory["ipr_slope"] = slope
        memory["ipr_count"] = count
        warmup = int(CONFIG.get("ipr_warmup", 20))
        spread_mult = self._spread_multiplier(book)
        threshold = float(CONFIG.get("ipr_extreme_threshold" if extreme else "ipr_threshold", 1.0))
        pos = self._position(state, IPR)
        residual = book["mid"] - fair
        features["ipr"] = {"fair": round(fair, 4), "mid": book["mid"], "residual": round(residual, 4), "spread": book["spread"], "warm": count >= warmup}
        if count < warmup or spread_mult <= 0:
            return
        clip = int(CONFIG.get("ipr_clip", 8) * spread_mult)
        if clip <= 0:
            return
        buy_edge = fair - book["best_ask"]
        sell_edge = book["best_bid"] - fair
        if buy_edge >= threshold:
            qty = min(book["ask_vol"], self._clip_for_inventory(clip, pos, 1))
            self._add_order(orders, caps, IPR, book["best_ask"], qty)
        if sell_edge >= threshold:
            qty = min(book["bid_vol"], self._clip_for_inventory(clip, pos, -1))
            self._add_order(orders, caps, IPR, book["best_bid"], -qty)

    def _trade_aco_reversal(self, state, memory, orders, caps, features):
        book = self._book(state, ACO)
        if book is None:
            features["aco_reversal_status"] = "missing_book"
            return
        last_mid = memory.get("aco_last_mid")
        memory["aco_last_mid"] = book["mid"]
        if last_mid is None:
            features["aco_reversal"] = {"status": "warming", "mid": book["mid"]}
            return
        delta = book["mid"] - float(last_mid)
        coeff = float(CONFIG.get("aco_reversal_coeff", 0.5))
        fair = book["mid"] - coeff * delta
        features["aco_reversal"] = {"fair": round(fair, 4), "mid": book["mid"], "delta": round(delta, 4), "spread": book["spread"]}
        spread_mult = self._spread_multiplier(book)
        if spread_mult <= 0:
            return
        threshold = float(CONFIG.get("aco_edge", 1.0))
        clip = int(CONFIG.get("aco_clip", 8) * spread_mult)
        pos = self._position(state, ACO)
        if fair - book["best_ask"] >= threshold:
            qty = min(book["ask_vol"], self._clip_for_inventory(clip, pos, 1))
            self._add_order(orders, caps, ACO, book["best_ask"], qty)
        if book["best_bid"] - fair >= threshold:
            qty = min(book["bid_vol"], self._clip_for_inventory(clip, pos, -1))
            self._add_order(orders, caps, ACO, book["best_bid"], -qty)

    def _trade_aco_pressure(self, state, memory, orders, caps, features, kind):
        book = self._book(state, ACO)
        if book is None:
            features["aco_pressure_status"] = "missing_book"
            return
        top_total = book["bid_vol"] + book["ask_vol"]
        full_total = book["total_bid"] + book["total_ask"]
        if top_total <= 0 or full_total <= 0:
            features["aco_pressure_status"] = "empty_depth"
            return
        mid = book["mid"]
        if kind == "microprice":
            fair = (book["best_ask"] * book["bid_vol"] + book["best_bid"] * book["ask_vol"]) / top_total
            signal = fair - mid
            threshold = float(CONFIG.get("micro_threshold", 0.75))
        elif kind == "full_book":
            signal = (book["total_bid"] - book["total_ask"]) / full_total
            fair = mid + float(CONFIG.get("full_book_coeff", 2.0)) * signal
            threshold = float(CONFIG.get("full_book_threshold", 0.20))
        else:
            signal = (book["bid_vol"] - book["ask_vol"]) / top_total
            fair = mid + float(CONFIG.get("imbalance_coeff", 2.0)) * signal
            threshold = float(CONFIG.get("imbalance_threshold", 0.15))
        features["aco_" + kind] = {"fair": round(fair, 4), "mid": mid, "signal": round(signal, 4), "spread": book["spread"]}
        if abs(signal) < threshold:
            return
        spread_mult = self._spread_multiplier(book)
        if spread_mult <= 0:
            return
        clip = int(CONFIG.get("aco_clip", 8) * spread_mult)
        pos = self._position(state, ACO)
        edge = float(CONFIG.get("aco_edge", 1.0))
        buy_edge = fair - book["best_ask"]
        sell_edge = book["best_bid"] - fair
        if buy_edge >= edge or signal > threshold:
            price = book["best_ask"] if buy_edge >= edge else min(book["best_ask"], book["best_bid"] + 1)
            qty = min(book["ask_vol"] if price >= book["best_ask"] else clip, self._clip_for_inventory(clip, pos, 1))
            self._add_order(orders, caps, ACO, price, qty)
        if sell_edge >= edge or signal < -threshold:
            price = book["best_bid"] if sell_edge >= edge else max(book["best_bid"], book["best_ask"] - 1)
            qty = min(book["bid_vol"] if price <= book["best_bid"] else clip, self._clip_for_inventory(clip, pos, -1))
            self._add_order(orders, caps, ACO, price, -qty)

    def _log(self, state, features, orders):
        if not CONFIG.get("log", True):
            return
        payload = {
            "tag": "R2_BOT_LOG",
            "bot": CONFIG["bot_id"],
            "role": CONFIG.get("role", "strategy"),
            "timestamp": getattr(state, "timestamp", None),
            "positions": getattr(state, "position", {}) or {},
            "features": features,
            "order_counts": {p: len(v) for p, v in orders.items()},
            "maf_bid": int(CONFIG.get("maf_bid", 0)),
        }
        try:
            print(json.dumps(payload, separators=(",", ":"), sort_keys=True))
        except Exception:
            print("R2_BOT_LOG_ERROR " + CONFIG["bot_id"])

    def run(self, state: TradingState):
        memory = self._load_memory(getattr(state, "traderData", ""))
        orders = {}
        caps = self._capacities(state)
        features = {}
        modes = CONFIG.get("modes", [])
        if "ipr_drift" in modes:
            self._trade_ipr(state, memory, orders, caps, features, extreme=False)
        if "ipr_extreme" in modes:
            self._trade_ipr(state, memory, orders, caps, features, extreme=True)
        if "aco_reversal" in modes:
            self._trade_aco_reversal(state, memory, orders, caps, features)
        if "aco_imbalance" in modes:
            self._trade_aco_pressure(state, memory, orders, caps, features, "imbalance")
        if "aco_microprice" in modes:
            self._trade_aco_pressure(state, memory, orders, caps, features, "microprice")
        if "aco_full_book" in modes:
            self._trade_aco_pressure(state, memory, orders, caps, features, "full_book")
        if CONFIG.get("no_trade", False):
            orders = {p: [] for p in (getattr(state, "order_depths", {}) or {}).keys()}
        self._log(state, features, orders)
        return orders, 0, self._dump_memory(memory)