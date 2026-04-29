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
from typing import Any, Dict, List, Optional, Tuple
import json
import math
import traceback


HYDROGEL_PACK = "HYDROGEL_PACK"
VELVETFRUIT_EXTRACT = "VELVETFRUIT_EXTRACT"
VOUCHER_PRODUCTS = [
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
ACTIVE_VOUCHER_PRODUCTS = set(VOUCHER_PRODUCTS)

POSITION_LIMITS = {
    HYDROGEL_PACK: 200,
    VELVETFRUIT_EXTRACT: 200,
    "VEV_4000": 300,
    "VEV_4500": 300,
    "VEV_5000": 300,
    "VEV_5100": 300,
    "VEV_5200": 300,
    "VEV_5300": 300,
    "VEV_5400": 300,
    "VEV_5500": 300,
    "VEV_6000": 300,
    "VEV_6500": 300,
}

# Core option-model assumptions.
# Set this to match the exact dataset you are testing:
# This log came from day 2 in the live environment, so use 6d here by default.
# Change this when testing a different dataset.
OPTION_TIME_TO_EXPIRY_DAYS = 6.0
OPTION_TIME_TO_EXPIRY = OPTION_TIME_TO_EXPIRY_DAYS / 365.0
RISK_FREE_RATE = 0.0
DEFAULT_IV = 0.30
MIN_IV = 0.05
MAX_IV = 2.00

# Signal and execution controls.
MID_HISTORY_LENGTH = 30
IV_HISTORY_LENGTH = 40
ROLLING_WINDOW = 20
SPOT_SHORT_WINDOW = 6
SPOT_LONG_WINDOW = 24
CROSS_SECTION_STRIKE_GAP = 300
IV_SIGNAL_THRESHOLD = 0.020
BASE_TIME_VALUE_THRESHOLD = 2.0
SPREAD_BUFFER = 1.0
MIN_HISTORY_TO_TRADE = 2
ACTIVE_STRIKE_DISTANCE = 500
SECONDARY_STRIKE_DISTANCE = 1600
INVENTORY_EDGE_PENALTY = 1.50
MAX_SPOT_TRADE_SIZE = 8
MAX_VOUCHER_TRADE_SIZE = 4
SECONDARY_VOUCHER_TRADE_SIZE = 0
MAX_HEDGE_TRADE_SIZE = 6
HEDGE_REBALANCE_THRESHOLD = 5
UNDERLYING_HEDGE_RATIO = 0.0
HYDROGEL_TAKE_SPREAD_FRACTION = 0.35
VELVETFRUIT_TAKE_SPREAD_FRACTION = 0.80
HYDROGEL_QUOTE_SPREAD_FRACTION = 0.25
VELVETFRUIT_QUOTE_SPREAD_FRACTION = 0.65
HYDROGEL_SPOT_INVENTORY_SKEW = 6.0
VELVETFRUIT_SPOT_INVENTORY_SKEW = 18.0
HYDROGEL_FAIR_MID_WEIGHT = 0.30
VELVETFRUIT_FAIR_MID_WEIGHT = 0.65
HYDROGEL_ONE_SIDED_QUOTE_FRACTION = 0.35
VELVETFRUIT_ONE_SIDED_QUOTE_FRACTION = 0.10
HYDROGEL_TREND_WEIGHT = 0.35
VELVETFRUIT_TREND_WEIGHT = 0.20
HYDROGEL_TREND_CAP = 4.5
VELVETFRUIT_TREND_CAP = 2.5
HYDROGEL_VOL_BUFFER = 0.12
VELVETFRUIT_VOL_BUFFER = 0.18
HYDROGEL_TAKE_SIZE = 8
VELVETFRUIT_TAKE_SIZE = 3
HYDROGEL_QUOTE_SIZE = 12
VELVETFRUIT_QUOTE_SIZE = 3
SECONDARY_IV_SIGNAL_THRESHOLD = 0.035
SECONDARY_EDGE_BUFFER = 0.75
VOUCHER_QUOTE_SPREAD_FRACTION = 0.35
PRIMARY_VOUCHER_QUOTE_SIZE = 0
SECONDARY_VOUCHER_QUOTE_SIZE = 0
VOUCHER_INVENTORY_SKEW = 8.0
FOCUS_VOUCHER_DISTANCE_LIMIT = 1600.0
FOCUS_VOUCHER_INVENTORY_CAP = 60.0
MAX_ACTIVE_VOUCHERS_PER_TICK = 2

MAX_HYDROGEL_SPREAD = 20.0
MAX_VELVETFRUIT_SPREAD = 8.0
MAX_VOUCHER_ABSOLUTE_SPREAD = 8.0
MAX_VOUCHER_RELATIVE_SPREAD = 0.18


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

        max_item_length = (self.max_log_length - base_length) // 3

        print(
            self.to_json(
                [
                    self.compress_state(
                        state, self.truncate(getattr(state, "traderData", ""), max_item_length)
                    ),
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
        compressed: List[List[Any]] = []
        for listing in listings.values():
            compressed.append(
                [
                    getattr(listing, "symbol", listing["symbol"] if isinstance(listing, dict) else None),
                    getattr(
                        listing,
                        "product",
                        listing["product"] if isinstance(listing, dict) else None,
                    ),
                    getattr(
                        listing,
                        "denomination",
                        listing["denomination"] if isinstance(listing, dict) else None,
                    ),
                ]
            )
        return compressed

    def compress_order_depths(
        self, order_depths: Dict[Symbol, OrderDepth]
    ) -> Dict[Symbol, List[Any]]:
        compressed: Dict[Symbol, List[Any]] = {}
        for symbol, order_depth in order_depths.items():
            compressed[symbol] = [order_depth.buy_orders, order_depth.sell_orders]
        return compressed

    def compress_trades(self, trades: Dict[Symbol, List[Trade]]) -> List[List[Any]]:
        compressed: List[List[Any]] = []
        for trade_list in trades.values():
            for trade in trade_list:
                compressed.append(
                    [
                        trade.symbol,
                        trade.price,
                        trade.quantity,
                        trade.buyer,
                        trade.seller,
                        trade.timestamp,
                    ]
                )
        return compressed

    def compress_observations(self, observations: Observation) -> List[Any]:
        conversion_observations: Dict[str, List[Any]] = {}
        for product, observation in observations.conversionObservations.items():
            conversion_observations[product] = [
                getattr(observation, "bidPrice", None),
                getattr(observation, "askPrice", None),
                getattr(observation, "transportFees", None),
                getattr(observation, "exportTariff", None),
                getattr(observation, "importTariff", None),
                getattr(observation, "sunlight", getattr(observation, "sunlightIndex", None)),
                getattr(observation, "humidity", getattr(observation, "sugarPrice", None)),
            ]

        return [observations.plainValueObservations, conversion_observations]

    def compress_orders(self, orders: Dict[Symbol, List[Order]]) -> List[List[Any]]:
        compressed: List[List[Any]] = []
        for order_list in orders.values():
            for order in order_list:
                compressed.append([order.symbol, order.price, order.quantity])
        return compressed

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        if max_length <= 0:
            return ""

        if len(value) <= max_length:
            return value

        if max_length <= 3:
            return value[:max_length]

        return value[: max_length - 3] + "..."


logger = Logger()


class Trader:
    def __init__(self) -> None:
        self.position_limits = POSITION_LIMITS.copy()
        self.orders: Dict[str, List[Order]] = {}
        self.conversions = 0
        self.data = self.default_state()

    # ------------------------------------------------------------------
    # Persistent traderData helpers
    # ------------------------------------------------------------------
    def default_state(self) -> Dict[str, Any]:
        return {
            "mid_history": {
                HYDROGEL_PACK: [],
                VELVETFRUIT_EXTRACT: [],
            },
            "iv_history": {product: [] for product in VOUCHER_PRODUCTS},
            "tv_history": {product: [] for product in VOUCHER_PRODUCTS},
        }

    def load_state(self, trader_data: str) -> Dict[str, Any]:
        state = self.default_state()
        if not trader_data:
            return state

        try:
            raw = json.loads(trader_data)
        except (TypeError, ValueError, json.JSONDecodeError):
            return state

        if not isinstance(raw, dict):
            return state

        raw_mid = raw.get("mid_history", {})
        if isinstance(raw_mid, dict):
            for product in state["mid_history"]:
                state["mid_history"][product] = self.clean_history(
                    raw_mid.get(product, []), MID_HISTORY_LENGTH
                )

        raw_iv = raw.get("iv_history", {})
        if isinstance(raw_iv, dict):
            for product in VOUCHER_PRODUCTS:
                state["iv_history"][product] = self.clean_history(
                    raw_iv.get(product, []), IV_HISTORY_LENGTH
                )

        raw_tv = raw.get("tv_history", {})
        if isinstance(raw_tv, dict):
            for product in VOUCHER_PRODUCTS:
                state["tv_history"][product] = self.clean_history(
                    raw_tv.get(product, []), IV_HISTORY_LENGTH
                )

        return state

    def dump_state(self) -> str:
        return json.dumps(self.data, separators=(",", ":"))

    def clean_history(self, values: Any, max_length: int) -> List[float]:
        cleaned: List[float] = []
        if not isinstance(values, list):
            return cleaned

        for value in values[-max_length:]:
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(numeric_value):
                cleaned.append(numeric_value)
        return cleaned

    def append_history(self, history: List[float], value: Optional[float], max_length: int) -> None:
        if value is None:
            return
        if not math.isfinite(value):
            return
        history.append(float(value))
        if len(history) > max_length:
            del history[:-max_length]

    # ------------------------------------------------------------------
    # Market data helpers
    # ------------------------------------------------------------------
    def get_best_bid_ask(self, order_depth: Optional[OrderDepth]) -> Tuple[Optional[int], Optional[int]]:
        if order_depth is None:
            return None, None

        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        return best_bid, best_ask

    def get_mid_price(self, order_depth: Optional[OrderDepth]) -> Optional[float]:
        best_bid, best_ask = self.get_best_bid_ask(order_depth)
        if best_bid is not None and best_ask is not None:
            return (best_bid + best_ask) / 2.0
        if best_bid is not None:
            return float(best_bid)
        if best_ask is not None:
            return float(best_ask)
        return None

    def parse_strike(self, product: str) -> Optional[int]:
        if not product.startswith("VEV_"):
            return None
        try:
            return int(product.split("_", 1)[1])
        except (IndexError, ValueError):
            return None

    def get_position(self, state: TradingState, product: str) -> int:
        return int(state.position.get(product, 0))

    def get_sorted_buys(self, order_depth: Optional[OrderDepth]) -> List[Tuple[int, int]]:
        if order_depth is None:
            return []
        return sorted(order_depth.buy_orders.items(), key=lambda item: item[0], reverse=True)

    def get_sorted_sells(self, order_depth: Optional[OrderDepth]) -> List[Tuple[int, int]]:
        if order_depth is None:
            return []
        return sorted(order_depth.sell_orders.items(), key=lambda item: item[0])

    def average(self, values: List[float], window: Optional[int] = None) -> Optional[float]:
        if not values:
            return None
        trimmed = values[-window:] if window is not None else values
        if not trimmed:
            return None
        return sum(trimmed) / float(len(trimmed))

    def stddev(self, values: List[float], window: Optional[int] = None) -> float:
        if not values:
            return 0.0
        trimmed = values[-window:] if window is not None else values
        if len(trimmed) < 2:
            return 0.0
        avg = sum(trimmed) / float(len(trimmed))
        variance = sum((value - avg) * (value - avg) for value in trimmed) / float(len(trimmed) - 1)
        return math.sqrt(max(0.0, variance))

    def clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def add_order(self, product: str, price: int, quantity: int) -> None:
        if quantity == 0:
            return
        self.orders.setdefault(product, []).append(Order(product, int(price), int(quantity)))

    def buy_room(self, position: int, limit: int) -> int:
        return max(0, limit - position)

    def sell_room(self, position: int, limit: int) -> int:
        return max(0, limit + position)

    def spread_is_tradeable(self, product: str, mid_price: Optional[float], spread: Optional[float]) -> bool:
        if mid_price is None or spread is None:
            return False

        if product == HYDROGEL_PACK:
            return spread <= MAX_HYDROGEL_SPREAD

        if product == VELVETFRUIT_EXTRACT:
            return spread <= MAX_VELVETFRUIT_SPREAD

        if spread > MAX_VOUCHER_ABSOLUTE_SPREAD:
            return False

        if mid_price > 0 and spread > (mid_price * MAX_VOUCHER_RELATIVE_SPREAD + 1.0):
            return False

        return True

    # ------------------------------------------------------------------
    # Black-Scholes helpers
    # ------------------------------------------------------------------
    def normal_cdf(self, x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def black_scholes_call_price(
        self, spot: float, strike: float, expiry: float, rate: float, sigma: float
    ) -> Optional[float]:
        if spot <= 0 or strike <= 0:
            return None
        if expiry <= 0:
            return max(spot - strike, 0.0)

        discounted_strike = strike * math.exp(-rate * expiry)
        if sigma <= 0:
            return max(spot - discounted_strike, 0.0)

        sqrt_t = math.sqrt(expiry)
        sigma_sqrt_t = sigma * sqrt_t
        if sigma_sqrt_t <= 0:
            return max(spot - discounted_strike, 0.0)

        d1 = (math.log(spot / strike) + (rate + 0.5 * sigma * sigma) * expiry) / sigma_sqrt_t
        d2 = d1 - sigma_sqrt_t
        return spot * self.normal_cdf(d1) - discounted_strike * self.normal_cdf(d2)

    def black_scholes_call_delta(
        self, spot: float, strike: float, expiry: float, rate: float, sigma: float
    ) -> Optional[float]:
        if spot <= 0 or strike <= 0:
            return None
        if expiry <= 0 or sigma <= 0:
            if spot > strike:
                return 1.0
            if spot < strike:
                return 0.0
            return 0.5

        sigma_sqrt_t = sigma * math.sqrt(expiry)
        if sigma_sqrt_t <= 0:
            return None

        d1 = (math.log(spot / strike) + (rate + 0.5 * sigma * sigma) * expiry) / sigma_sqrt_t
        return self.normal_cdf(d1)

    def implied_volatility_call(
        self, spot: float, strike: float, expiry: float, rate: float, market_price: float
    ) -> Optional[float]:
        if spot <= 0 or strike <= 0 or expiry <= 0 or market_price < 0:
            return None

        intrinsic = max(spot - strike, 0.0)
        if market_price < intrinsic - 1e-6:
            return None
        if market_price > spot + 1e-6:
            return None

        low = MIN_IV
        high = MAX_IV
        low_price = self.black_scholes_call_price(spot, strike, expiry, rate, low)
        high_price = self.black_scholes_call_price(spot, strike, expiry, rate, high)

        if low_price is None or high_price is None:
            return None

        if market_price <= low_price:
            return low
        if market_price >= high_price:
            return high

        for _ in range(60):
            mid = (low + high) / 2.0
            model_price = self.black_scholes_call_price(spot, strike, expiry, rate, mid)
            if model_price is None:
                return None
            if model_price > market_price:
                high = mid
            else:
                low = mid

        return self.clamp((low + high) / 2.0, MIN_IV, MAX_IV)

    # ------------------------------------------------------------------
    # Execution helpers
    # ------------------------------------------------------------------
    def sweep_asks(
        self,
        product: str,
        order_depth: OrderDepth,
        fair_price: float,
        required_edge: float,
        max_quantity: int,
    ) -> int:
        traded = 0
        for ask_price, ask_volume in self.get_sorted_sells(order_depth):
            available = abs(int(ask_volume))
            if available <= 0 or traded >= max_quantity:
                continue
            if fair_price - ask_price <= required_edge:
                break
            quantity = min(max_quantity - traded, available)
            self.add_order(product, ask_price, quantity)
            traded += quantity
            if traded >= max_quantity:
                break
        return traded

    def sweep_bids(
        self,
        product: str,
        order_depth: OrderDepth,
        fair_price: float,
        required_edge: float,
        max_quantity: int,
    ) -> int:
        traded = 0
        for bid_price, bid_volume in self.get_sorted_buys(order_depth):
            available = abs(int(bid_volume))
            if available <= 0 or traded >= max_quantity:
                continue
            if bid_price - fair_price <= required_edge:
                break
            quantity = min(max_quantity - traded, available)
            self.add_order(product, bid_price, -quantity)
            traded += quantity
            if traded >= max_quantity:
                break
        return traded

    def compute_size_cap(
        self, max_trade_size: int, edge: float, required_edge: float, weight: float = 1.0
    ) -> int:
        if max_trade_size <= 0:
            return 0

        denominator = max(required_edge, 1.0)
        strength = edge / denominator
        scale = min(1.0, max(0.25, strength / 2.0))
        size = int(round(max_trade_size * weight * scale))
        return max(1, min(max_trade_size, size))

    def get_spot_parameters(self, product: str) -> Dict[str, float]:
        if product == HYDROGEL_PACK:
            return {
                "take_fraction": HYDROGEL_TAKE_SPREAD_FRACTION,
                "quote_fraction": HYDROGEL_QUOTE_SPREAD_FRACTION,
                "inventory_skew": HYDROGEL_SPOT_INVENTORY_SKEW,
                "fair_mid_weight": HYDROGEL_FAIR_MID_WEIGHT,
                "one_sided_fraction": HYDROGEL_ONE_SIDED_QUOTE_FRACTION,
                "trend_weight": HYDROGEL_TREND_WEIGHT,
                "trend_cap": HYDROGEL_TREND_CAP,
                "vol_buffer": HYDROGEL_VOL_BUFFER,
            }

        return {
            "take_fraction": VELVETFRUIT_TAKE_SPREAD_FRACTION,
            "quote_fraction": VELVETFRUIT_QUOTE_SPREAD_FRACTION,
            "inventory_skew": VELVETFRUIT_SPOT_INVENTORY_SKEW,
            "fair_mid_weight": VELVETFRUIT_FAIR_MID_WEIGHT,
            "one_sided_fraction": VELVETFRUIT_ONE_SIDED_QUOTE_FRACTION,
            "trend_weight": VELVETFRUIT_TREND_WEIGHT,
            "trend_cap": VELVETFRUIT_TREND_CAP,
            "vol_buffer": VELVETFRUIT_VOL_BUFFER,
        }

    def get_voucher_parameters(self, product: str) -> Dict[str, float]:
        return {
            "max_trade_size": float(MAX_VOUCHER_TRADE_SIZE),
            "iv_threshold": IV_SIGNAL_THRESHOLD,
            "edge_buffer": 0.0,
            "distance_limit": FOCUS_VOUCHER_DISTANCE_LIMIT,
            "quote_size": float(PRIMARY_VOUCHER_QUOTE_SIZE),
            "inventory_cap": FOCUS_VOUCHER_INVENTORY_CAP,
        }

    # ------------------------------------------------------------------
    # Spot strategies
    # ------------------------------------------------------------------
    def trade_mean_reversion_spot(
        self,
        state: TradingState,
        product: str,
        max_spread: float,
        max_trade_size: int,
    ) -> Optional[float]:
        order_depth = state.order_depths.get(product)
        if order_depth is None:
            return None

        best_bid, best_ask = self.get_best_bid_ask(order_depth)
        mid_price = self.get_mid_price(order_depth)
        if best_bid is None or best_ask is None or mid_price is None:
            return mid_price

        spread = float(best_ask - best_bid)
        if spread > max_spread:
            return mid_price

        history = self.data["mid_history"].setdefault(product, [])
        fair_price = self.average(history, ROLLING_WINDOW)
        if fair_price is None:
            fair_price = mid_price

        position = self.get_position(state, product)
        limit = self.position_limits.get(product, 0)
        required_edge = spread / 2.0 + SPREAD_BUFFER

        buy_edge = fair_price - best_ask
        if buy_edge > required_edge:
            size_cap = self.compute_size_cap(max_trade_size, buy_edge, required_edge)
            size_cap = min(size_cap, self.buy_room(position, limit))
            traded = self.sweep_asks(product, order_depth, fair_price, required_edge, size_cap)
            position += traded

        sell_edge = best_bid - fair_price
        if sell_edge > required_edge:
            size_cap = self.compute_size_cap(max_trade_size, sell_edge, required_edge)
            size_cap = min(size_cap, self.sell_room(position, limit))
            self.sweep_bids(product, order_depth, fair_price, required_edge, size_cap)

        return mid_price

    def trade_active_spot(
        self,
        state: TradingState,
        product: str,
        max_spread: float,
        max_take_size: int,
        quote_size: int,
    ) -> Optional[float]:
        order_depth = state.order_depths.get(product)
        if order_depth is None:
            return None

        best_bid, best_ask = self.get_best_bid_ask(order_depth)
        mid_price = self.get_mid_price(order_depth)
        if best_bid is None or best_ask is None or mid_price is None:
            return mid_price

        spread = float(best_ask - best_bid)
        if spread <= 0 or spread > max_spread:
            return mid_price

        history = self.data["mid_history"].setdefault(product, [])
        history_fair = self.average(history, ROLLING_WINDOW)
        params = self.get_spot_parameters(product)
        price_series = history[-(SPOT_LONG_WINDOW - 1) :] + [mid_price]
        short_fair = self.average(price_series, SPOT_SHORT_WINDOW)
        long_fair = self.average(price_series, SPOT_LONG_WINDOW)
        recent_volatility = self.stddev(price_series, SPOT_LONG_WINDOW)
        trend_signal = 0.0
        if short_fair is not None and long_fair is not None:
            trend_signal = short_fair - long_fair
        trend_bias = self.clamp(
            params["trend_weight"] * trend_signal,
            -params["trend_cap"],
            params["trend_cap"],
        )
        if history_fair is None:
            fair_price = mid_price
        else:
            fair_price = (
                params["fair_mid_weight"] * mid_price
                + (1.0 - params["fair_mid_weight"]) * history_fair
            )
        fair_price += trend_bias

        position = self.get_position(state, product)
        limit = self.position_limits.get(product, 0)
        if limit <= 0:
            return mid_price

        reservation_price = fair_price - params["inventory_skew"] * position / float(limit)
        take_threshold = max(
            1.0,
            params["take_fraction"] * spread + params["vol_buffer"] * recent_volatility,
        )
        quote_buffer = max(
            1.0,
            params["quote_fraction"] * spread + 0.5 * params["vol_buffer"] * recent_volatility,
        )

        buy_edge = reservation_price - best_ask
        if buy_edge > take_threshold:
            size_cap = self.compute_size_cap(max_take_size, buy_edge, take_threshold)
            size_cap = min(size_cap, self.buy_room(position, limit))
            traded = self.sweep_asks(product, order_depth, reservation_price, take_threshold, size_cap)
            position += traded

        sell_edge = best_bid - reservation_price
        if sell_edge > take_threshold:
            size_cap = self.compute_size_cap(max_take_size, sell_edge, take_threshold)
            size_cap = min(size_cap, self.sell_room(position, limit))
            traded = self.sweep_bids(product, order_depth, reservation_price, take_threshold, size_cap)
            position -= traded

        if spread >= 2:
            bid_quote = int(min(best_bid + 1, math.floor(reservation_price - quote_buffer)))
            ask_quote = int(max(best_ask - 1, math.ceil(reservation_price + quote_buffer)))
            bid_quote = max(0, bid_quote)
            ask_quote = max(0, ask_quote)

            if bid_quote >= ask_quote:
                bid_quote = best_bid
                ask_quote = best_ask

            quote_limit = params["one_sided_fraction"] * float(limit)
            allow_bid_quote = position < quote_limit
            allow_ask_quote = position > -quote_limit
            strong_trend = abs(trend_bias) >= max(1.0, 0.75 * spread)
            if strong_trend and trend_bias > 0:
                allow_ask_quote = False
            if strong_trend and trend_bias < 0:
                allow_bid_quote = False

            buy_size = min(quote_size, self.buy_room(position, limit))
            if allow_bid_quote and buy_size > 0 and reservation_price - bid_quote >= 0.5:
                self.add_order(product, bid_quote, buy_size)

            sell_size = min(quote_size, self.sell_room(position, limit))
            if allow_ask_quote and sell_size > 0 and ask_quote - reservation_price >= 0.5:
                self.add_order(product, ask_quote, -sell_size)

        return mid_price

    # ------------------------------------------------------------------
    # Voucher analytics
    # ------------------------------------------------------------------
    def voucher_weight(self, product: str, spot_price: float, strike: int) -> float:
        distance = abs(spot_price - strike)
        if distance <= 100:
            distance_weight = 1.20
        elif distance <= 250:
            distance_weight = 1.00
        elif distance <= 500:
            distance_weight = 0.80
        else:
            distance_weight = 0.60

        product_weight = {
            "VEV_4000": 0.85,
            "VEV_4500": 0.80,
            "VEV_5000": 1.05,
            "VEV_5100": 1.10,
            "VEV_5200": 1.15,
            "VEV_5300": 1.15,
            "VEV_5400": 1.10,
            "VEV_5500": 1.05,
            "VEV_6000": 0.80,
            "VEV_6500": 0.70,
        }.get(product, 1.0)

        return distance_weight * product_weight

    def collect_voucher_metrics(
        self, state: TradingState, spot_price: Optional[float]
    ) -> Dict[str, Dict[str, float]]:
        metrics: Dict[str, Dict[str, float]] = {}
        if spot_price is None:
            return metrics

        for product in VOUCHER_PRODUCTS:
            order_depth = state.order_depths.get(product)
            if order_depth is None:
                continue

            strike = self.parse_strike(product)
            voucher_mid = self.get_mid_price(order_depth)
            best_bid, best_ask = self.get_best_bid_ask(order_depth)
            if strike is None or voucher_mid is None or best_bid is None or best_ask is None:
                continue

            intrinsic = max(spot_price - strike, 0.0)
            time_value = voucher_mid - intrinsic
            spread = float(best_ask - best_bid)
            implied_vol = self.implied_volatility_call(
                spot_price, float(strike), OPTION_TIME_TO_EXPIRY, RISK_FREE_RATE, voucher_mid
            )

            metrics[product] = {
                "strike": float(strike),
                "mid": voucher_mid,
                "best_bid": float(best_bid),
                "best_ask": float(best_ask),
                "spread": spread,
                "intrinsic": intrinsic,
                "time_value": time_value,
                "implied_vol": implied_vol if implied_vol is not None else float("nan"),
            }

        return metrics

    def finite_or_none(self, value: float) -> Optional[float]:
        if math.isfinite(value):
            return value
        return None

    def enrich_voucher_metrics(
        self, spot_price: Optional[float], metrics: Dict[str, Dict[str, float]]
    ) -> None:
        if spot_price is None:
            return

        anchor_sigma_inputs: List[float] = [DEFAULT_IV]
        anchor_info = metrics.get("VEV_5000")
        if anchor_info is not None:
            anchor_current_iv = self.finite_or_none(anchor_info["implied_vol"])
            if anchor_current_iv is not None:
                anchor_sigma_inputs.extend([anchor_current_iv, anchor_current_iv])
        anchor_history_iv = self.average(self.data["iv_history"].get("VEV_5000", []), ROLLING_WINDOW)
        if anchor_history_iv is not None:
            anchor_sigma_inputs.extend([anchor_history_iv, anchor_history_iv])
        anchor_sigma = self.clamp(self.average(anchor_sigma_inputs) or DEFAULT_IV, MIN_IV, MAX_IV)

        for product, info in metrics.items():
            strike = int(info["strike"])
            current_iv = self.finite_or_none(info["implied_vol"])
            history_iv = self.average(self.data["iv_history"].get(product, []), ROLLING_WINDOW)
            history_tv = self.average(self.data["tv_history"].get(product, []), ROLLING_WINDOW)

            neighbour_ivs: List[float] = []
            neighbour_tvs: List[float] = []
            for other_product, other_info in metrics.items():
                if other_product == product:
                    continue
                other_strike = int(other_info["strike"])
                if abs(other_strike - strike) > CROSS_SECTION_STRIKE_GAP:
                    continue

                other_iv = self.finite_or_none(other_info["implied_vol"])
                if other_iv is not None:
                    neighbour_ivs.append(other_iv)
                neighbour_tvs.append(other_info["time_value"])

            cross_iv = self.average(neighbour_ivs)
            cross_tv = self.average(neighbour_tvs)

            sigma_inputs: List[float] = [DEFAULT_IV, anchor_sigma, anchor_sigma]
            if history_iv is not None:
                sigma_inputs.extend([history_iv, history_iv])
            if cross_iv is not None:
                sigma_inputs.append(cross_iv)
            if current_iv is not None and product == "VEV_5000":
                sigma_inputs.append(current_iv)

            fair_sigma = self.clamp(self.average(sigma_inputs) or DEFAULT_IV, MIN_IV, MAX_IV)
            model_price = self.black_scholes_call_price(
                spot_price, float(strike), OPTION_TIME_TO_EXPIRY, RISK_FREE_RATE, fair_sigma
            )
            fair_price = model_price if model_price is not None else info["mid"]
            fair_time_value = max(fair_price - info["intrinsic"], 0.0)
            info["fair_sigma"] = fair_sigma
            info["history_iv"] = history_iv if history_iv is not None else float("nan")
            info["cross_iv"] = cross_iv if cross_iv is not None else float("nan")
            info["fair_time_value"] = fair_time_value
            info["history_time_value"] = history_tv if history_tv is not None else float("nan")
            info["cross_time_value"] = cross_tv if cross_tv is not None else float("nan")
            info["fair_price"] = fair_price

    # ------------------------------------------------------------------
    # Voucher trading and underlying hedge
    # ------------------------------------------------------------------
    def trade_vouchers(
        self, state: TradingState, spot_price: Optional[float], metrics: Dict[str, Dict[str, float]]
    ) -> None:
        if spot_price is None:
            return

        if len(self.data["mid_history"].get(VELVETFRUIT_EXTRACT, [])) < MIN_HISTORY_TO_TRADE:
            return

        ranked_signals: List[Tuple[float, str]] = []
        for product, info in metrics.items():
            if product not in ACTIVE_VOUCHER_PRODUCTS:
                continue

            current_iv = self.finite_or_none(info["implied_vol"])
            if current_iv is None:
                continue

            strike = int(info["strike"])
            voucher_mid = info["mid"]
            spread = info["spread"]
            if not self.spread_is_tradeable(product, voucher_mid, spread):
                continue

            voucher_params = self.get_voucher_parameters(product)
            if abs(spot_price - strike) > voucher_params["distance_limit"]:
                continue

            fair_price = info["fair_price"]
            fair_sigma = info["fair_sigma"]
            fair_time_value = info["fair_time_value"]
            market_time_value = info["time_value"]
            iv_gap = fair_sigma - current_iv
            tv_gap = fair_time_value - market_time_value
            best_bid = int(info["best_bid"])
            best_ask = int(info["best_ask"])
            edge = max(fair_price - best_ask, best_bid - fair_price, 0.0)
            score = (
                max(abs(iv_gap) - voucher_params["iv_threshold"], 0.0)
                + 0.25 * max(abs(tv_gap) - BASE_TIME_VALUE_THRESHOLD, 0.0)
                + 0.05 * edge
            )
            ranked_signals.append((score, product))

        ranked_signals.sort(reverse=True)
        active_products = {
            product
            for score, product in ranked_signals[:MAX_ACTIVE_VOUCHERS_PER_TICK]
            if score > 0.0
        }

        for product, info in metrics.items():
            if product not in ACTIVE_VOUCHER_PRODUCTS:
                continue

            order_depth = state.order_depths.get(product)
            if order_depth is None:
                continue

            voucher_mid = info["mid"]
            spread = info["spread"]
            best_bid = int(info["best_bid"])
            best_ask = int(info["best_ask"])
            fair_price = info["fair_price"]
            fair_sigma = info["fair_sigma"]
            current_iv = self.finite_or_none(info["implied_vol"])
            market_time_value = info["time_value"]
            fair_time_value = info["fair_time_value"]
            strike = int(info["strike"])

            if not self.spread_is_tradeable(product, voucher_mid, spread):
                continue

            position = self.get_position(state, product)
            limit = self.position_limits.get(product, 0)
            if product not in active_products and position == 0:
                continue

            weight = self.voucher_weight(product, spot_price, strike)
            voucher_params = self.get_voucher_parameters(product)
            if abs(spot_price - strike) > voucher_params["distance_limit"]:
                continue

            inventory_cap = int(min(limit, voucher_params["inventory_cap"]))
            if inventory_cap <= 0:
                continue

            inventory_penalty = INVENTORY_EDGE_PENALTY * abs(position) / max(inventory_cap, 1)
            required_edge = (
                0.60 * spread
                + SPREAD_BUFFER
                + voucher_params["edge_buffer"]
                + inventory_penalty
            )
            iv_gap = fair_sigma - current_iv if current_iv is not None else 0.0
            tv_gap = fair_time_value - market_time_value

            can_trade_signal = product in active_products
            if not can_trade_signal and position != 0:
                if position > 0:
                    unwind_edge = best_bid - fair_price
                    if unwind_edge > -0.5 * required_edge:
                        unwind_size = min(abs(position), int(voucher_params["max_trade_size"]))
                        if unwind_size > 0:
                            self.add_order(product, best_bid, -unwind_size)
                            position -= unwind_size
                else:
                    unwind_edge = fair_price - best_ask
                    if unwind_edge > -0.5 * required_edge:
                        unwind_size = min(abs(position), int(voucher_params["max_trade_size"]))
                        if unwind_size > 0:
                            self.add_order(product, best_ask, unwind_size)
                            position += unwind_size

            if current_iv is not None and can_trade_signal:
                buy_edge = fair_price - best_ask
                if (
                    buy_edge > required_edge
                    and (
                        iv_gap > voucher_params["iv_threshold"]
                        or tv_gap > BASE_TIME_VALUE_THRESHOLD
                    )
                ):
                    size_cap = self.compute_size_cap(
                        int(voucher_params["max_trade_size"]), buy_edge, required_edge, weight
                    )
                    size_cap = min(size_cap, max(0, inventory_cap - position))
                    traded = self.sweep_asks(product, order_depth, fair_price, required_edge, size_cap)
                    position += traded

                sell_edge = best_bid - fair_price
                if (
                    sell_edge > required_edge
                    and (
                        -iv_gap > voucher_params["iv_threshold"]
                        or -tv_gap > BASE_TIME_VALUE_THRESHOLD
                    )
                ):
                    size_cap = self.compute_size_cap(
                        int(voucher_params["max_trade_size"]), sell_edge, required_edge, weight
                    )
                    size_cap = min(size_cap, max(0, inventory_cap + position))
                    traded = self.sweep_bids(product, order_depth, fair_price, required_edge, size_cap)
                    position -= traded

            if spread >= 1 and voucher_params["quote_size"] > 0 and (can_trade_signal or position != 0):
                reservation_price = fair_price - VOUCHER_INVENTORY_SKEW * position / max(inventory_cap, 1)
                quote_buffer = max(
                    1.0,
                    VOUCHER_QUOTE_SPREAD_FRACTION * spread + voucher_params["edge_buffer"],
                )
                bid_quote = int(min(best_bid + 1, math.floor(reservation_price - quote_buffer)))
                ask_quote = int(max(best_ask - 1, math.ceil(reservation_price + quote_buffer)))
                bid_quote = max(0, bid_quote)
                ask_quote = max(0, ask_quote)

                if bid_quote >= ask_quote:
                    bid_quote = best_bid
                    ask_quote = best_ask

                quote_size = int(voucher_params["quote_size"])
                quote_limit = 0.70 * inventory_cap
                if can_trade_signal and position < quote_limit and reservation_price - bid_quote >= 0.5:
                    buy_size = min(quote_size, max(0, inventory_cap - position))
                    if buy_size > 0:
                        self.add_order(product, bid_quote, buy_size)

                if position > 0 and ask_quote >= best_bid:
                    exit_size = min(quote_size, position)
                    if exit_size > 0:
                        self.add_order(product, ask_quote, -exit_size)
                elif position < 0 and bid_quote <= best_ask:
                    exit_size = min(quote_size, -position)
                    if exit_size > 0:
                        self.add_order(product, bid_quote, exit_size)
                elif can_trade_signal and position > -quote_limit and ask_quote - reservation_price >= 0.5:
                    sell_size = min(quote_size, max(0, inventory_cap + position))
                    if sell_size > 0:
                        self.add_order(product, ask_quote, -sell_size)

    def estimate_net_voucher_delta(
        self, state: TradingState, spot_price: Optional[float], metrics: Dict[str, Dict[str, float]]
    ) -> float:
        if spot_price is None:
            return 0.0

        net_delta = 0.0
        for product in VOUCHER_PRODUCTS:
            position = self.get_position(state, product)
            if position == 0:
                continue

            strike = self.parse_strike(product)
            if strike is None:
                continue

            sigma = DEFAULT_IV
            info = metrics.get(product)
            if info is not None:
                current_iv = self.finite_or_none(info["implied_vol"])
                if current_iv is not None:
                    sigma = current_iv
                else:
                    sigma = info.get("fair_sigma", DEFAULT_IV)
            else:
                history_iv = self.average(self.data["iv_history"].get(product, []), ROLLING_WINDOW)
                if history_iv is not None:
                    sigma = history_iv

            delta = self.black_scholes_call_delta(
                spot_price, float(strike), OPTION_TIME_TO_EXPIRY, RISK_FREE_RATE, sigma
            )
            if delta is not None:
                net_delta += position * delta

        return net_delta

    def trade_velvetfruit(
        self, state: TradingState, spot_price: Optional[float], metrics: Dict[str, Dict[str, float]]
    ) -> None:
        if UNDERLYING_HEDGE_RATIO <= 0.0:
            self.trade_active_spot(
                state=state,
                product=VELVETFRUIT_EXTRACT,
                max_spread=MAX_VELVETFRUIT_SPREAD,
                max_take_size=VELVETFRUIT_TAKE_SIZE,
                quote_size=VELVETFRUIT_QUOTE_SIZE,
            )
            return

        order_depth = state.order_depths.get(VELVETFRUIT_EXTRACT)
        if order_depth is None or spot_price is None:
            return

        best_bid, best_ask = self.get_best_bid_ask(order_depth)
        if best_bid is None or best_ask is None:
            return

        spread = float(best_ask - best_bid)
        if not self.spread_is_tradeable(VELVETFRUIT_EXTRACT, spot_price, spread):
            return

        position = self.get_position(state, VELVETFRUIT_EXTRACT)
        limit = self.position_limits.get(VELVETFRUIT_EXTRACT, 0)
        net_voucher_delta = self.estimate_net_voucher_delta(state, spot_price, metrics)
        target_position = int(round(-UNDERLYING_HEDGE_RATIO * net_voucher_delta))
        target_position = max(-limit, min(limit, target_position))
        hedge_gap = target_position - position

        # If voucher inventory needs a hedge, prioritize that over spot alpha.
        if abs(hedge_gap) >= HEDGE_REBALANCE_THRESHOLD:
            if hedge_gap > 0:
                quantity = min(MAX_HEDGE_TRADE_SIZE, hedge_gap, self.buy_room(position, limit))
                if quantity > 0:
                    self.add_order(VELVETFRUIT_EXTRACT, best_ask, quantity)
            else:
                quantity = min(MAX_HEDGE_TRADE_SIZE, -hedge_gap, self.sell_room(position, limit))
                if quantity > 0:
                    self.add_order(VELVETFRUIT_EXTRACT, best_bid, -quantity)
            return

        self.trade_active_spot(
            state=state,
            product=VELVETFRUIT_EXTRACT,
            max_spread=MAX_VELVETFRUIT_SPREAD,
            max_take_size=VELVETFRUIT_TAKE_SIZE,
            quote_size=VELVETFRUIT_QUOTE_SIZE,
        )

    # ------------------------------------------------------------------
    # History updates
    # ------------------------------------------------------------------
    def store_current_observations(
        self,
        hydrogel_mid: Optional[float],
        velvetfruit_mid: Optional[float],
        metrics: Dict[str, Dict[str, float]],
    ) -> None:
        self.append_history(
            self.data["mid_history"].setdefault(HYDROGEL_PACK, []),
            hydrogel_mid,
            MID_HISTORY_LENGTH,
        )
        self.append_history(
            self.data["mid_history"].setdefault(VELVETFRUIT_EXTRACT, []),
            velvetfruit_mid,
            MID_HISTORY_LENGTH,
        )

        for product, info in metrics.items():
            current_iv = self.finite_or_none(info["implied_vol"])
            if current_iv is not None:
                self.append_history(
                    self.data["iv_history"].setdefault(product, []),
                    current_iv,
                    IV_HISTORY_LENGTH,
                )
            self.append_history(
                self.data["tv_history"].setdefault(product, []),
                info["time_value"],
                IV_HISTORY_LENGTH,
            )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def run(self, state: TradingState):
        self.conversions = 0
        self.orders = {product: [] for product in state.order_depths.keys()}
        trader_data = ""

        try:
            self.data = self.load_state(state.traderData)

            hydrogel_mid = self.trade_active_spot(
                state=state,
                product=HYDROGEL_PACK,
                max_spread=MAX_HYDROGEL_SPREAD,
                max_take_size=HYDROGEL_TAKE_SIZE,
                quote_size=HYDROGEL_QUOTE_SIZE,
            )

            velvetfruit_depth = state.order_depths.get(VELVETFRUIT_EXTRACT)
            velvetfruit_mid = self.get_mid_price(velvetfruit_depth)
            voucher_metrics = self.collect_voucher_metrics(state, velvetfruit_mid)
            self.enrich_voucher_metrics(velvetfruit_mid, voucher_metrics)
            self.trade_vouchers(state, velvetfruit_mid, voucher_metrics)
            self.trade_velvetfruit(state, velvetfruit_mid, voucher_metrics)

            self.store_current_observations(hydrogel_mid, velvetfruit_mid, voucher_metrics)
            trader_data = self.dump_state()
            return self.orders, self.conversions, trader_data
        except Exception as exc:
            logger.print("RUN_ERROR", repr(exc))
            logger.print(traceback.format_exc())
            trader_data = state.traderData if isinstance(state.traderData, str) else ""
            return self.orders, self.conversions, trader_data
        finally:
            logger.flush(state, self.orders, self.conversions, trader_data)