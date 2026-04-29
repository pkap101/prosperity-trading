"""Round 3 trader version 4.

Changes from v1:
- Expands to all active vouchers: VEV_4000, VEV_5300, VEV_5400, VEV_5500, VEV_6000, and VEV_6500.
- Uses a pure local smile anchor with no EMA smoothing.
- Narrows take widths and quote edges and increases size caps to test a more aggressive outright voucher stance.
- Disables delta hedging.

Backtest performance:
- Day 0: 6,229
- Day 1: 2,632
- Day 2: -11,434
- Total round-3 PnL: -2,573
- Aggregate product PnL:
  HYDROGEL_PACK: 12,800
  VELVETFRUIT_EXTRACT: 6,845
  VEV_4000: 8,712
  VEV_4500: 0
  VEV_5000: 0
  VEV_5100: 0
  VEV_5200: 0
  VEV_5300: -1,676
  VEV_5400: -15,945
  VEV_5500: -10,988
  VEV_6000: 0
  VEV_6500: -2,321

Takeaway:
- This was a clear miss. The middle strikes, especially VEV_5400 and VEV_5500, were badly loss-making when pushed aggressively off the raw local smile.
"""

from round3_common import ACTIVE_VOUCHERS, make_trader_class

CONFIG = {
    "name": "v4_local_aggressive",
    "traded_vouchers": ACTIVE_VOUCHERS,
    "anchor_weights": {"local": 1.0, "ema": 0.0, "static": 0.0},
    "delta_hedge": {"enabled": False},
    "voucher_cfg": {
        "VEV_4000": {"max_abs_pos": 100, "take_width": 5.0, "quote_edge": 2.0, "quote_size": 40},
        "VEV_5300": {"max_abs_pos": 120, "take_width": 1.5, "quote_edge": 0.5, "quote_size": 45},
        "VEV_5400": {"max_abs_pos": 120, "take_width": 1.5, "quote_edge": 0.5, "quote_size": 45},
        "VEV_5500": {"max_abs_pos": 120, "take_width": 1.5, "quote_edge": 0.5, "quote_size": 45},
        "VEV_6000": {"max_abs_pos": 150, "take_width": 0.75, "quote_edge": 0.25, "quote_size": 50, "side_mode": "bid"},
        "VEV_6500": {"max_abs_pos": 150, "take_width": 0.75, "quote_edge": 0.25, "quote_size": 50, "side_mode": "bid"},
    },
}

Trader = make_trader_class(CONFIG)
