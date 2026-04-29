"""Round 3 trader version 39.

Hybrid design:
- Voucher fair-value anchor blends `v24` and `v22`:
  - running anchor from `v24`
  - Black-Scholes smile anchor from `v22`
- Underliers from `trader_v19`.
- Far strikes from `v27`.

Architecture goal:
- Reduce dependence on a pure historical running mean without giving up the strong `v24` outright structure.
- Let the BS anchor regularize the strip while keeping the running anchor sensitive to this tape.

Backtest performance:
- Day 0: 16,116
- Day 1: 60,733
- Day 2: 61,694
- Total round-3 PnL: 138,542
- Aggregate product PnL:
  HYDROGEL_PACK: 23,634
  VELVETFRUIT_EXTRACT: 7,103
  VEV_4000: 27,916
  VEV_4500: 28,117
  VEV_5000: 23,041
  VEV_5100: 15,330
  VEV_5200: 8,751
  VEV_5300: 3,964
  VEV_5400: 92
  VEV_5500: -306
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
    "quote_size": 26,
    "max_diverge_position": 220,
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

VOUCHER_CFG = {prod: {**BASE, "product": prod, "diverge_threshold": THRESHOLDS[prod]} for prod in CORE_VOUCHERS}
VOUCHER_CFG.update({"VEV_6000": {"wide_quote_size": 7}, "VEV_6500": {"wide_quote_size": 7}})

Trader = make_trader_class({
    "underlying_mode": "mmbot",
    "underlier_cfg": UNDERLIER_CFG,
    "voucher_cfg": VOUCHER_CFG,
})
