"""Round 3 trader version 5.

Changes from v1:
- Pushes the voucher fair value much closer to rolling EMA IV memory and away from the instantaneous local fit.
- Keeps the traded set narrow and sizes smaller.
- Retains a milder partial delta hedge.
- This is the stability-first version.

Backtest performance:
- Day 0: 12,956
- Day 1: 14,134
- Day 2: 1,226
- Total round-3 PnL: 28,316
- Aggregate product PnL:
  HYDROGEL_PACK: 12,800
  VELVETFRUIT_EXTRACT: 6,845
  VEV_4000: 8,670
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
- This was one of the strongest runs. The slow anchor plus a near-single-name emphasis on VEV_4000 produced materially better day-2 resilience than the baseline.
"""

from round3_common import make_trader_class

CONFIG = {
    "name": "v5_rolling_conservative",
    "traded_vouchers": ["VEV_4000", "VEV_5500", "VEV_6000"],
    "anchor_weights": {"local": 0.15, "ema": 0.85, "static": 0.0},
    "delta_hedge": {"enabled": True, "trigger": 35.0, "ratio": 0.35, "cap": 90},
    "voucher_cfg": {
        "VEV_4000": {"max_abs_pos": 40, "take_width": 10.0, "quote_edge": 4.0, "quote_size": 12},
        "VEV_5500": {"max_abs_pos": 50, "take_width": 2.5, "quote_edge": 1.25, "quote_size": 15},
        "VEV_6000": {"max_abs_pos": 70, "take_width": 1.5, "quote_edge": 0.75, "quote_size": 20, "side_mode": "bid"},
    },
}

Trader = make_trader_class(CONFIG)
