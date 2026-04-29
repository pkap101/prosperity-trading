"""Round 3 v58 — v48 plus Black-Scholes confirmation filter on voucher divergence trades.

Changes from v48:
- Build a live BS smile each timestamp from the VEV strip using VELVETFRUIT_EXTRACT as spot.
- Keep the voucher anchor-divergence engine intact.
- Only block the aggressive divergence-leg when BS residual strongly disagrees with the anchor signal.
- Passive quotes and underlier logic remain effectively the same structure as v48.

Intent:
- Preserve the profitable v48 microstructure core.
- Use BS only as a veto on the worst-looking outright voucher entries.

Public round-3 backtest:
- Total PnL: 721,377
- Outcome: identical to v48 on the public data; the BS veto was economically inert.
"""

from v58_bs_common import VoucherOverlayTrader, VoucherOverlayConfig


class Trader(VoucherOverlayTrader):
    overlay_cfg = VoucherOverlayConfig(
        mode="confirm",
        residual_tol=8.0,
    )
