# Round 3 Version Backtest Summary

Command used for every version:
- `source .venv/bin/activate && prosperity3bt src/round3/trader_vX.py 3 --no-out --no-progress`

Backtester note:
- `backtester/prosperity3bt/data.py` was patched so Round 3 products and vouchers have limits and the local backtester can run these files correctly.

## Leaderboard

| Version | Total PnL |
| --- | ---: |
| `trader_v19` | 33,697 |
| `trader_v7` | 29,254 |
| `trader_v8` | 29,037 |
| `trader_v5` | 28,316 |
| `trader_v6` | 28,058 |
| `trader_v1` | 26,144 |
| `trader_v11` | 23,728 |
| `trader_v10` | 21,630 |
| `trader_v2` | 19,646 |
| `trader_v12` | 17,546 |
| `trader_v13` | 8,717 |
| `trader_v3` | 6,499 |
| `trader_v15` | -529 |
| `trader_v9` | -961 |
| `trader_v4` | -2,572 |
| `trader_v16` | -3,114 |
| `trader_v17` | -135,275 |
| `trader_v18` | -142,574 |
| `trader_v20` | -206,339 |
| `trader_v14` | -892,361 |

## Updated Conclusions

- Best overall is now `trader_v19` at 33,697. This is the first truly different architecture to beat the earlier voucher-heavy families.
- Best voucher-heavy copy-inspired version remains `trader_v7` at 29,254, followed closely by `trader_v8` at 29,037.
- Best adaptive conservative voucher variant remains `trader_v5` at 28,316.
- `VEV_4000` is still the cleanest positive standalone voucher.
- Multiple pure target-position voucher strategies failed badly: `trader_v17`, `trader_v18`, and `trader_v20`.
- The copied market-maker envelope idea in `trader_v16` was not enough by itself because the hedge cost dominated the voucher gains.
- The broader picture is now clearer: the strongest edge may currently be in the underlying books, while many of the voucher signals require much better execution and risk control than the naive target-position forms used here.
