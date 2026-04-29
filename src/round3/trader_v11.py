"""Round 3 trader version 11.

Changes from v1:
- Makes the underlying market-making layer materially more aggressive.
- Keeps voucher participation modest and removes the weakest-looking far OTM name from the baseline set.
- Tests whether the main edge may be in HYDROGEL_PACK and VELVETFRUIT_EXTRACT, with vouchers as a secondary add-on.

Backtest performance:
- Day 0: 12,688
- Day 1: 11,746
- Day 2: -706
- Total round-3 PnL: 23,728
- Aggregate product PnL:
  HYDROGEL_PACK: 9,045
  VELVETFRUIT_EXTRACT: 5,740
  VEV_4000: 8,717
  VEV_4500: 0
  VEV_5000: 0
  VEV_5100: 0
  VEV_5200: 0
  VEV_5300: 0
  VEV_5400: 0
  VEV_5500: 226
  VEV_6000: 0
  VEV_6500: 0

Takeaway:
- This underperformed the baseline. More aggressive underlying quoting hurt HYDROGEL_PACK and did not compensate with better voucher PnL.
"""

from round3_common import HYDRO, VELVET, make_trader_class

CONFIG = {
    "name": "v11_underlying_aggressive_core_vouchers",
    "traded_vouchers": ["VEV_4000", "VEV_5500", "VEV_6000"],
    "delta_one_cfg": {
        HYDRO: {"signal_weight": 1.5, "take_width": 3.0, "make_edge": 3.0, "max_quote": 70},
        VELVET: {"signal_weight": 1.2, "take_width": 1.5, "make_edge": 1.0, "max_quote": 80},
    },
    "voucher_cfg": {
        "VEV_4000": {"max_abs_pos": 50, "take_width": 8.5, "quote_edge": 3.5, "quote_size": 18},
        "VEV_5500": {"max_abs_pos": 70, "take_width": 2.0, "quote_edge": 1.0, "quote_size": 18},
        "VEV_6000": {"max_abs_pos": 90, "take_width": 1.25, "quote_edge": 0.5, "quote_size": 18, "side_mode": "bid"},
    },
}

Trader = make_trader_class(CONFIG)
