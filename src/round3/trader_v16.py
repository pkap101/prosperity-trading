"""Round 3 trader version 16.

Changes from v1:
- Structurally different voucher market maker inspired by the 2025 team that quoted bid and ask from separate implied-vol curves.
- No delta-one alpha in HYDROGEL_PACK or VELVETFRUIT_EXTRACT.
- Quotes all active vouchers off static-smile bid/ask envelopes and takes crossed opportunities.
- Adds a simple current-position delta hedge in VELVETFRUIT_EXTRACT.

Backtest performance:
- Day 0: -886
- Day 1: -1,238
- Day 2: -990
- Total round-3 PnL: -3,114
- Aggregate product PnL:
  HYDROGEL_PACK: 0
  VELVETFRUIT_EXTRACT: -11,333
  VEV_4000: 8,706
  VEV_4500: 0
  VEV_5000: 0
  VEV_5100: 0
  VEV_5200: 0
  VEV_5300: -553
  VEV_5400: 66
  VEV_5500: 0
  VEV_6000: 75
  VEV_6500: -75

Takeaway:
- The voucher quoting logic itself was respectable, but the hedge implementation was too costly and wiped out the edge. This is a useful negative result: copying the quote architecture without better hedge design is not enough.
"""

import json
import math
from typing import Dict, List

from datamodel import Order, TradingState
from round3_common import ACTIVE_VOUCHERS, Logger, POSITION_LIMITS, STATIC_SMILE_LAST_YEAR_AVG, VELVET

logger = Logger()


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_call(spot: float, strike: float, tte_days: float, vol: float) -> float:
    t = max(tte_days / 365.0, 1e-9)
    if spot <= 0 or strike <= 0 or vol <= 0:
        return max(spot - strike, 0.0)
    d1 = (math.log(spot / strike) + 0.5 * vol * vol * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    return spot * norm_cdf(d1) - strike * norm_cdf(d2)


def call_delta(spot: float, strike: float, tte_days: float, vol: float) -> float:
    t = max(tte_days / 365.0, 1e-9)
    if spot <= 0 or strike <= 0 or vol <= 0:
        return 1.0 if spot > strike else 0.0
    d1 = (math.log(spot / strike) + 0.5 * vol * vol * t) / (vol * math.sqrt(t))
    return norm_cdf(d1)


def book_spot(state: TradingState) -> float | None:
    depth = state.order_depths.get(VELVET)
    if depth is None or not depth.buy_orders or not depth.sell_orders:
        return None
    best_bid = max(depth.buy_orders)
    best_ask = min(depth.sell_orders)
    return (best_bid + best_ask) / 2.0


class Trader:
    def run(self, state: TradingState):
        orders: Dict[str, List[Order]] = {product: [] for product in state.order_depths}
        spot = book_spot(state)
        if spot is None:
            trader_data = state.traderData if state.traderData else "{}"
            logger.flush(state, orders, 0, trader_data)
            return orders, 0, trader_data

        tte_days = max(0.25, 5.0 - state.timestamp / 1_000_000.0)
        total_delta = 0.0
        for product in ACTIVE_VOUCHERS:
            depth = state.order_depths.get(product)
            if depth is None or not depth.buy_orders or not depth.sell_orders:
                continue
            strike = float(product.split("_")[1])
            m = math.log(spot / strike) / math.sqrt(max(tte_days / 365.0, 1e-9))
            a, b, c = STATIC_SMILE_LAST_YEAR_AVG
            base_vol = max(0.01, a * m * m + b * m + c)
            bid_vol = max(0.01, base_vol - 0.01 - 0.015 * abs(m))
            ask_vol = max(0.01, base_vol + 0.01 + 0.015 * abs(m))
            model_bid = int(math.floor(bs_call(spot, strike, tte_days, bid_vol)))
            model_ask = int(math.ceil(bs_call(spot, strike, tte_days, ask_vol)))
            best_bid = max(depth.buy_orders)
            best_ask = min(depth.sell_orders)
            pos = state.position.get(product, 0)
            cap = 70 if strike < 5600 else 50
            buy_room = max(0, cap - pos)
            sell_room = max(0, cap + pos)
            sent_buy = 0
            sent_sell = 0

            if model_bid > best_ask and buy_room > 0:
                qty = min(buy_room, -depth.sell_orders[best_ask])
                if qty > 0:
                    orders[product].append(Order(product, best_ask, int(qty)))
                    sent_buy += qty
            if model_ask < best_bid and sell_room > 0:
                qty = min(sell_room, depth.buy_orders[best_bid])
                if qty > 0:
                    orders[product].append(Order(product, best_bid, int(-qty)))
                    sent_sell += qty

            quote_buy = max(0, min(model_bid, best_bid + 1 if best_bid + 1 < best_ask else model_bid))
            quote_sell = max(quote_buy + 1, max(model_ask, best_ask - 1 if best_ask - 1 > best_bid else model_ask))
            quote_size = max(8, cap // 3)
            buy_qty = min(quote_size, max(0, buy_room - sent_buy))
            sell_qty = min(quote_size, max(0, sell_room - sent_sell))
            if buy_qty > 0:
                orders[product].append(Order(product, quote_buy, int(buy_qty)))
            if sell_qty > 0:
                orders[product].append(Order(product, quote_sell, int(-sell_qty)))

            delta = call_delta(spot, strike, tte_days, base_vol)
            total_delta += delta * pos
            logger.print(product, "bid_ask", model_bid, model_ask, "pos", pos)

        if VELVET in state.order_depths and state.order_depths[VELVET].buy_orders and state.order_depths[VELVET].sell_orders:
            hedge_target = int(round(-0.35 * total_delta))
            current = state.position.get(VELVET, 0)
            delta_qty = hedge_target - current
            if delta_qty > 0:
                best_ask = min(state.order_depths[VELVET].sell_orders)
                orders[VELVET].append(Order(VELVET, best_ask, int(min(delta_qty, 40))))
            elif delta_qty < 0:
                best_bid = max(state.order_depths[VELVET].buy_orders)
                orders[VELVET].append(Order(VELVET, best_bid, int(max(delta_qty, -40))))

        trader_data = json.dumps({}, separators=(",", ":"))
        logger.flush(state, orders, 0, trader_data)
        return orders, 0, trader_data
