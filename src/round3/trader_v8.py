"""Round 3 trader version 8.

Changes from v1:
- Keeps the copy-inspired static smile, but blends it with rolling EMA IV memory instead of trusting it completely.
- Maintains the broader active voucher set.
- Re-enables a moderate delta hedge.

Backtest performance:
- Day 0: 13,568
- Day 1: 14,002
- Day 2: 1,467
- Total round-3 PnL: 29,037
- Aggregate product PnL:
  HYDROGEL_PACK: 12,800
  VELVETFRUIT_EXTRACT: 6,845
  VEV_4000: 9,532
  VEV_4500: 0
  VEV_5000: 0
  VEV_5100: 0
  VEV_5200: 0
  VEV_5300: -639
  VEV_5400: 76
  VEV_5500: 359
  VEV_6000: 0
  VEV_6500: 63

Takeaway:
- Very strong. Slightly behind v7 overall, but still far better than the original baseline and more balanced across VEV_4000, VEV_5500, and the small tail strikes.
"""

from round3_common import ACTIVE_VOUCHERS, STATIC_SMILE_LAST_YEAR_AVG, make_trader_class

CONFIG = {
    "name": "v8_static_plus_ema",
    "traded_vouchers": ACTIVE_VOUCHERS,
    "anchor_weights": {"local": 0.0, "ema": 0.35, "static": 0.65},
    "static_smile_coeffs": STATIC_SMILE_LAST_YEAR_AVG,
    "delta_hedge": {"enabled": True, "trigger": 40.0, "ratio": 0.4, "cap": 100},
}

Trader = make_trader_class(CONFIG)
