"""Round 3 trader version 9.

Changes from v1:
- Turns off single-name voucher quoting.
- Trades only aggressive cross-strike spread opportunities using market spread versus fair spread.
- The pair list comes directly from the notebook’s stronger spread candidates.

Backtest performance:
- Day 0: -284
- Day 1: -210
- Day 2: -467
- Total round-3 PnL: -961
- Aggregate product PnL:
  HYDROGEL_PACK: 0
  VELVETFRUIT_EXTRACT: 0
  VEV_4000: 0
  VEV_4500: 0
  VEV_5000: 0
  VEV_5100: 0
  VEV_5200: 0
  VEV_5300: -652
  VEV_5400: -153
  VEV_5500: 84
  VEV_6000: -120
  VEV_6500: -120

Takeaway:
- Spread-only logic was close to flat but still negative. The notebook’s spread signal did not translate well to this naive aggressive execution scheme.
"""

from round3_common import make_trader_class

CONFIG = {
    "name": "v9_spread_pairs_only",
    "trade_underlyings": False,
    "traded_vouchers": [],
    "delta_hedge": {"enabled": False},
    "spread_pairs": [
        {"long": "VEV_4000", "short": "VEV_5300", "threshold": 3.0, "clip": 12},
        {"long": "VEV_5300", "short": "VEV_5400", "threshold": 1.0, "clip": 20},
        {"long": "VEV_5400", "short": "VEV_5500", "threshold": 1.0, "clip": 20},
        {"long": "VEV_5500", "short": "VEV_6000", "threshold": 0.9, "clip": 24},
        {"long": "VEV_6000", "short": "VEV_6500", "threshold": 0.75, "clip": 28},
    ],
}

Trader = make_trader_class(CONFIG)
