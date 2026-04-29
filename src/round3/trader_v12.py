"""Round 3 trader version 12.

Changes from v1:
- Focuses on the passive-fill asymmetry observation for far OTM vouchers.
- Trades only VEV_5500, VEV_6000, and VEV_6500, with VEV_6000 and VEV_6500 constrained to bid-side accumulation and conditional clearing.
- Keeps the rest of the system conservative.

Backtest performance:
- Day 0: 9,565
- Day 1: 10,002
- Day 2: -2,022
- Total round-3 PnL: 17,546
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
  VEV_5500: 222
  VEV_6000: 0
  VEV_6500: -2,321

Takeaway:
- The bid-heavy far OTM idea did not carry on its own. The configuration lost too much by dropping VEV_4000 while still retaining VEV_6500 drag.
"""

from round3_common import make_trader_class

CONFIG = {
    "name": "v12_bid_heavy_otm",
    "traded_vouchers": ["VEV_5500", "VEV_6000", "VEV_6500"],
    "delta_hedge": {"enabled": False},
    "voucher_cfg": {
        "VEV_5500": {"max_abs_pos": 60, "take_width": 2.25, "quote_edge": 1.0, "quote_size": 20},
        "VEV_6000": {"max_abs_pos": 120, "take_width": 0.75, "quote_edge": 0.25, "quote_size": 40, "side_mode": "bid"},
        "VEV_6500": {"max_abs_pos": 120, "take_width": 0.75, "quote_edge": 0.25, "quote_size": 40, "side_mode": "bid"},
    },
}

Trader = make_trader_class(CONFIG)
