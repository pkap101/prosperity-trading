"""Round 3 trader version 1.

Version summary:
- First fully versioned baseline.
- Uses both delta-one market making on HYDROGEL_PACK and VELVETFRUIT_EXTRACT.
- Uses a blended voucher fair-value anchor built from the current cross-sectional smile and per-strike EMA IV memory.
- Trades VEV_4000, VEV_5500, VEV_6000, and VEV_6500, with one-sided bid-heavy logic on the far OTM names.
- Applies a coarse partial voucher delta hedge in VELVETFRUIT_EXTRACT.

Architecture:
- Underlyings: both delta-one products use the same microprice-plus-imbalance fair-value model, with product-specific widths, skew, and quote size. The engine takes clearly stale prices first and then posts passive quotes around the adjusted fair value.
- Voucher valuation: every timestamp, the trader estimates spot from VELVETFRUIT_EXTRACT, computes implied vols where possible, fits a local quadratic smile in moneyness space, and blends that with per-strike EMA IV memory stored in traderData. The intent was to be adaptive without letting the fair value jump too violently tick to tick.
- Voucher execution: VEV_4000 and VEV_5500 are traded two-sided. VEV_6000 and VEV_6500 are quoted mostly from the bid because the notebook showed strong bid-side touch behavior and weak ask-side touch behavior in those strikes.
- Risk control: the delta hedge only fires when estimated voucher delta passes a threshold. That was a deliberate architecture choice to keep the underlying hedge from overwhelming the alpha legs.

Backtest performance:
- Day 0: 12,561
- Day 1: 13,251
- Day 2: 332
- Total round-3 PnL: 26,144
- Aggregate product PnL:
  HYDROGEL_PACK: 12,800
  VELVETFRUIT_EXTRACT: 6,845
  VEV_4000: 8,717
  VEV_4500: 0
  VEV_5000: 0
  VEV_5100: 0
  VEV_5200: 0
  VEV_5300: 0
  VEV_5400: 0
  VEV_5500: 103
  VEV_6000: 0
  VEV_6500: -2,321

Takeaway:
- Baseline behavior was respectable but too concentrated in VEV_4000. The far OTM VEV_6500 leg was consistently harmful and the day-2 HYDROGEL_PACK book was unstable.
"""

from round3_common import make_trader_class

CONFIG = {
    "name": "v1_baseline_blended",
}

Trader = make_trader_class(CONFIG)
