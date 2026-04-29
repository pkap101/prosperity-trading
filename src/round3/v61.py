"""Round 3 v61 — v48 plus aggressive Black-Scholes confirmation veto on voucher divergence trades.

Changes from v48:
- Same live BS smile construction as v58-v60.
- Tighter residual tolerance than v58, so BS disagreement blocks more outright divergence trades.

Intent:
- Force BS to matter enough to test whether it genuinely improves or hurts the core voucher strip.

Public round-3 backtest:
- Total PnL: 707,640
- Outcome: clearly worse than v48; stronger BS veto blocked too many profitable voucher trades, especially in VEV_5400.
"""

from v58_bs_common import VoucherOverlayTrader, VoucherOverlayConfig


class Trader(VoucherOverlayTrader):
    overlay_cfg = VoucherOverlayConfig(
        mode="confirm",
        residual_tol=2.0,
    )
