"""Round 3 v59 — v48 plus Black-Scholes fair-value blend for voucher takes and quotes.

Changes from v48:
- Build a live BS smile each timestamp from the VEV strip using VELVETFRUIT_EXTRACT as spot.
- Blend the statistical fair with BS fair for voucher taking/quoting.
- Keep the anchor-divergence trigger itself intact.

Intent:
- Let BS gently recenter quotes without replacing the working anchor-divergence logic.

Public round-3 backtest:
- Total PnL: 721,440
- Outcome: tiny improvement versus v48 (+63), mostly via small quote/take changes in the voucher strip.
"""

from v58_bs_common import VoucherOverlayTrader, VoucherOverlayConfig


class Trader(VoucherOverlayTrader):
    overlay_cfg = VoucherOverlayConfig(
        mode="blend",
        residual_tol=0.0,
        blend_alpha=0.25,
        quote_shift_scale=0.10,
    )
