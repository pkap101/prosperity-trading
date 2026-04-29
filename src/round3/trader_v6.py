"""Round 3 trader version 6.

Changes from v1:
- Concentrates only on VEV_4000 and VEV_5500.
- Removes the far OTM bid-only legs entirely.
- Disables delta hedging to test whether concentration alone improves realized PnL.

Backtest performance:
- Day 0: 13,000
- Day 1: 14,092
- Day 2: 966
- Total round-3 PnL: 28,058
- Aggregate product PnL:
  HYDROGEL_PACK: 12,800
  VELVETFRUIT_EXTRACT: 6,845
  VEV_4000: 8,717
  VEV_4500: 0
  VEV_5000: 0
  VEV_5100: 0
  VEV_5200: 0
  VEV_5300: 0
  VEV_5400: 0
  VEV_5500: -305
  VEV_6000: 0
  VEV_6500: 0

Takeaway:
- Concentration helped. VEV_4000 remained strong and removing the harmful VEV_6500 leg was immediately beneficial, though VEV_5500 was still slightly net negative.
"""

from round3_common import make_trader_class

CONFIG = {
    "name": "v6_concentrated_4000_5500",
    "traded_vouchers": ["VEV_4000", "VEV_5500"],
    "delta_hedge": {"enabled": False},
    "voucher_cfg": {
        "VEV_4000": {"max_abs_pos": 80, "take_width": 7.0, "quote_edge": 2.5, "quote_size": 25},
        "VEV_5500": {"max_abs_pos": 100, "take_width": 1.75, "quote_edge": 0.75, "quote_size": 35},
    },
}

Trader = make_trader_class(CONFIG)
