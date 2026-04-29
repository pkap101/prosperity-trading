"""Round 3 v62 — v48 plus stronger Black-Scholes risk haircut on voucher divergence.

Changes from v48:
- Same live BS smile construction as v58-v60.
- When BS disagrees, shrink voucher divergence size and risk much more aggressively than v60.

Intent:
- Test BS as a meaningful drawdown-control layer rather than a cosmetic one.

Public round-3 backtest:
- Total PnL: 715,563
- Outcome: slightly below v48; stronger BS haircuts reduced profitable voucher participation more than they reduced risk.
"""

from v58_bs_common import VoucherOverlayTrader, VoucherOverlayConfig


class Trader(VoucherOverlayTrader):
    overlay_cfg = VoucherOverlayConfig(
        mode="haircut",
        residual_tol=2.0,
        disagree_scale=0.20,
    )
