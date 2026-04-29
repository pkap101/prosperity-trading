"""Round 3 trader version 3.

Changes from v1:
- Disables delta-one alpha in both underlyings.
- Trades only the voucher book with the same blended local-plus-EMA anchor as v1.
- Disables delta hedging so the result reflects pure voucher selection and execution.

Backtest performance:
- Day 0: 2,604
- Day 1: 2,355
- Day 2: 1,540
- Total round-3 PnL: 6,499
- Aggregate product PnL:
  HYDROGEL_PACK: 0
  VELVETFRUIT_EXTRACT: 0
  VEV_4000: 8,717
  VEV_4500: 0
  VEV_5000: 0
  VEV_5100: 0
  VEV_5200: 0
  VEV_5300: 0
  VEV_5400: 0
  VEV_5500: 103
  VEV_6000: 0
  VEV_6500: -2,321

Takeaway:
- Pure voucher trading worked, but mostly because VEV_4000 carried the book. The rest of the baseline voucher set did not justify themselves.
"""

from round3_common import make_trader_class

CONFIG = {
    "name": "v3_vouchers_only_unhedged",
    "trade_underlyings": False,
    "delta_hedge": {"enabled": False},
}

Trader = make_trader_class(CONFIG)
