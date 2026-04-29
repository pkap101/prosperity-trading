"""Round 3 trader version 20.

Changes from v1:
- Structurally different local-residual z-score strategy.
- Fits a fresh local smile each timestamp, converts each voucher’s price residual versus local fair into a rolling z-score, and trades only when that residual is extreme for that specific strike.
- No passive quoting; this is a pure residual mean-reversion rebalance design.
- This comes directly from the notebook idea that local-smile residuals may matter more than raw implied vol level.

Backtest performance:
- Day 0: -65,555
- Day 1: -68,737
- Day 2: -72,047
- Total round-3 PnL: -206,339
- Aggregate product PnL:
  HYDROGEL_PACK: 0
  VELVETFRUIT_EXTRACT: 0
  VEV_4000: -13,339
  VEV_4500: 0
  VEV_5000: 0
  VEV_5100: 0
  VEV_5200: 0
  VEV_5300: -84,336
  VEV_5400: -54,788
  VEV_5500: -53,876
  VEV_6000: 0
  VEV_6500: 0

Takeaway:
- This was a strong rejection of the pure residual-zscore hypothesis in executable form. The middle strikes were overwhelmingly harmful under aggressive residual rebalancing.
"""

import json
import math
from statistics import mean, pstdev
from typing import Dict, List

from datamodel import Order, TradingState
from round3_common import ACTIVE_VOUCHERS, Logger, POSITION_LIMITS, VELVET

logger = Logger()
WINDOW = 30
TRADED = ["VEV_4000", "VEV_5300", "VEV_5400", "VEV_5500"]


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


def fit_quadratic(xs: List[float], ys: List[float]) -> tuple[float, float, float]:
    n = float(len(xs))
    sx = sum(xs)
    sx2 = sum(x * x for x in xs)
    sx3 = sum(x * x * x for x in xs)
    sx4 = sum(x * x * x * x for x in xs)
    sy = sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sx2y = sum((x * x) * y for x, y in zip(xs, ys))
    a = [[sx4, sx3, sx2], [sx3, sx2, sx], [sx2, sx, n]]
    b = [sx2y, sxy, sy]
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


class Trader:
    def run(self, state: TradingState):
        try:
            memory = json.loads(state.traderData) if state.traderData else {}
            if not isinstance(memory, dict):
                memory = {}
        except Exception:
            memory = {}
        memory.setdefault("resid_hist", {})

        orders: Dict[str, List[Order]] = {product: [] for product in state.order_depths}
        velvet = state.order_depths.get(VELVET)
        if velvet is None or not velvet.buy_orders or not velvet.sell_orders:
            trader_data = json.dumps(memory, separators=(",", ":"))
            logger.flush(state, orders, 0, trader_data)
            return orders, 0, trader_data

        spot = (max(velvet.buy_orders) + min(velvet.sell_orders)) / 2.0
        tte_days = max(0.25, 5.0 - state.timestamp / 1_000_000.0)
        xs: List[float] = []
        ys: List[float] = []
        mids: Dict[str, float] = {}
        strikes: Dict[str, float] = {}
        for product in ACTIVE_VOUCHERS:
            depth = state.order_depths.get(product)
            if depth is None or not depth.buy_orders or not depth.sell_orders:
                continue
            strike = float(product.split("_")[1])
            mid = (max(depth.buy_orders) + min(depth.sell_orders)) / 2.0
            iv = implied_vol(mid, spot, strike, tte_days)
            if iv is None:
                continue
            m = math.log(spot / strike) / math.sqrt(max(tte_days / 365.0, 1e-9))
            xs.append(m)
            ys.append(iv)
            mids[product] = mid
            strikes[product] = strike
        if len(xs) < 3:
            trader_data = json.dumps(memory, separators=(",", ":"))
            logger.flush(state, orders, 0, trader_data)
            return orders, 0, trader_data

        a, b, c = fit_quadratic(xs, ys)
        for product in TRADED:
            if product not in mids:
                continue
            depth = state.order_depths[product]
            strike = strikes[product]
            m = math.log(spot / strike) / math.sqrt(max(tte_days / 365.0, 1e-9))
            fair_iv = max(0.01, a * m * m + b * m + c)
            fair_price = bs_call(spot, strike, tte_days, fair_iv)
            resid = mids[product] - fair_price
            hist = memory["resid_hist"].setdefault(product, [])
            hist.append(resid)
            if len(hist) > WINDOW:
                hist.pop(0)
            if len(hist) < WINDOW:
                continue
            sigma = pstdev(hist)
            if sigma < 1e-6:
                continue
            z = (resid - mean(hist)) / sigma
            cap = 100 if product == "VEV_4000" else 60
            target = 0
            if abs(z) > 1.5:
                target = (-1 if z > 0 else 1) * min(cap, int(round(cap * min(1.0, (abs(z) - 1.5) / 1.5))))
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
            logger.print(product, "resid_z", round(z, 4), "target", target)

        trader_data = json.dumps(memory, separators=(",", ":"))
        logger.flush(state, orders, 0, trader_data)
        return orders, 0, trader_data
