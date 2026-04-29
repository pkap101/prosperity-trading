"""Round 3 trader version 42.

Hybrid design:
- Full `v24` book inside the reusable hybrid core:
  - `v24`-style Kalman underliers
  - `v24`-style running-anchor outright voucher engine on `VEV_4000` through `VEV_5500`
- Adds `v27` far-strike passive 0/1 logic on `VEV_6000` and `VEV_6500`.

Architecture goal:
- Test the simplest additive hypothesis from batch 1: keep the strongest full-book engine intact and bolt on the only far-strike regime that has shown stable positive results.

Backtest performance:
- Day 0: 181,151
- Day 1: 220,448
- Day 2: 201,044
- Total round-3 PnL: 602,642
- Aggregate product PnL:
  HYDROGEL_PACK: 137,772
  VELVETFRUIT_EXTRACT: 87,908
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

from hybrid_round3_core import HYDRO, VELVET, CORE_VOUCHERS, make_trader_class

UNDERLIER_CFG = {
    HYDRO: {"product": HYDRO, "position_limit": 200, "k_ss": 0.02, "fair_static": 10030, "mr_gain": 2000, "sigma_init": 30.0, "take_max_pay": -6, "quote_edge": 3, "quote_size": 30},
    VELVET: {"product": VELVET, "position_limit": 200, "k_ss": 0.02, "fair_static": 5275, "mr_gain": 2000, "sigma_init": 15.0, "take_max_pay": -2, "quote_edge": 1, "quote_size": 30},
}

BASE = {
    "position_limit": 300,
    "quote_size": 30,
    "max_diverge_position": 295,
    "running_weight": 1.0,
    "bs_weight": 0.0,
    "quote_mode": "midpoint",
}
THRESHOLDS = {"VEV_4000": 25, "VEV_4500": 25, "VEV_5000": 22, "VEV_5100": 18, "VEV_5200": 14, "VEV_5300": 10, "VEV_5400": 5, "VEV_5500": 3}
VOUCHER_CFG = {prod: {**BASE, "product": prod, "diverge_threshold": THRESHOLDS[prod]} for prod in CORE_VOUCHERS}
VOUCHER_CFG.update({"VEV_6000": {"wide_quote_size": 7}, "VEV_6500": {"wide_quote_size": 7}})

Trader = make_trader_class({"underlying_mode": "kalman", "underlier_cfg": UNDERLIER_CFG, "voucher_cfg": VOUCHER_CFG})
