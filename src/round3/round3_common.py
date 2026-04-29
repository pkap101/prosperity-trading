import copy
import json
import math
from typing import Any, Dict, List, Tuple

from datamodel import (
    Listing,
    Observation,
    Order,
    OrderDepth,
    ProsperityEncoder,
    Symbol,
    Trade,
    TradingState,
)


class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(
        self,
        state: TradingState,
        orders: Dict[Symbol, List[Order]],
        conversions: int,
        trader_data: str,
    ) -> None:
        base_length = len(
            self.to_json(
                [
                    self.compress_state(state, ""),
                    self.compress_orders(orders),
                    conversions,
                    "",
                    "",
                ]
            )
        )
        max_item_length = max(0, (self.max_log_length - base_length) // 3)

        print(
            self.to_json(
                [
                    self.compress_state(state, self.truncate(state.traderData, max_item_length)),
                    self.compress_orders(orders),
                    conversions,
                    self.truncate(trader_data, max_item_length),
                    self.truncate(self.logs, max_item_length),
                ]
            )
        )
        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> List[Any]:
        return [
            state.timestamp,
            trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: Dict[Symbol, Listing]) -> List[List[Any]]:
        return [[listing.symbol, listing.product, listing.denomination] for listing in listings.values()]

    def compress_order_depths(self, order_depths: Dict[Symbol, OrderDepth]) -> Dict[Symbol, List[Any]]:
        return {symbol: [depth.buy_orders, depth.sell_orders] for symbol, depth in order_depths.items()}

    def compress_trades(self, trades: Dict[Symbol, List[Trade]]) -> List[List[Any]]:
        compressed: List[List[Any]] = []
        for arr in trades.values():
            for trade in arr:
                compressed.append(
                    [trade.symbol, trade.price, trade.quantity, trade.buyer, trade.seller, trade.timestamp]
                )
        return compressed

    def compress_observations(self, observations: Observation) -> List[Any]:
        return [observations.plainValueObservations, {}]

    def compress_orders(self, orders: Dict[Symbol, List[Order]]) -> List[List[Any]]:
        compressed: List[List[Any]] = []
        for arr in orders.values():
            for order in arr:
                compressed.append([order.symbol, order.price, order.quantity])
        return compressed

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        if len(value) <= max_length:
            return value
        return value[: max(0, max_length - 3)] + "..."


logger = Logger()

HYDRO = "HYDROGEL_PACK"
VELVET = "VELVETFRUIT_EXTRACT"
ALL_VOUCHERS = [
    "VEV_4000",
    "VEV_4500",
    "VEV_5000",
    "VEV_5100",
    "VEV_5200",
    "VEV_5300",
    "VEV_5400",
    "VEV_5500",
    "VEV_6000",
    "VEV_6500",
]
ACTIVE_VOUCHERS = ["VEV_4000", "VEV_5300", "VEV_5400", "VEV_5500", "VEV_6000", "VEV_6500"]
POSITION_LIMITS = {
    HYDRO: 200,
    VELVET: 200,
    **{product: 300 for product in ALL_VOUCHERS},
}

STATIC_SMILE_LAST_YEAR_AVG = (
    0.1911174674723973,
    -0.0017554688314080687,
    0.15101018251088908,
)
STATIC_SMILE_DART = (0.8, -0.15, 0.18)

BASE_CONFIG: Dict[str, Any] = {
    "name": "baseline_blended",
    "trade_underlyings": True,
    "trade_vouchers": True,
    "all_vouchers": ALL_VOUCHERS,
    "traded_vouchers": ["VEV_4000", "VEV_5500", "VEV_6000", "VEV_6500"],
    "round3_start_tte_days": 5.0,
    "timestamp_units_per_day": 1_000_000.0,
    "min_time_value_for_iv": 1.0,
    "iv_ema_alpha": 0.08,
    "min_fit_points": 3,
    "anchor_weights": {"local": 0.65, "ema": 0.35, "static": 0.0},
    "static_smile_coeffs": None,
    "delta_one_cfg": {
        HYDRO: {
            "fair_mix_micro": 0.7,
            "signal_weight": 1.2,
            "inventory_skew": 0.03,
            "take_width": 4.0,
            "make_edge": 4.0,
            "max_quote": 50,
        },
        VELVET: {
            "fair_mix_micro": 0.7,
            "signal_weight": 0.9,
            "inventory_skew": 0.02,
            "take_width": 2.0,
            "make_edge": 1.5,
            "max_quote": 60,
        },
    },
    "voucher_cfg": {
        "VEV_4000": {
            "max_abs_pos": 60,
            "take_width": 8.0,
            "quote_edge": 3.0,
            "inventory_skew": 0.08,
            "side_mode": "both",
            "quote_size": 20,
            "clear_width": 0.25,
        },
        "VEV_4500": {
            "max_abs_pos": 40,
            "take_width": 3.5,
            "quote_edge": 2.0,
            "inventory_skew": 0.06,
            "side_mode": "both",
            "quote_size": 20,
            "clear_width": 0.25,
        },
        "VEV_5000": {
            "max_abs_pos": 40,
            "take_width": 3.0,
            "quote_edge": 1.5,
            "inventory_skew": 0.06,
            "side_mode": "both",
            "quote_size": 20,
            "clear_width": 0.25,
        },
        "VEV_5100": {
            "max_abs_pos": 40,
            "take_width": 2.5,
            "quote_edge": 1.5,
            "inventory_skew": 0.05,
            "side_mode": "both",
            "quote_size": 20,
            "clear_width": 0.25,
        },
        "VEV_5200": {
            "max_abs_pos": 40,
            "take_width": 2.5,
            "quote_edge": 1.5,
            "inventory_skew": 0.05,
            "side_mode": "both",
            "quote_size": 20,
            "clear_width": 0.25,
        },
        "VEV_5300": {
            "max_abs_pos": 80,
            "take_width": 2.0,
            "quote_edge": 1.0,
            "inventory_skew": 0.05,
            "side_mode": "both",
            "quote_size": 30,
            "clear_width": 0.25,
        },
        "VEV_5400": {
            "max_abs_pos": 80,
            "take_width": 2.0,
            "quote_edge": 1.0,
            "inventory_skew": 0.05,
            "side_mode": "both",
            "quote_size": 30,
            "clear_width": 0.25,
        },
        "VEV_5500": {
            "max_abs_pos": 90,
            "take_width": 2.0,
            "quote_edge": 1.0,
            "inventory_skew": 0.05,
            "side_mode": "both",
            "quote_size": 30,
            "clear_width": 0.25,
        },
        "VEV_6000": {
            "max_abs_pos": 120,
            "take_width": 1.0,
            "quote_edge": 0.5,
            "inventory_skew": 0.03,
            "side_mode": "bid",
            "quote_size": 40,
            "clear_width": 0.25,
        },
        "VEV_6500": {
            "max_abs_pos": 120,
            "take_width": 1.0,
            "quote_edge": 0.5,
            "inventory_skew": 0.03,
            "side_mode": "bid",
            "quote_size": 40,
            "clear_width": 0.25,
        },
    },
    "spread_pairs": [],
    "delta_hedge": {
        "enabled": True,
        "trigger": 45.0,
        "ratio": 0.5,
        "cap": 120,
    },
}


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = copy.deepcopy(value)
    return base


class ConfigurableRound3Trader:
    CONFIG: Dict[str, Any] = BASE_CONFIG

    def __init__(self) -> None:
        self.config = deep_merge(copy.deepcopy(BASE_CONFIG), getattr(self, "CONFIG", {}))

    def run(self, state: TradingState):
        memory = self._load_memory(state.traderData)
        orders: Dict[str, List[Order]] = {product: [] for product in state.order_depths.keys()}

        hydro_fair = None
        velvet_fair = None

        if self.config["trade_underlyings"] and HYDRO in state.order_depths:
            hydro_orders, hydro_fair = self._trade_underlying(state, HYDRO)
            orders[HYDRO].extend(hydro_orders)

        if (self.config["trade_underlyings"] or self.config["trade_vouchers"]) and VELVET in state.order_depths:
            if self.config["trade_underlyings"]:
                velvet_orders, velvet_fair = self._trade_underlying(state, VELVET)
                orders[VELVET].extend(velvet_orders)
            elif state.order_depths[VELVET].buy_orders and state.order_depths[VELVET].sell_orders:
                velvet_fair = self._book_fair(state.order_depths[VELVET])

        voucher_context = None
        if self.config["trade_vouchers"] and VELVET in state.order_depths:
            voucher_context = self._build_voucher_context(state, memory)
            if voucher_context is not None:
                voucher_orders = self._trade_vouchers(state, voucher_context)
                for product, product_orders in voucher_orders.items():
                    orders.setdefault(product, []).extend(product_orders)

                hedge_order = self._coarse_delta_hedge(state, orders, voucher_context)
                if hedge_order is not None:
                    orders.setdefault(VELVET, []).append(hedge_order)

        self._log_snapshot(state, hydro_fair, velvet_fair, voucher_context)

        trader_data = json.dumps(memory, separators=(",", ":"))
        logger.flush(state, orders, 0, trader_data)
        return orders, 0, trader_data

    def _load_memory(self, trader_data: str) -> Dict[str, Any]:
        try:
            memory = json.loads(trader_data) if trader_data else {}
            if not isinstance(memory, dict):
                memory = {}
        except Exception:
            memory = {}
        memory.setdefault("iv_ema", {})
        return memory

    def _tracked_voucher_products(self) -> List[str]:
        tracked = list(self.config["traded_vouchers"])
        for pair in self.config.get("spread_pairs", []):
            if pair["long"] not in tracked:
                tracked.append(pair["long"])
            if pair["short"] not in tracked:
                tracked.append(pair["short"])
        return tracked

    def _book_fair(self, depth: OrderDepth) -> float | None:
        if not depth.buy_orders or not depth.sell_orders:
            return None
        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        best_bid_vol = depth.buy_orders[best_bid]
        best_ask_vol = -depth.sell_orders[best_ask]
        total_top = best_bid_vol + best_ask_vol
        if total_top <= 0:
            return (best_bid + best_ask) / 2.0
        mid = (best_bid + best_ask) / 2.0
        micro = (best_bid * best_ask_vol + best_ask * best_bid_vol) / total_top
        return 0.7 * micro + 0.3 * mid

    def _trade_underlying(self, state: TradingState, product: str) -> Tuple[List[Order], float | None]:
        depth = state.order_depths.get(product)
        if depth is None or not depth.buy_orders or not depth.sell_orders:
            return [], None

        cfg = self.config["delta_one_cfg"][product]
        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        best_bid_vol = depth.buy_orders[best_bid]
        best_ask_vol = -depth.sell_orders[best_ask]
        total_top = best_bid_vol + best_ask_vol
        if total_top <= 0:
            return [], None

        mid = (best_bid + best_ask) / 2.0
        micro = (best_bid * best_ask_vol + best_ask * best_bid_vol) / total_top
        imbalance = (best_bid_vol - best_ask_vol) / total_top
        position = state.position.get(product, 0)

        fair = cfg["fair_mix_micro"] * micro + (1.0 - cfg["fair_mix_micro"]) * mid
        fair += cfg["signal_weight"] * imbalance
        fair -= cfg["inventory_skew"] * position

        orders: List[Order] = []
        buy_used = 0
        sell_used = 0
        limit = POSITION_LIMITS[product]

        for ask in sorted(depth.sell_orders.keys()):
            if ask > fair - cfg["take_width"]:
                break
            avail = -depth.sell_orders[ask]
            qty = min(avail, self._buy_room(product, position, buy_used, limit))
            if qty > 0:
                orders.append(Order(product, int(ask), int(qty)))
                buy_used += qty

        for bid in sorted(depth.buy_orders.keys(), reverse=True):
            if bid < fair + cfg["take_width"]:
                break
            avail = depth.buy_orders[bid]
            qty = min(avail, self._sell_room(product, position, sell_used, limit))
            if qty > 0:
                orders.append(Order(product, int(bid), int(-qty)))
                sell_used += qty

        buy_px = max(0, int(math.floor(fair - cfg["make_edge"])))
        sell_px = int(math.ceil(fair + cfg["make_edge"]))

        if best_bid + 1 < best_ask and best_bid + 1 <= fair - 0.5:
            buy_px = max(buy_px, best_bid + 1)
        if best_ask - 1 > best_bid and best_ask - 1 >= fair + 0.5:
            sell_px = min(sell_px, best_ask - 1)

        if buy_px < sell_px:
            buy_qty = min(cfg["max_quote"], self._buy_room(product, position, buy_used, limit))
            sell_qty = min(cfg["max_quote"], self._sell_room(product, position, sell_used, limit))
            if buy_qty > 0:
                orders.append(Order(product, buy_px, int(buy_qty)))
            if sell_qty > 0:
                orders.append(Order(product, sell_px, int(-sell_qty)))

        return orders, fair

    def _build_voucher_context(self, state: TradingState, memory: Dict[str, Any]) -> Dict[str, Any] | None:
        velvet_depth = state.order_depths.get(VELVET)
        if velvet_depth is None or not velvet_depth.buy_orders or not velvet_depth.sell_orders:
            return None

        spot_bid = max(velvet_depth.buy_orders)
        spot_ask = min(velvet_depth.sell_orders)
        spot_bid_vol = velvet_depth.buy_orders[spot_bid]
        spot_ask_vol = -velvet_depth.sell_orders[spot_ask]
        total_top = spot_bid_vol + spot_ask_vol
        if total_top <= 0:
            return None

        spot_mid = (spot_bid + spot_ask) / 2.0
        spot_micro = (spot_bid * spot_ask_vol + spot_ask * spot_bid_vol) / total_top
        spot = 0.7 * spot_micro + 0.3 * spot_mid
        tte_days = max(0.25, self.config["round3_start_tte_days"] - state.timestamp / self.config["timestamp_units_per_day"])

        chain: Dict[str, Dict[str, float | None]] = {}
        fit_moneyness: List[float] = []
        fit_ivs: List[float] = []

        for product in self.config["all_vouchers"]:
            depth = state.order_depths.get(product)
            if depth is None or not depth.buy_orders or not depth.sell_orders:
                continue

            best_bid = max(depth.buy_orders)
            best_ask = min(depth.sell_orders)
            mid = (best_bid + best_ask) / 2.0
            strike = float(product.split("_")[1])
            intrinsic = max(spot - strike, 0.0)
            time_value = mid - intrinsic
            mid_iv = self._implied_vol_call(mid, spot, strike, tte_days)
            moneyness = self._moneyness(spot, strike, tte_days)
            chain[product] = {
                "best_bid": float(best_bid),
                "best_ask": float(best_ask),
                "mid": float(mid),
                "strike": strike,
                "intrinsic": intrinsic,
                "time_value": time_value,
                "mid_iv": mid_iv,
                "moneyness": moneyness,
            }
            if mid_iv is not None and time_value > self.config["min_time_value_for_iv"]:
                fit_moneyness.append(moneyness)
                fit_ivs.append(mid_iv)
                old_ema = memory["iv_ema"].get(product)
                if old_ema is None:
                    memory["iv_ema"][product] = mid_iv
                else:
                    alpha = self.config["iv_ema_alpha"]
                    memory["iv_ema"][product] = (1.0 - alpha) * old_ema + alpha * mid_iv

        local_coeffs = None
        if len(fit_moneyness) >= self.config["min_fit_points"]:
            local_coeffs = self._fit_quadratic(fit_moneyness, fit_ivs)

        static_coeffs = self.config.get("static_smile_coeffs")
        if local_coeffs is None and static_coeffs is None:
            return None

        fair_map: Dict[str, Dict[str, float]] = {}
        for product, raw_row in chain.items():
            row = {key: float(value) if value is not None else value for key, value in raw_row.items()}
            fair_iv = self._fair_iv(
                row["moneyness"],
                memory["iv_ema"].get(product),
                local_coeffs,
                static_coeffs,
                row["mid_iv"],
            )
            fair_price = max(row["intrinsic"], self._black_scholes_call(spot, row["strike"], tte_days, fair_iv))
            delta = self._call_delta(spot, row["strike"], tte_days, fair_iv)
            fair_map[product] = {
                **row,
                "fair_iv": fair_iv,
                "fair_price": fair_price,
                "delta": delta,
            }

        return {
            "spot": spot,
            "spot_bid": float(spot_bid),
            "spot_ask": float(spot_ask),
            "spot_spread": float(spot_ask - spot_bid),
            "tte_days": float(tte_days),
            "local_coeffs": local_coeffs,
            "static_coeffs": static_coeffs,
            "chain": fair_map,
        }

    def _fair_iv(
        self,
        moneyness: float,
        ema_iv: float | None,
        local_coeffs: Tuple[float, float, float] | None,
        static_coeffs: Tuple[float, float, float] | None,
        fallback_iv: float | None,
    ) -> float:
        weights = self.config["anchor_weights"]
        total = 0.0
        weight_sum = 0.0

        if local_coeffs is not None and weights.get("local", 0.0) > 0.0:
            total += weights["local"] * self._predict_quadratic(local_coeffs, moneyness)
            weight_sum += weights["local"]
        if ema_iv is not None and weights.get("ema", 0.0) > 0.0:
            total += weights["ema"] * ema_iv
            weight_sum += weights["ema"]
        if static_coeffs is not None and weights.get("static", 0.0) > 0.0:
            total += weights["static"] * self._predict_quadratic(static_coeffs, moneyness)
            weight_sum += weights["static"]

        if weight_sum > 0.0:
            return max(0.01, total / weight_sum)
        if fallback_iv is not None:
            return max(0.01, fallback_iv)
        if ema_iv is not None:
            return max(0.01, ema_iv)
        if local_coeffs is not None:
            return max(0.01, self._predict_quadratic(local_coeffs, moneyness))
        if static_coeffs is not None:
            return max(0.01, self._predict_quadratic(static_coeffs, moneyness))
        return 0.15

    def _trade_vouchers(self, state: TradingState, context: Dict[str, Any]) -> Dict[str, List[Order]]:
        result: Dict[str, List[Order]] = {}
        used = {product: {"buy": 0, "sell": 0} for product in self._tracked_voucher_products()}

        for pair in self.config.get("spread_pairs", []):
            self._trade_spread_pair(state, context, pair, result, used)

        for product in self.config["traded_vouchers"]:
            if product not in context["chain"]:
                continue
            depth = state.order_depths.get(product)
            if depth is None or not depth.buy_orders or not depth.sell_orders:
                continue

            row = context["chain"][product]
            cfg = self.config["voucher_cfg"][product]
            position = state.position.get(product, 0)
            limit = min(POSITION_LIMITS[product], cfg["max_abs_pos"])
            side_mode = cfg.get("side_mode", "both")
            fair = row["fair_price"] - cfg["inventory_skew"] * position
            best_bid = int(row["best_bid"])
            best_ask = int(row["best_ask"])
            spread = max(1.0, best_ask - best_bid)

            orders = result.setdefault(product, [])
            buy_used = used[product]["buy"]
            sell_used = used[product]["sell"]

            if side_mode != "ask" and best_ask <= fair - cfg["take_width"]:
                qty = min(-depth.sell_orders[best_ask], self._buy_room(product, position, buy_used, limit))
                if qty > 0:
                    orders.append(Order(product, best_ask, int(qty)))
                    buy_used += qty

            if side_mode != "bid" and best_bid >= fair + cfg["take_width"]:
                qty = min(depth.buy_orders[best_bid], self._sell_room(product, position, sell_used, limit))
                if qty > 0:
                    orders.append(Order(product, best_bid, int(-qty)))
                    sell_used += qty

            quote_edge = max(cfg["quote_edge"], 0.5 * spread)
            buy_px = max(0, int(math.floor(fair - quote_edge)))
            sell_px = int(math.ceil(fair + quote_edge))

            if side_mode != "ask" and best_bid + 1 < best_ask and best_bid + 1 <= fair - 0.25:
                buy_px = max(buy_px, best_bid + 1)
            if side_mode != "bid" and best_ask - 1 > best_bid and best_ask - 1 >= fair + 0.25:
                sell_px = min(sell_px, best_ask - 1)

            quote_size = cfg.get("quote_size", max(5, limit // 3))
            if side_mode != "ask":
                buy_qty = min(quote_size, self._buy_room(product, position, buy_used, limit))
                if buy_qty > 0:
                    orders.append(Order(product, buy_px, int(buy_qty)))
                    buy_used += buy_qty

            if side_mode != "bid":
                sell_qty = min(quote_size, self._sell_room(product, position, sell_used, limit))
                if sell_qty > 0 and buy_px < sell_px:
                    orders.append(Order(product, sell_px, int(-sell_qty)))
                    sell_used += sell_qty

            clear_width = cfg.get("clear_width", 0.25)
            if side_mode == "bid" and position > 0 and best_bid >= fair - clear_width:
                clear_qty = min(position, depth.buy_orders[best_bid], self._sell_room(product, position, sell_used, limit))
                if clear_qty > 0:
                    orders.append(Order(product, best_bid, int(-clear_qty)))
                    sell_used += clear_qty
            if side_mode == "ask" and position < 0 and best_ask <= fair + clear_width:
                clear_qty = min(-position, -depth.sell_orders[best_ask], self._buy_room(product, position, buy_used, limit))
                if clear_qty > 0:
                    orders.append(Order(product, best_ask, int(clear_qty)))
                    buy_used += clear_qty

            used[product]["buy"] = buy_used
            used[product]["sell"] = sell_used

        return result

    def _trade_spread_pair(
        self,
        state: TradingState,
        context: Dict[str, Any],
        pair: Dict[str, Any],
        result: Dict[str, List[Order]],
        used: Dict[str, Dict[str, int]],
    ) -> None:
        long_product = pair["long"]
        short_product = pair["short"]
        if long_product not in context["chain"] or short_product not in context["chain"]:
            return

        long_depth = state.order_depths.get(long_product)
        short_depth = state.order_depths.get(short_product)
        if long_depth is None or short_depth is None:
            return
        if not long_depth.buy_orders or not long_depth.sell_orders or not short_depth.buy_orders or not short_depth.sell_orders:
            return

        long_row = context["chain"][long_product]
        short_row = context["chain"][short_product]
        fair_spread = long_row["fair_price"] - short_row["fair_price"]
        buy_spread_cost = long_row["best_ask"] - short_row["best_bid"]
        sell_spread_value = long_row["best_bid"] - short_row["best_ask"]
        threshold = pair.get("threshold", 1.0)
        clip = pair.get("clip", 20)

        long_pos = state.position.get(long_product, 0)
        short_pos = state.position.get(short_product, 0)
        long_limit = min(POSITION_LIMITS[long_product], self.config["voucher_cfg"][long_product]["max_abs_pos"])
        short_limit = min(POSITION_LIMITS[short_product], self.config["voucher_cfg"][short_product]["max_abs_pos"])

        if buy_spread_cost <= fair_spread - threshold:
            qty = min(
                -long_depth.sell_orders[int(long_row["best_ask"])],
                short_depth.buy_orders[int(short_row["best_bid"])],
                self._buy_room(long_product, long_pos, used[long_product]["buy"], long_limit),
                self._sell_room(short_product, short_pos, used[short_product]["sell"], short_limit),
                clip,
            )
            if qty > 0:
                result.setdefault(long_product, []).append(Order(long_product, int(long_row["best_ask"]), int(qty)))
                result.setdefault(short_product, []).append(Order(short_product, int(short_row["best_bid"]), int(-qty)))
                used[long_product]["buy"] += qty
                used[short_product]["sell"] += qty
        elif sell_spread_value >= fair_spread + threshold:
            qty = min(
                long_depth.buy_orders[int(long_row["best_bid"])],
                -short_depth.sell_orders[int(short_row["best_ask"])],
                self._sell_room(long_product, long_pos, used[long_product]["sell"], long_limit),
                self._buy_room(short_product, short_pos, used[short_product]["buy"], short_limit),
                clip,
            )
            if qty > 0:
                result.setdefault(long_product, []).append(Order(long_product, int(long_row["best_bid"]), int(-qty)))
                result.setdefault(short_product, []).append(Order(short_product, int(short_row["best_ask"]), int(qty)))
                used[long_product]["sell"] += qty
                used[short_product]["buy"] += qty

    def _coarse_delta_hedge(
        self,
        state: TradingState,
        orders: Dict[str, List[Order]],
        context: Dict[str, Any],
    ) -> Order | None:
        cfg = self.config["delta_hedge"]
        if not cfg.get("enabled", False) or VELVET not in state.order_depths:
            return None

        net_delta = 0.0
        for product in self._tracked_voucher_products():
            if product not in context["chain"]:
                continue
            delta = context["chain"][product]["delta"]
            pos = state.position.get(product, 0)
            delta_order_flow = sum(order.quantity for order in orders.get(product, []))
            net_delta += delta * (pos + delta_order_flow)

        if abs(net_delta) < cfg["trigger"]:
            return None

        target_underlying = int(max(-cfg["cap"], min(cfg["cap"], round(-cfg["ratio"] * net_delta))))
        current_underlying = state.position.get(VELVET, 0) + sum(order.quantity for order in orders.get(VELVET, []))
        delta_qty = target_underlying - current_underlying
        if delta_qty == 0:
            return None

        depth = state.order_depths[VELVET]
        if delta_qty > 0:
            best_ask = min(depth.sell_orders)
            return Order(VELVET, int(best_ask), int(delta_qty))

        best_bid = max(depth.buy_orders)
        return Order(VELVET, int(best_bid), int(delta_qty))

    def _buy_room(self, product: str, position: int, buy_used: int, limit: int) -> int:
        return max(0, limit - position - buy_used)

    def _sell_room(self, product: str, position: int, sell_used: int, limit: int) -> int:
        return max(0, limit + position - sell_used)

    def _log_snapshot(
        self,
        state: TradingState,
        hydro_fair: float | None,
        velvet_fair: float | None,
        voucher_context: Dict[str, Any] | None,
    ) -> None:
        logger.print("strategy", self.config["name"])
        if hydro_fair is not None:
            logger.print("HYDRO fair", round(hydro_fair, 3), "pos", state.position.get(HYDRO, 0))
        if velvet_fair is not None:
            logger.print("VELVET fair", round(velvet_fair, 3), "pos", state.position.get(VELVET, 0))
        if voucher_context is not None:
            coeffs = voucher_context["local_coeffs"] or voucher_context["static_coeffs"] or (0.0, 0.0, 0.0)
            logger.print(
                "Voucher tte",
                round(voucher_context["tte_days"], 4),
                "spot",
                round(voucher_context["spot"], 3),
                "fit",
                tuple(round(x, 6) for x in coeffs),
            )
            for product in self._tracked_voucher_products():
                if product in voucher_context["chain"]:
                    row = voucher_context["chain"][product]
                    logger.print(
                        product,
                        "mid",
                        round(row["mid"], 3),
                        "fair",
                        round(row["fair_price"], 3),
                        "iv",
                        round(row["fair_iv"], 5),
                        "delta",
                        round(row["delta"], 4),
                    )

    def _fit_quadratic(self, moneyness: List[float], ivs: List[float]) -> Tuple[float, float, float]:
        n = float(len(moneyness))
        sx = sum(moneyness)
        sx2 = sum(x * x for x in moneyness)
        sx3 = sum(x * x * x for x in moneyness)
        sx4 = sum(x * x * x * x for x in moneyness)
        sy = sum(ivs)
        sxy = sum(x * y for x, y in zip(moneyness, ivs))
        sx2y = sum((x * x) * y for x, y in zip(moneyness, ivs))
        a = [[sx4, sx3, sx2], [sx3, sx2, sx], [sx2, sx, n]]
        b = [sx2y, sxy, sy]
        return self._solve_3x3(a, b)

    def _predict_quadratic(self, coeffs: Tuple[float, float, float], x: float) -> float:
        a, b, c = coeffs
        return a * x * x + b * x + c

    def _solve_3x3(self, a: List[List[float]], b: List[float]) -> Tuple[float, float, float]:
        mat = [row[:] + [rhs] for row, rhs in zip(a, b)]
        for i in range(3):
            pivot = max(range(i, 3), key=lambda r: abs(mat[r][i]))
            mat[i], mat[pivot] = mat[pivot], mat[i]
            if abs(mat[i][i]) < 1e-12:
                return 0.0, 0.0, 0.15
            div = mat[i][i]
            for j in range(i, 4):
                mat[i][j] /= div
            for r in range(3):
                if r == i:
                    continue
                factor = mat[r][i]
                for j in range(i, 4):
                    mat[r][j] -= factor * mat[i][j]
        return mat[0][3], mat[1][3], mat[2][3]

    def _moneyness(self, spot: float, strike: float, tte_days: float) -> float:
        t = max(tte_days / 365.0, 1e-9)
        return math.log(spot / strike) / math.sqrt(t)

    def _black_scholes_call(self, spot: float, strike: float, tte_days: float, vol: float) -> float:
        t = max(tte_days / 365.0, 1e-9)
        if spot <= 0 or strike <= 0 or vol <= 0:
            return max(spot - strike, 0.0)
        d1 = (math.log(spot / strike) + 0.5 * vol * vol * t) / (vol * math.sqrt(t))
        d2 = d1 - vol * math.sqrt(t)
        return spot * self._norm_cdf(d1) - strike * self._norm_cdf(d2)

    def _call_delta(self, spot: float, strike: float, tte_days: float, vol: float) -> float:
        t = max(tte_days / 365.0, 1e-9)
        if spot <= 0 or strike <= 0 or vol <= 0:
            return 1.0 if spot > strike else 0.0
        d1 = (math.log(spot / strike) + 0.5 * vol * vol * t) / (vol * math.sqrt(t))
        return self._norm_cdf(d1)

    def _implied_vol_call(
        self,
        price: float,
        spot: float,
        strike: float,
        tte_days: float,
    ) -> float | None:
        intrinsic = max(spot - strike, 0.0)
        if price <= intrinsic + 1e-9 or spot <= 0 or strike <= 0 or tte_days <= 0:
            return None
        low = 1e-4
        high = 3.0
        for _ in range(80):
            mid = 0.5 * (low + high)
            val = self._black_scholes_call(spot, strike, tte_days, mid)
            if val > price:
                high = mid
            else:
                low = mid
        return 0.5 * (low + high)

    def _norm_cdf(self, x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def make_trader_class(config: Dict[str, Any]):
    class Trader(ConfigurableRound3Trader):
        CONFIG = config

    return Trader
