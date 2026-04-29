# `v45`-`v50` Analysis

## Summary

These six models are not exact duplicates, but they are the same strategy family.

Shared architecture:
- `HYDROGEL_PACK` and `VELVETFRUIT_EXTRACT`: Kalman-style mean reversion toward fixed static fair values with active taking and passive quoting.
- `VEV_4000` through `VEV_5500`: running-anchor divergence plus market making.
- No `VEV_6000` / `VEV_6500` trading.

What changes across `v45`-`v50` is mostly the underlier layer:
- informed-flow target bias on `VELVETFRUIT_EXTRACT` only, or on both underliers
- `HYDROGEL_PACK` position limit in `v47`
- `mr_gain` on `HYDROGEL_PACK` and `VELVETFRUIT_EXTRACT`

## Exact-Duplicate Check

All six files have different content hashes, so there are no exact byte-identical duplicates.

Closest groups:
- `v45`, `v47`, `v48`, `v49`, `v50` are the same base architecture with different informed-flow strength and underlier `mr_gain` values.
- `v46` is the only one that adds informed-flow to both `HYDROGEL_PACK` and `VELVETFRUIT_EXTRACT`.

## Total PnL

| Rank | Version | Total PnL |
|---|---:|---:|
| 1 | `v48` | 721,377 |
| 2 | `v50` | 717,025 |
| 3 | `v49` | 715,812 |
| 4 | `v45` | 715,498 |
| 5 | `v46` | 709,347 |
| 6 | `v47` | 687,665 |
| 7 | `v24` | 601,742 |
| 8 | `v27` | 124,713 |

## Per-Product PnL

### `v45`-`v50`

| Product | `v45` | `v46` | `v47` | `v48` | `v49` | `v50` | Best |
|---|---:|---:|---:|---:|---:|---:|---:|
| `HYDROGEL_PACK` | 137,772 | 137,207 | 105,395 | 139,107 | 133,542 | 139,107 | `v48` / `v50` |
| `VELVETFRUIT_EXTRACT` | 87,398 | 81,812 | 91,942 | 91,942 | 91,942 | 87,590 | `v47` / `v48` / `v49` |
| `VEV_4000` | 41,974 | 41,974 | 41,974 | 41,974 | 41,974 | 41,974 | all tied |
| `VEV_4500` | 65,872 | 65,872 | 65,872 | 65,872 | 65,872 | 65,872 | all tied |
| `VEV_5000` | 110,279 | 110,279 | 110,279 | 110,279 | 110,279 | 110,279 | all tied |
| `VEV_5100` | 103,463 | 103,463 | 103,463 | 103,463 | 103,463 | 103,463 | all tied |
| `VEV_5200` | 83,575 | 83,575 | 83,575 | 83,575 | 83,575 | 83,575 | all tied |
| `VEV_5300` | 54,194 | 54,194 | 54,194 | 54,194 | 54,194 | 54,194 | all tied |
| `VEV_5400` | 22,892 | 22,892 | 22,892 | 22,892 | 22,892 | 22,892 | all tied |
| `VEV_5500` | 8,078 | 8,078 | 8,078 | 8,078 | 8,078 | 8,078 | all tied |
| `VEV_6000` | 0 | 0 | 0 | 0 | 0 | 0 | all tied |
| `VEV_6500` | 0 | 0 | 0 | 0 | 0 | 0 | all tied |

### Comparison to `v24` and `v27`

| Product | Best of `v45`-`v50` | `v24` | `v27` |
|---|---:|---:|---:|
| `HYDROGEL_PACK` | 139,107 | 137,772 | 59,319 |
| `VELVETFRUIT_EXTRACT` | 91,942 | 87,908 | 26,461 |
| `VEV_4000` | 41,974 | 44,785 | 16,836 |
| `VEV_4500` | 65,872 | 49,563 | 4,766 |
| `VEV_5000` | 110,279 | 86,591 | 12,057 |
| `VEV_5100` | 103,463 | 83,634 | 9,791 |
| `VEV_5200` | 83,575 | 65,860 | -5,451 |
| `VEV_5300` | 54,194 | 25,847 | -2,063 |
| `VEV_5400` | 22,892 | 17,513 | 2,963 |
| `VEV_5500` | 8,078 | 2,269 | -867 |
| `VEV_6000` | 0 | 0 | 450 |
| `VEV_6500` | 0 | 0 | 450 |

## Why This Family Beats `v24`

