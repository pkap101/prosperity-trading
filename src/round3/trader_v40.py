"""Round 3 trader version 40.

Hybrid design:
- Core from `trader_v39`: blended running + BS voucher anchor, `trader_v19` underliers, `v27` far-strike handling.
- Adds a tactical guardrail derived from the worst models:
  - if the running anchor and BS anchor diverge too much in the dangerous middle / upper-middle strikes,
    shrink quote size and suppress fresh divergence-taking.

Architecture goal:
- Lean into a specific lesson from `trader_v14`, `trader_v20`, `v23`, and `v35`:
  the middle and upper-middle strikes become dangerous when the local tape and structural fair disagree sharply.

Backtest performance:
- Day 0: 18,362
- Day 1: 51,170
- Day 2: 53,568
- Total round-3 PnL: 123,100
- Aggregate product PnL:
  HYDROGEL_PACK: 23,634
  VELVETFRUIT_EXTRACT: 7,103
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
    HYDRO: {"threshold": 18, "retreat": 0.04, "edge_per_lot": 0.18, "cap": 80, "revert": -0.22},
    VELVET: {"threshold": 15, "retreat": 0.03, "edge_per_lot": 0.12, "cap": 90, "revert": -0.18},
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
    "underlying_mode": "mmbot",
    "underlier_cfg": UNDERLIER_CFG,
    "voucher_cfg": VOUCHER_CFG,
})
