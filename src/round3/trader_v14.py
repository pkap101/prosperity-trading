"""Round 3 trader version 14.

Changes from v1:
- Focuses on the middle strike cluster VEV_5300, VEV_5400, and VEV_5500.
- Uses local-only smile fitting and adds tight spread-pair overlays between adjacent strikes.
- Intended to probe whether the middle of the surface offers cleaner relative-value opportunities than the tails.

Backtest performance:
- Day 0: -206,650
- Day 1: -333,176
- Day 2: -352,535
- Total round-3 PnL: -892,361
- Aggregate product PnL:
  HYDROGEL_PACK: 0
  VELVETFRUIT_EXTRACT: 0
  VEV_4000: 0
  VEV_4500: 0
  VEV_5000: 0
  VEV_5100: 0
  VEV_5200: 0
  VEV_5300: -376,896
  VEV_5400: -364,443
  VEV_5500: -151,023
  VEV_6000: 0
  VEV_6500: 0

Takeaway:
- This blew up completely. The middle-cluster spread overlay is not safe in its current form and should not be reused without explicit inventory and spread-position controls.
"""

from round3_common import make_trader_class

CONFIG = {
    "name": "v14_mid_cluster_local_spreads",
    "trade_underlyings": False,
    "traded_vouchers": ["VEV_5300", "VEV_5400", "VEV_5500"],
    "anchor_weights": {"local": 1.0, "ema": 0.0, "static": 0.0},
    "delta_hedge": {"enabled": False},
    "spread_pairs": [
        {"long": "VEV_5300", "short": "VEV_5400", "threshold": 0.85, "clip": 18},
        {"long": "VEV_5400", "short": "VEV_5500", "threshold": 0.85, "clip": 18},
    ],
    "voucher_cfg": {
        "VEV_5300": {"max_abs_pos": 90, "take_width": 1.5, "quote_edge": 0.5, "quote_size": 28},
        "VEV_5400": {"max_abs_pos": 90, "take_width": 1.5, "quote_edge": 0.5, "quote_size": 28},
        "VEV_5500": {"max_abs_pos": 90, "take_width": 1.5, "quote_edge": 0.5, "quote_size": 28},
    },
}

Trader = make_trader_class(CONFIG)