The underlier core is basically the same as `v24`:
- `v24` underlier configs: [v24.py](/Users/pranavkapur2/Code/prosperity-trading/src/round3/v24.py#L236)
- `v45` underlier configs: [v45.py](/Users/pranavkapur2/Code/prosperity-trading/src/round3/v45.py#L254)

The main improvement is the voucher thresholds:
- `v24` voucher thresholds are wider: [v24.py](/Users/pranavkapur2/Code/prosperity-trading/src/round3/v24.py#L261)
- `v45`-family thresholds are tighter: [v45.py](/Users/pranavkapur2/Code/prosperity-trading/src/round3/v45.py#L279)

Concretely:
- `VEV_4000`: `25 -> 18`
- `VEV_4500`: `25 -> 18`
- `VEV_5000`: `22 -> 15`
- `VEV_5100`: `18 -> 13`
- `VEV_5200`: `14 -> 10`
- `VEV_5300`: `10 -> 7`
- `VEV_5400`: `5 -> 4`
- `VEV_5500`: `3 -> 2`

That does two things:
- it enters the outright voucher names much more often
- it still stays in the same simple outright architecture instead of layering fragile cross-strike logic on top

This is why the family beats `v24` on almost every core voucher while keeping similar or slightly better underliers.

## Why `v48` Wins This Group

`v48` is effectively the best balance among these knobs:
- it keeps the stronger `VELVETFRUIT_EXTRACT` informed-flow target bias (`INFORMED_GAIN_S = 10`): [v48.py](/Users/pranavkapur2/Code/prosperity-trading/src/round3/v48.py#L291)
- it reduces `HYDROGEL_PACK` `mr_gain` from `2000` to `1000`: [v48.py](/Users/pranavkapur2/Code/prosperity-trading/src/round3/v48.py#L254)

Interpretation:
- `HYDROGEL_PACK` benefits from less aggressive target reversion than `v45`
- `VELVETFRUIT_EXTRACT` benefits from keeping the stronger flow-driven target bias
- the voucher book is untouched, so the strong strip PnL remains intact

This is why `v48` dominates total PnL without needing any exotic extra engine.

## Product-by-Product Strategy Read

### `HYDROGEL_PACK`

What works:
- static-anchor Kalman mean reversion with disciplined crossing and passive quoting
- enough aggression to monetize deviations, but not so much that inventory control breaks

Evidence:
- `v48` / `v50` lead here with `139,107`
- `v24` is already strong at `137,772`
- bad Hydro models like `v29` / `v30` showed Hydro can destroy an otherwise good book

Why this works better than our worse models:
- it is a direct single-name reversion engine
- it does not force multi-leg or hedge-dependent logic
- it avoids the unstable “clever” overlays that caused catastrophic PnL elsewhere

### `VELVETFRUIT_EXTRACT`

What works:
- same Kalman mean-reversion skeleton
- selective informed-flow target bias on top of the anchor, rather than replacing the anchor

Evidence:
- best here is `91,942` (`v47` / `v48` / `v49`)
- `v46` underperforms because adding Hydro informed-flow as well did not help overall and also weakened VFE versus the best variants
- `v45` underperforms the best variants because its VFE informed-flow gain is too small

Why it works:
- the signal is additive, not dominant
- the model still reverts to a stable anchor and just leans harder when the tape gives a credible large-trade cue

### `VEV_4000` through `VEV_5500`

What works:
- simple outright anchor-divergence plus market making
- tighter thresholds than `v24`
- no forced spread books, no cross-strike inventory puzzle, no local-zscore relative-value overlays

Why this beats our worse voucher models:
- the bad models tried to be too structural about the strip
- examples of losing ideas:
  - `trader_v14`: middle-strike spread overlays were catastrophically wrong
  - `trader_v20`: local-smile residual z-score rebalancing lost heavily
  - `v23`: extra skew / fair-exit / inventory logic destabilized the middle and upper-middle strikes
- this family just trades the names that actually pay, directly and repeatedly

The most important contrast is with `v24`:
- `v24` already had the right structure
- `v45`-`v50` mostly improve it by lowering the divergence thresholds and participating more aggressively in the profitable core strip

### `VEV_6000` and `VEV_6500`

This family does nothing here.

Why that is still acceptable:
- `v27` proved these names need separate logic
- the profitable logic there was the special passive `0/1` regime, not a normal extension of the core voucher engine
- these models stay focused on the high-quality core strip and do not dilute it with unsupported far-strike logic

## Why `v24` and `v27` Beat The Worse Models

### Why `v24` works

`v24` wins because it is simple in the right places:
- strong single-name underlier MR
- strong outright voucher participation in the liquid core of the strip
- no dependence on fragile pair relationships or complex hedge state

It extracts edge where the tape is actually offering it.

### Why `v27` works, despite much lower total PnL

`v27` is not a better all-book model than `v24`.
It matters because it isolates one thing the other models missed:
- `VEV_6000` and `VEV_6500` needed separate special-case logic

That is why `v27` was valuable as a component model, even though its core strip and underlier performance were much weaker.

### Why the bad models lose

The recurring failure pattern was not “too passive” or “too conservative.”
It was structural mismatch.

They tended to do one or more of the following:
- force relative-value trades across strikes that were not robustly supported by the realized tape
- add extra skew, smile, spread, or inventory machinery that reduced fill quality or amplified inventory risk
- depend on hedge coordination that failed when one leg monetized much worse than the others
- overtrade weaker parts of the strip instead of harvesting the obvious core names directly

The `v45`-`v50` family avoids most of that.

## Practical Takeaways

1. `v48` is the best version in this new family.
2. The reason is not a new architecture. It is a better calibration of the same winning architecture.
3. The biggest edge remains the core voucher strip `VEV_4500` through `VEV_5300`, especially `VEV_5000` and `VEV_5100`.
4. Underlier tuning still matters, because the voucher engine is identical across `v45`-`v50`.
5. `v27` remains relevant only as a far-strike specialist, not as a full-book benchmark.
