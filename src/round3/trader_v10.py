"""Round 3 trader version 10.

Changes from v1:
- Broad active voucher universe.
- Blended local/EMA anchor, but with much tighter quote edges and larger sizes.
- Keeps underlyings and a light hedge.
- This is a deliberate presence-heavy dart throw.

Backtest performance:
- Day 0: 12,002
- Day 1: 11,626
- Day 2: -1,998
- Total round-3 PnL: 21,630
- Aggregate product PnL:
  HYDROGEL_PACK: 12,800
  VELVETFRUIT_EXTRACT: 6,845
  VEV_4000: 8,715
  VEV_4500: 0
  VEV_5000: 0
  VEV_5100: 0
  VEV_5200: 0
  VEV_5300: -445
  VEV_5400: -2,452
  VEV_5500: -1,512
  VEV_6000: 0
  VEV_6500: -2,321

Takeaway:
- Being present on more voucher names more often was not enough. The extra middle-strike exposure dragged total PnL well below the better concentrated versions.
"""

from round3_common import ACTIVE_VOUCHERS, make_trader_class

CONFIG = {
    "name": "v10_all_active_dart",
    "traded_vouchers": ACTIVE_VOUCHERS,
    "anchor_weights": {"local": 0.5, "ema": 0.5, "static": 0.0},
    "delta_hedge": {"enabled": True, "trigger": 55.0, "ratio": 0.25, "cap": 80},
    "voucher_cfg": {
        "VEV_4000": {"max_abs_pos": 120, "take_width": 4.5, "quote_edge": 1.5, "quote_size": 50},
        "VEV_5300": {"max_abs_pos": 120, "take_width": 1.25, "quote_edge": 0.5, "quote_size": 50},
        "VEV_5400": {"max_abs_pos": 120, "take_width": 1.25, "quote_edge": 0.5, "quote_size": 50},
        "VEV_5500": {"max_abs_pos": 120, "take_width": 1.25, "quote_edge": 0.5, "quote_size": 50},
        "VEV_6000": {"max_abs_pos": 140, "take_width": 0.75, "quote_edge": 0.25, "quote_size": 55, "side_mode": "bid"},
        "VEV_6500": {"max_abs_pos": 140, "take_width": 0.75, "quote_edge": 0.25, "quote_size": 55, "side_mode": "bid"},
    },
}

Trader = make_trader_class(CONFIG)
