"""Round 3 trader version 2.

Changes from v1:
- Disables voucher trading entirely.
- Keeps only the delta-one market-making framework in HYDROGEL_PACK and VELVETFRUIT_EXTRACT.
- This isolates whether the round’s edge comes mainly from the two underlying books.

Backtest performance:
- Day 0: 9,957
- Day 1: 10,896
- Day 2: -1,208
- Total round-3 PnL: 19,646
- Aggregate product PnL:
  HYDROGEL_PACK: 12,800
  VELVETFRUIT_EXTRACT: 6,845
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
- Underlyings alone made money, but they left a meaningful amount on the table versus the better voucher-enabled versions.
"""

from round3_common import make_trader_class

CONFIG = {
    "name": "v2_underlyings_only",
    "trade_vouchers": False,
}

Trader = make_trader_class(CONFIG)
