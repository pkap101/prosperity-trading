"""Round 3 trader version 15.

Changes from v1:
- Structurally different target-position strategy.
- Trades only VEV_4000.
- Uses a static smile prior and maps IV mispricing directly into a target position instead of market making around a fair price.
- Inspired by the target-leaf sizing style from one of the 2025 top-team voucher traders.

Backtest performance:
- Day 0: -3,219
- Day 1: 364
- Day 2: 2,326
- Total round-3 PnL: -529
- Aggregate product PnL:
  HYDROGEL_PACK: 0
  VELVETFRUIT_EXTRACT: 0
  VEV_4000: -529
  VEV_4500: 0
  VEV_5000: 0
  VEV_5100: 0
  VEV_5200: 0
  VEV_5300: 0
  VEV_5400: 0
  VEV_5500: 0
  VEV_6000: 0
  VEV_6500: 0

Takeaway:
- The target-position idea on a single static-smile VEV_4000 signal was not robust. It recovered late, but the day-0 drawdown was enough to make it slightly negative overall.
"""

import json
import math
from typing import Any, Dict, List

from datamodel import Order, TradingState
from round3_common import Logger, POSITION_LIMITS, STATIC_SMILE_LAST_YEAR_AVG, VELVET

logger = Logger()
VOUCHER = "VEV_4000"


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_call(spot: float, strike: float, tte_days: float, vol: float) -> float:
    t = max(tte_days / 365.0, 1e-9)
    if spot <= 0 or strike <= 0 or vol <= 0:
        return max(spot - strike, 0.0)
    d1 = (math.log(spot / strike) + 0.5 * vol * vol * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    return spot * norm_cdf(d1) - strike * norm_cdf(d2)


def implied_vol(price: float, spot: float, strike: float, tte_days: float) -> float | None:
    intrinsic = max(spot - strike, 0.0)
    if price <= intrinsic + 1e-9:
        return None
    low, high = 1e-4, 3.0
    for _ in range(80):
        mid = 0.5 * (low + high)
        if bs_call(spot, strike, tte_days, mid) > price:
            high = mid
        else:
            low = mid
    return 0.5 * (low + high)


def book_spot(state: TradingState) -> float | None:
    depth = state.order_depths.get(VELVET)
    if depth is None or not depth.buy_orders or not depth.sell_orders:
        return None
    best_bid = max(depth.buy_orders)
    best_ask = min(depth.sell_orders)
    bid_vol = depth.buy_orders[best_bid]
    ask_vol = -depth.sell_orders[best_ask]
    total = bid_vol + ask_vol
    if total <= 0:
        return (best_bid + best_ask) / 2.0
    micro = (best_bid * ask_vol + best_ask * bid_vol) / total
    return 0.7 * micro + 0.3 * ((best_bid + best_ask) / 2.0)


def target_size(signal: float, enter: float, full: float, cap: int) -> int:
    abs_signal = abs(signal)
    if abs_signal <= enter:
        return 0
    if abs_signal >= full:
        size = cap
    else:
        frac = (abs_signal - enter) / (full - enter)
        size = int(round(cap * frac * frac))
    return -size if signal > 0 else size


class Trader:
    def run(self, state: TradingState):
        orders: Dict[str, List[Order]] = {product: [] for product in state.order_depths}
        spot = book_spot(state)
        if spot is None or VOUCHER not in state.order_depths:
            trader_data = state.traderData if state.traderData else "{}"
            logger.flush(state, orders, 0, trader_data)
            return orders, 0, trader_data

        depth = state.order_depths[VOUCHER]
        if not depth.buy_orders or not depth.sell_orders:
            trader_data = state.traderData if state.traderData else "{}"
            logger.flush(state, orders, 0, trader_data)
            return orders, 0, trader_data

        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        mid = (best_bid + best_ask) / 2.0
        strike = 4000.0
        tte_days = max(0.25, 5.0 - state.timestamp / 1_000_000.0)
        current_iv = implied_vol(mid, spot, strike, tte_days)
        if current_iv is not None:
            m = math.log(spot / strike) / math.sqrt(max(tte_days / 365.0, 1e-9))
            a, b, c = STATIC_SMILE_LAST_YEAR_AVG
            fair_iv = max(0.01, a * m * m + b * m + c)
            signal = current_iv - fair_iv
            target = target_size(signal, 0.01, 0.04, 180)
            position = state.position.get(VOUCHER, 0)
            delta = target - position
            if delta > 0:
                qty = min(delta, -depth.sell_orders[best_ask], POSITION_LIMITS[VOUCHER] - position)
                if qty > 0:
                    orders[VOUCHER].append(Order(VOUCHER, best_ask, int(qty)))
            elif delta < 0:
                qty = min(-delta, depth.buy_orders[best_bid], POSITION_LIMITS[VOUCHER] + position)
                if qty > 0:
                    orders[VOUCHER].append(Order(VOUCHER, best_bid, int(-qty)))
            logger.print("signal", round(signal, 6), "target", target, "pos", position)

        trader_data = json.dumps({}, separators=(",", ":"))
        logger.flush(state, orders, 0, trader_data)
        return orders, 0, trader_data
