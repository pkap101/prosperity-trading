"""Round 3 trader version 18.

Changes from v1:
- Structurally different spread-target trader.
- Trades only two adjacent vertical pairs: VEV_5300/VEV_5400 and VEV_6000/VEV_6500.
- Uses fair spread versus market spread to compute a bounded target spread position, then aggressively rebalances both legs together.
- This is a safer follow-up to the failed broad spread experiments, with hard pair selection and much tighter size caps.

Backtest performance:
- Day 0: -32,170
- Day 1: -45,683
- Day 2: -64,722
- Total round-3 PnL: -142,574
- Aggregate product PnL:
  HYDROGEL_PACK: 0
  VELVETFRUIT_EXTRACT: 0
  VEV_4000: 0
  VEV_4500: 0
  VEV_5000: 0
  VEV_5100: 0
  VEV_5200: 0
  VEV_5300: -41,163
  VEV_5400: -27,218
  VEV_5500: 0
  VEV_6000: -37,096
  VEV_6500: -37,096

Takeaway:
- Even the constrained spread-target version was very bad. The notebook spread signal did not survive naive aggressive execution, and the 6000/6500 pair was especially harmful.
"""

import json
import math
from typing import Dict, List

from datamodel import Order, TradingState
from round3_common import Logger, STATIC_SMILE_LAST_YEAR_AVG, VELVET

logger = Logger()
PAIRS = [
    ("VEV_5300", "VEV_5400", 10),
    ("VEV_6000", "VEV_6500", 12),
]


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_call(spot: float, strike: float, tte_days: float, vol: float) -> float:
    t = max(tte_days / 365.0, 1e-9)
    if spot <= 0 or strike <= 0 or vol <= 0:
        return max(spot - strike, 0.0)
    d1 = (math.log(spot / strike) + 0.5 * vol * vol * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    return spot * norm_cdf(d1) - strike * norm_cdf(d2)


def fair_price(spot: float, strike: float, tte_days: float) -> float:
    m = math.log(spot / strike) / math.sqrt(max(tte_days / 365.0, 1e-9))
    a, b, c = STATIC_SMILE_LAST_YEAR_AVG
    vol = max(0.01, a * m * m + b * m + c)
    return bs_call(spot, strike, tte_days, vol)


def size_from_edge(edge: float, enter: float, full: float, cap: int) -> int:
    sign = -1 if edge > 0 else 1
    abs_edge = abs(edge)
    if abs_edge <= enter:
        return 0
    if abs_edge >= full:
        return sign * cap
    frac = (abs_edge - enter) / (full - enter)
    return sign * int(round(cap * frac * frac))


class Trader:
    def run(self, state: TradingState):
        orders: Dict[str, List[Order]] = {product: [] for product in state.order_depths}
        velvet = state.order_depths.get(VELVET)
        if velvet is None or not velvet.buy_orders or not velvet.sell_orders:
            trader_data = state.traderData if state.traderData else "{}"
            logger.flush(state, orders, 0, trader_data)
            return orders, 0, trader_data

        spot = (max(velvet.buy_orders) + min(velvet.sell_orders)) / 2.0
        tte_days = max(0.25, 5.0 - state.timestamp / 1_000_000.0)
        for long_product, short_product, cap in PAIRS:
            long_depth = state.order_depths.get(long_product)
            short_depth = state.order_depths.get(short_product)
            if long_depth is None or short_depth is None:
                continue
            if not long_depth.buy_orders or not long_depth.sell_orders or not short_depth.buy_orders or not short_depth.sell_orders:
                continue
            long_mid = (max(long_depth.buy_orders) + min(long_depth.sell_orders)) / 2.0
            short_mid = (max(short_depth.buy_orders) + min(short_depth.sell_orders)) / 2.0
            fair_spread = fair_price(spot, float(long_product.split("_")[1]), tte_days) - fair_price(spot, float(short_product.split("_")[1]), tte_days)
            market_spread = long_mid - short_mid
            edge = market_spread - fair_spread
            target = size_from_edge(edge, 0.75, 2.0, cap)
            current = state.position.get(long_product, 0) - state.position.get(short_product, 0)
            delta = target - current
            if delta > 0:
                qty = min(delta, -long_depth.sell_orders[min(long_depth.sell_orders)], short_depth.buy_orders[max(short_depth.buy_orders)], 4)
                if qty > 0:
                    orders[long_product].append(Order(long_product, min(long_depth.sell_orders), int(qty)))
                    orders[short_product].append(Order(short_product, max(short_depth.buy_orders), int(-qty)))
            elif delta < 0:
                qty = min(-delta, long_depth.buy_orders[max(long_depth.buy_orders)], -short_depth.sell_orders[min(short_depth.sell_orders)], 4)
                if qty > 0:
                    orders[long_product].append(Order(long_product, max(long_depth.buy_orders), int(-qty)))
                    orders[short_product].append(Order(short_product, min(short_depth.sell_orders), int(qty)))
            logger.print(long_product, short_product, "edge", round(edge, 4), "target", target)

        trader_data = json.dumps({}, separators=(",", ":"))
        logger.flush(state, orders, 0, trader_data)
        return orders, 0, trader_data
