"""Round 3 v60 — v48 plus Black-Scholes disagreement haircut on voucher risk.

Changes from v48:
- Build a live BS smile each timestamp from the VEV strip using VELVETFRUIT_EXTRACT as spot.
- Keep the same anchor-divergence trigger.
- When BS residual materially disagrees with the anchor signal, shrink voucher divergence size and position cap.

Intent:
- Use BS as a bounded risk manager rather than as a primary valuation engine.

Public round-3 backtest:
- Total PnL: 721,377
- Outcome: identical to v48 on the public data; the haircut almost never activated.
"""

from v58_bs_common import VoucherOverlayTrader, VoucherOverlayConfig


class Trader(VoucherOverlayTrader):
    overlay_cfg = VoucherOverlayConfig(
        mode="haircut",
        residual_tol=8.0,
        disagree_scale=0.40,
    )
