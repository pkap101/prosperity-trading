"""Round 3 trader version 38.

Hybrid design:
- Voucher core from `v25`: aggressive running-anchor divergence engine with skewed quoting and flow-adjusted fair value.
- Underliers from `trader_v19`: mmbot-style adverse-volume predictor on `HYDROGEL_PACK` and `VELVETFRUIT_EXTRACT`.
- Far strikes from `v27`: passive 0/1 quoting on `VEV_6000` and `VEV_6500`.

Architecture goal:
- Preserve the broad, aggressive voucher posture that drove `v25`.
- Remove the weak `v25` underlier contribution and replace it with a stronger internal underlier engine.
- Keep far strikes strictly passive.

Backtest performance:
- Day 0: 131,268
- Day 1: 126,104
- Day 2: 147,956
- Total round-3 PnL: 405,328
- Aggregate product PnL:
  HYDROGEL_PACK: 23,634
  VELVETFRUIT_EXTRACT: 7,103
  VEV_4000: 43,453
  VEV_4500: 49,561
  VEV_5000: 86,591
  VEV_5100: 83,634
  VEV_5200: 65,516
  VEV_5300: 25,383
  VEV_5400: 17,031
  VEV_5500: 2,522
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
    "quote_size": 30,
    "max_diverge_position": 295,
    "running_weight": 1.0,
    "bs_weight": 0.0,
    "quote_mode": "skewed",
    "skew_per_unit": 0.02,
    "baseline_vol": 0.5,
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
VOUCHER_CFG["VEV_4000"]["aggressor_lambda"] = 0.015
VOUCHER_CFG["VEV_5500"]["baseline_vol"] = 0.3
VOUCHER_CFG.update({"VEV_6000": {"wide_quote_size": 7}, "VEV_6500": {"wide_quote_size": 7}})

Trader = make_trader_class({
    "underlying_mode": "mmbot",
    "underlier_cfg": UNDERLIER_CFG,
    "voucher_cfg": VOUCHER_CFG,
})
