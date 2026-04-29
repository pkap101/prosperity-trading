"""Round 3 trader version 19.

Changes from v1:
- Structurally different underlying-only predictor inspired by the 2025 KELP trader architecture that used adverse-volume levels and a retreat-based theo.
- Trades HYDROGEL_PACK and VELVETFRUIT_EXTRACT only.
- Builds a simple mmbot bid/ask, predicts a one-step mean-reverting fair price, then sizes quotes off the edge to that fair value.
- No voucher logic at all.

Backtest performance:
- Day 0: 15,118
- Day 1: 15,002
- Day 2: 3,577
- Total round-3 PnL: 33,697
- Aggregate product PnL:
  HYDROGEL_PACK: 23,634
  VELVETFRUIT_EXTRACT: 10,063
  VEV_4000: 0
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
- This was the best version overall. A genuinely different underlying architecture beat every voucher-heavy design tested so far, which materially changes the current hypothesis about where the real round edge is.
"""

import json
import math
from typing import Dict, List

from datamodel import Order, OrderDepth, TradingState
from round3_common import HYDRO, Logger, POSITION_LIMITS, VELVET

logger = Logger()


def mm_bot_prices(depth: OrderDepth, adverse_threshold: int) -> tuple[int, int] | tuple[None, None]:
    if not depth.buy_orders or not depth.sell_orders:
        return None, None
    buy_levels = sorted(depth.buy_orders.items(), reverse=True)
    sell_levels = sorted(depth.sell_orders.items())
    mm_bid = buy_levels[0][0]
    mm_ask = sell_levels[0][0]
    for price, volume in buy_levels[:3]:
        if volume >= adverse_threshold:
            mm_bid = price
            break
    for price, volume in sell_levels[:3]:
        if -volume >= adverse_threshold:
            mm_ask = price
            break
    return mm_bid, mm_ask


class Trader:
    def run(self, state: TradingState):
        try:
            memory = json.loads(state.traderData) if state.traderData else {}
            if not isinstance(memory, dict):
                memory = {}
        except Exception:
            memory = {}
        memory.setdefault("prev_mid", {})

        orders: Dict[str, List[Order]] = {product: [] for product in state.order_depths}
        params = {
            HYDRO: {"threshold": 18, "retreat": 0.04, "edge_per_lot": 0.18, "cap": 80, "revert": -0.22},
            VELVET: {"threshold": 15, "retreat": 0.03, "edge_per_lot": 0.12, "cap": 90, "revert": -0.18},
        }
        for product in [HYDRO, VELVET]:
            depth = state.order_depths.get(product)
            if depth is None:
                continue
            mm_bid, mm_ask = mm_bot_prices(depth, params[product]["threshold"])
            if mm_bid is None or mm_ask is None:
                continue
            current_mid = (mm_bid + mm_ask) / 2.0
            prev_mid = memory["prev_mid"].get(product, current_mid)
            log_ret = math.log(max(current_mid, 1.0) / max(prev_mid, 1.0))
            pred_mid = current_mid * math.exp(params[product]["revert"] * log_ret)
            pos = state.position.get(product, 0)
            theo = pred_mid - params[product]["retreat"] * pos
            buy_price = min(int(math.floor(theo)), max(depth.buy_orders) + 1)
            sell_price = max(int(math.ceil(theo)), min(depth.sell_orders) - 1)
            bid_edge = theo - buy_price
            ask_edge = sell_price - theo
            buy_qty = int(max(0.0, bid_edge / params[product]["edge_per_lot"]))
            sell_qty = int(max(0.0, ask_edge / params[product]["edge_per_lot"]))
            buy_qty = min(buy_qty, params[product]["cap"], POSITION_LIMITS[product] - pos)
            sell_qty = min(sell_qty, params[product]["cap"], POSITION_LIMITS[product] + pos)
            if buy_qty > 0:
                orders[product].append(Order(product, buy_price, int(buy_qty)))
            if sell_qty > 0 and sell_price > buy_price:
                orders[product].append(Order(product, sell_price, int(-sell_qty)))
            memory["prev_mid"][product] = current_mid
            logger.print(product, "theo", round(theo, 3), "mid", round(current_mid, 3), "pos", pos)

        trader_data = json.dumps(memory, separators=(",", ":"))
        logger.flush(state, orders, 0, trader_data)
        return orders, 0, trader_data
