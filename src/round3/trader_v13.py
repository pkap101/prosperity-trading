"""Round 3 trader version 13.

Changes from v1:
- Trades only VEV_4000.
- Disables underlyings and hedging.
- This is the cleanest single-name voucher isolation version.

Backtest performance:
- Day 0: 2,996
- Day 1: 3,284
- Day 2: 2,437
- Total round-3 PnL: 8,717
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
  VEV_5500: 0
  VEV_6000: 0
  VEV_6500: 0

Takeaway:
- The single-name VEV_4000 hypothesis was real. On its own, it produced solid positive PnL without any help from the underlying books.
"""

from round3_common import make_trader_class

CONFIG = {
    "name": "v13_4000_only",
    "trade_underlyings": False,
    "traded_vouchers": ["VEV_4000"],
    "delta_hedge": {"enabled": False},
    "voucher_cfg": {
        "VEV_4000": {"max_abs_pos": 120, "take_width": 5.5, "quote_edge": 2.0, "quote_size": 35},
    },
}

Trader = make_trader_class(CONFIG)
