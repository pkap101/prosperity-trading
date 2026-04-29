"""Round 3 trader version 37.

Hybrid design:
- Voucher core from `v24`: running-anchor divergence plus full-depth fair-value market making on `VEV_4000` through `VEV_5500`.
- Underliers from `trader_v19`: mmbot-style adverse-volume predictor on `HYDROGEL_PACK` and `VELVETFRUIT_EXTRACT`.
- Far strikes from `v27`: passive 0/1 quoting on `VEV_6000` and `VEV_6500` when the book is in the standard wide regime.

Architecture goal:
- Keep the strongest outright voucher engine from the open-source matrix.
- Replace the underlier leg with the best internal underlier-only engine.
- Add the only far-strike logic that has shown any meaningful edge.

Backtest performance:
- Day 0: 132,382
- Day 1: 126,800
- Day 2: 148,517
- Total round-3 PnL: 407,699
- Aggregate product PnL:
  HYDROGEL_PACK: 23,634
  VELVETFRUIT_EXTRACT: 7,103
  VEV_4000: 44,785
  VEV_4500: 49,563
  VEV_5000: 86,591
  VEV_5100: 83,634
  VEV_5200: 65,860
  VEV_5300: 25,847
  VEV_5400: 17,513
  VEV_5500: 2,269
  VEV_6000: 450
  VEV_6500: 450
"""

from hybrid_round3_core import HYDRO, VELVET, ALL_VOUCHERS, CORE_VOUCHERS, make_trader_class

UNDERLIER_CFG = {
    HYDRO: {"threshold": 18, "retreat": 0.04, "edge_per_lot": 0.18, "cap": 80, "revert": -0.22},
    VELVET: {"threshold": 15, "retreat": 0.03, "edge_per_lot": 0.12, "cap": 90, "revert": -0.18},
}

BASE = {
    "position_limit": 300,
    "quote_size": 30,
    "max_diverge_position": 295,
    "running_weight": 1.0,
    "bs_weight": 0.0,
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
