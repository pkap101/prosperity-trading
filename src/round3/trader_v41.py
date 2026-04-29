"""Round 3 trader version 41.

Hybrid design:
- Voucher core from `trader_v40`: blended running + BS anchor with middle-strike guardrails.
- Underliers from `v24` / `v22`: Kalman-style mean-reversion instead of the `trader_v19` predictor.
- Adds `v27`-style far-strike passive 0/1 logic.

Architecture goal:
- Test whether the best hybrid voucher design wants the stronger open-source underlier style instead of the internal mmbot predictor.
- This isolates the underlier choice while keeping the same tactical voucher protections.

Backtest performance:
- Day 0: 67,132
- Day 1: 144,818
- Day 2: 106,094
- Total round-3 PnL: 318,044
- Aggregate product PnL:
  HYDROGEL_PACK: 137,772
  VELVETFRUIT_EXTRACT: 87,908
  VEV_4000: 25,744
  VEV_4500: 25,495
  VEV_5000: 0
  VEV_5100: 13,907
  VEV_5200: 13,973
  VEV_5300: 8,779
  VEV_5400: 2,673
  VEV_5500: 892
  VEV_6000: 450
  VEV_6500: 450
"""

from hybrid_round3_core import HYDRO, VELVET, CORE_VOUCHERS, make_trader_class

UNDERLIER_CFG = {
    HYDRO: {"product": HYDRO, "position_limit": 200, "k_ss": 0.02, "fair_static": 10030, "mr_gain": 2000, "sigma_init": 30.0, "take_max_pay": -6, "quote_edge": 3, "quote_size": 30},
    VELVET: {"product": VELVET, "position_limit": 200, "k_ss": 0.02, "fair_static": 5275, "mr_gain": 2000, "sigma_init": 15.0, "take_max_pay": -2, "quote_edge": 1, "quote_size": 30},
}

BASE = {
    "position_limit": 300,
    "quote_size": 24,
    "max_diverge_position": 200,
    "running_weight": 0.55,
    "bs_weight": 0.45,
    "quote_mode": "midpoint",
}

THRESHOLDS = {
    "VEV_4000": 25,
    "VEV_4500": 25,
    "VEV_5000": 22,
    "VEV_5100": 18,
    "VEV_5200": 14,
    "VEV_5300": 10,
    "VEV_5400": 5,
    "VEV_5500": 3,
}

GUARDS = {
    "VEV_5000": 10.0,
    "VEV_5100": 9.0,
    "VEV_5200": 8.0,
    "VEV_5300": 6.0,
    "VEV_5400": 5.0,
    "VEV_5500": 4.0,
}

VOUCHER_CFG = {prod: {**BASE, "product": prod, "diverge_threshold": THRESHOLDS[prod]} for prod in CORE_VOUCHERS}
for prod, guard in GUARDS.items():
    VOUCHER_CFG[prod]["anchor_gap_guard"] = guard
    VOUCHER_CFG[prod]["guard_quote_size"] = 10
    VOUCHER_CFG[prod]["guard_max_diverge_position"] = 35
    VOUCHER_CFG[prod]["disable_diverge_on_guard"] = True
VOUCHER_CFG.update({"VEV_6000": {"wide_quote_size": 7}, "VEV_6500": {"wide_quote_size": 7}})

Trader = make_trader_class({
    "underlying_mode": "kalman",
    "underlier_cfg": UNDERLIER_CFG,
    "voucher_cfg": VOUCHER_CFG,
})
