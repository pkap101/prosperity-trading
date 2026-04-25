# Round 2 Backtest Results

This note compares the three most relevant Round 2 trader variants currently in the repo:

- `v1`: strongest standalone baseline among the imported Round 2 files
- `v3`: strongest alternate baseline, especially on Osmium
- `v6`: product-level hybrid using Pepper from `v1` and Osmium from `v3`

The goal of this document is to make one question easy to answer:

> Did the product-wise hybrid actually improve the local baseline, or did the merge just move PnL around?

## Test Setup

Backtests were run locally with:

```bash
prosperity3bt src/round2/<file>.py <round> --no-out --no-progress
```

Assumptions and caveats:

- Trade matching mode is the local default: `all`
- Round 1 uses days `-2, -1, 0`
- Round 2 uses days `-1, 0, 1`
- The local backtester does **not** simulate Round 2 market access
- The local backtester does **not** call `Trader.bid()`
- No MAF fee is deducted in any numbers below

Interpretation:

- These are **base strategy PnLs on the default local book**
- They are useful for comparing trading logic
- They do **not** answer whether a specific Round 2 `bid()` value is good

## Files Compared

| File | Pepper Logic | Osmium Logic | `bid()` in file | Notes |
|---|---|---|---:|---|
| `v1.py` | `v1` | `v1` | 15 | Best standalone baseline |
| `v3.py` | `v3` | `v3` | 1103 | Better Osmium, weaker Pepper |
| `v6.py` | `v1` | `v3` | 15 | Hybrid merge |

## Round 1: Per-Day Results

### Day -2

| File | Osmium | Pepper | Total |
|---|---:|---:|---:|
| `v1` | 17,615 | 81,585 | 99,200 |
| `v3` | 18,364 | 79,649 | 98,013 |
| `v6` | 18,364 | 81,585 | 99,949 |

### Day -1

| File | Osmium | Pepper | Total |
|---|---:|---:|---:|
| `v1` | 18,990 | 81,136 | 100,126 |
| `v3` | 19,858 | 79,318 | 99,176 |
| `v6` | 19,858 | 81,136 | 100,994 |

### Day 0

| File | Osmium | Pepper | Total |
|---|---:|---:|---:|
| `v1` | 17,959 | 81,106 | 99,065 |
| `v3` | 18,121 | 79,450 | 97,571 |
| `v6` | 18,121 | 81,106 | 99,227 |

### Round 1 Sum

| File | Osmium | Pepper | Total |
|---|---:|---:|---:|
| `v1` | 54,564 | 243,827 | 298,391 |
| `v3` | 56,343 | 238,417 | 294,760 |
| `v6` | 56,343 | 243,827 | 300,170 |

## Round 2: Per-Day Results

### Day -1

| File | Osmium | Pepper | Total |
|---|---:|---:|---:|
| `v1` | 19,583 | 80,358 | 99,941 |
| `v3` | 20,290 | 79,418 | 99,708 |
| `v6` | 20,290 | 80,358 | 100,648 |

### Day 0

| File | Osmium | Pepper | Total |
|---|---:|---:|---:|
| `v1` | 20,356 | 80,241 | 100,597 |
| `v3` | 20,404 | 79,399 | 99,803 |
| `v6` | 20,404 | 80,241 | 100,645 |

### Day 1

| File | Osmium | Pepper | Total |
|---|---:|---:|---:|
| `v1` | 19,141 | 81,752 | 100,893 |
| `v3` | 20,185 | 79,197 | 99,382 |
| `v6` | 20,185 | 81,752 | 101,937 |

### Round 2 Sum

| File | Osmium | Pepper | Total |
|---|---:|---:|---:|
| `v1` | 59,080 | 242,351 | 301,431 |
| `v3` | 60,879 | 238,014 | 298,893 |
| `v6` | 60,879 | 242,351 | 303,230 |

## All 6 Days Combined

| File | Osmium | Pepper | Total |
|---|---:|---:|---:|
| `v1` | 113,644 | 486,178 | 599,822 |
| `v3` | 117,222 | 476,431 | 593,653 |
| `v6` | 117,222 | 486,178 | 603,400 |

## What Actually Happened

The clean summary is:

- `v1` is better on Pepper
- `v3` is better on Osmium
- `v6` preserves both of those advantages

This was not just a small reshuffle. The hybrid won on:

- Round 1 total
- Round 2 total
- Combined 6-day total

### Improvement vs Parents

| Comparison | Round 1 | Round 2 | All 6 Days |
|---|---:|---:|---:|
| `v6 - v1` | +1,779 | +1,799 | +3,578 |
| `v6 - v3` | +5,410 | +4,337 | +9,747 |

## Interpretation

### 1. The hybrid thesis was correct

This was the right kind of merge:

- no cross-product dependency
- separate position limits
- separate product-specific signal logic

That matters because not all “hybrids” are valid. In this case, the merge was clean and the resulting PnL behaved as expected.

### 2. The edge is additive enough to matter

The main concern before merging was whether combining the two product strategies would silently break due to:

- shared `traderData`
- inconsistent helper logic
- run-order side effects

That did not happen here. `v6` beat both parents on both rounds, which is strong evidence that the merge was implemented correctly.

### 3. Pepper is still the larger contributor

Even in the best hybrid:

- Pepper contributes `486,178`
- Osmium contributes `117,222`

So Pepper remains the bigger driver of total PnL. But the Osmium improvement is still meaningful enough to lift the whole strategy.

## Practical Conclusion

Current local ranking:

1. `v6`
2. `v1`
3. `v3`

Actionable takeaway:

- `v6` should be treated as the current strongest local baseline
- future Round 2 iteration should branch from `v6`, not from `v1` or `v3`
- MAF bidding should be analyzed separately, because these results do not include market-access effects or fee deductions

## Next Questions

The next useful questions are:

1. Can `v6` be improved further without adding fragile complexity?
2. Does `v6` still hold up under alternative backtester assumptions, especially different trade-matching modes?
3. What is the incremental value of market access relative to the no-access baseline established here?
