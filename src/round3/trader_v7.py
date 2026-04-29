"""Round 3 trader version 7.

Changes from v1:
- Replaces the adaptive local-plus-EMA voucher anchor with a pure static smile.
- The static coefficients are the average of the bid and ask smile coefficients from one of the strong 2025 round-3 voucher teams supplied by the user.
- This is the cleanest copy-inspired outright voucher baseline.

Backtest performance:
- Day 0: 13,064
- Day 1: 14,026
- Day 2: 2,164
- Total round-3 PnL: 29,254
- Aggregate product PnL:
  HYDROGEL_PACK: 12,800
  VELVETFRUIT_EXTRACT: 6,845
  VEV_4000: 9,927
  VEV_4500: 0
  VEV_5000: 0
  VEV_5100: 0
  VEV_5200: 0
  VEV_5300: -564
  VEV_5400: 66
  VEV_5500: 51
  VEV_6000: 57
  VEV_6500: 71

Takeaway:
- This was the best first-pass version. The static smile stabilized the middle and far strikes while materially improving VEV_4000 performance versus the original baseline.
"""

from round3_common import ACTIVE_VOUCHERS, STATIC_SMILE_LAST_YEAR_AVG, make_trader_class

CONFIG = {
    "name": "v7_static_smile_copy_avg",
    "traded_vouchers": ACTIVE_VOUCHERS,
    "anchor_weights": {"local": 0.0, "ema": 0.0, "static": 1.0},
    "static_smile_coeffs": STATIC_SMILE_LAST_YEAR_AVG,
    "voucher_cfg": {
        "VEV_4000": {"max_abs_pos": 70, "take_width": 7.0, "quote_edge": 2.5, "quote_size": 24},
        "VEV_5300": {"max_abs_pos": 70, "take_width": 2.0, "quote_edge": 1.0, "quote_size": 24},
        "VEV_5400": {"max_abs_pos": 70, "take_width": 2.0, "quote_edge": 1.0, "quote_size": 24},
        "VEV_5500": {"max_abs_pos": 70, "take_width": 2.0, "quote_edge": 1.0, "quote_size": 24},
        "VEV_6000": {"max_abs_pos": 90, "take_width": 1.25, "quote_edge": 0.5, "quote_size": 24, "side_mode": "both"},
        "VEV_6500": {"max_abs_pos": 90, "take_width": 1.25, "quote_edge": 0.5, "quote_size": 24, "side_mode": "both"},
    },
}

Trader = make_trader_class(CONFIG)
