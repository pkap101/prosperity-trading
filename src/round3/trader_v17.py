"""Round 3 trader version 17.

Changes from v1:
- Structurally different rolling-IV z-score strategy.
- Trades a small voucher set by mapping each strike’s current IV versus its own rolling history into a target position.
- No passive market making; it only rebalances toward target inventory at the touch.
- Inspired by the z-score voucher style from one of the user-provided 2025 Round 3 files.

Backtest performance:
- Day 0: -43,016
- Day 1: -45,844
- Day 2: -46,415
- Total round-3 PnL: -135,275
- Aggregate product PnL:
  HYDROGEL_PACK: 0
  VELVETFRUIT_EXTRACT: 0
  VEV_4000: -16,155
  VEV_4500: 0
  VEV_5000: 0
  VEV_5100: 0
  VEV_5200: 0
  VEV_5300: 0
  VEV_5400: 0
  VEV_5500: -53,540
  VEV_6000: -65,580
  VEV_6500: 0

Takeaway:
- This failed decisively. Raw rolling-IV z-scores without cross-sectional context or better execution control were badly unstable, especially in VEV_5500 and VEV_6000.
"""

import json
import math
from statistics import mean, pstdev
from typing import Any, Dict, List

from datamodel import Order, TradingState
from round3_common import Logger, POSITION_LIMITS, VELVET

logger = Logger()
TRADED = ["VEV_4000", "VEV_5500", "VEV_6000"]
WINDOW = 25


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_call(spot: float, strike: float, tte_days: float, vol: float) -> float:
    t = max(tte_days / 365.0, 1e-9)
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
    return (max(depth.buy_orders) + min(depth.sell_orders)) / 2.0


def size_from_z(z: float, cap: int) -> int:
    abs_z = abs(z)
    if abs_z < 1.2:
        return 0
    if abs_z > 3.0:
        size = cap
    else:
        size = int(round(cap * ((abs_z - 1.2) / 1.8) ** 2))
    return -size if z > 0 else size


class Trader:
    def run(self, state: TradingState):
        try:
            memory = json.loads(state.traderData) if state.traderData else {}
            if not isinstance(memory, dict):
                memory = {}
        except Exception:
            memory = {}
        memory.setdefault("iv_hist", {})

        orders: Dict[str, List[Order]] = {product: [] for product in state.order_depths}
        spot = book_spot(state)
        if spot is None:
            trader_data = json.dumps(memory, separators=(",", ":"))
            logger.flush(state, orders, 0, trader_data)
            return orders, 0, trader_data

        tte_days = max(0.25, 5.0 - state.timestamp / 1_000_000.0)
        for product in TRADED:
            depth = state.order_depths.get(product)
            if depth is None or not depth.buy_orders or not depth.sell_orders:
                continue
            strike = float(product.split("_")[1])
            mid = (max(depth.buy_orders) + min(depth.sell_orders)) / 2.0
            iv = implied_vol(mid, spot, strike, tte_days)
            if iv is None:
                continue
            hist = memory["iv_hist"].setdefault(product, [])
            hist.append(iv)
            if len(hist) > WINDOW:
                hist.pop(0)
            if len(hist) < WINDOW:
                continue
            mu = mean(hist)
            sigma = pstdev(hist)
            if sigma < 1e-6:
                continue
            z = (iv - mu) / sigma
            target = size_from_z(z, 120 if product == "VEV_4000" else 80)
            pos = state.position.get(product, 0)
            delta = target - pos
            best_bid = max(depth.buy_orders)
            best_ask = min(depth.sell_orders)
            if delta > 0:
                qty = min(delta, -depth.sell_orders[best_ask], POSITION_LIMITS[product] - pos)
                if qty > 0:
                    orders[product].append(Order(product, best_ask, int(qty)))
            elif delta < 0:
                qty = min(-delta, depth.buy_orders[best_bid], POSITION_LIMITS[product] + pos)
                if qty > 0:
                    orders[product].append(Order(product, best_bid, int(-qty)))
            logger.print(product, "z", round(z, 4), "target", target, "pos", pos)

        trader_data = json.dumps(memory, separators=(",", ":"))
        logger.flush(state, orders, 0, trader_data)
        return orders, 0, trader_data
