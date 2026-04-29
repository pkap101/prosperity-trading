# Round 3 Hybrid Iteration Notes

## Goal

This iteration focused on hybridizing the most promising components from the earlier matrix rather than just testing isolated open-source files.

Main source components:
- `v24`: strongest all-book running-anchor voucher engine plus very strong underliers
- `v25`: aggressive skewed-quote voucher variant
- `v27`: only far-strike logic that consistently made money in `VEV_6000` and `VEV_6500`
- `v22`: Black-Scholes smile anchor concept
- `trader_v19`: strongest internal underlier-only engine
- bad models used as negative signal: `trader_v14`, `trader_v20`, `v23`, `v35`

A reusable hybrid engine was added in [hybrid_round3_core.py](/Users/pranavkapur2/Code/prosperity-trading/src/round3/hybrid_round3_core.py) so the variants differ by actual components rather than ad hoc copy-paste.

## Batch 1: Structural Hybrids

| Version | Total PnL | Main mix |
| --- | ---: | --- |
| `trader_v37` | 407,699 | `v24` voucher core + `trader_v19` underliers + `v27` far strikes |
| `trader_v38` | 405,328 | `v25` voucher core + `trader_v19` underliers + `v27` far strikes |
| `trader_v41` | 318,044 | guarded blended-anchor vouchers + `v24`/`v22` Kalman underliers |
| `trader_v39` | 138,542 | blended running + BS anchor + `trader_v19` underliers |
| `trader_v40` | 123,100 | blended anchor + tactical middle-strike guardrails + `trader_v19` underliers |

### Batch 1 findings

1. `v24`'s voucher engine is the real center of gravity.
   - In `trader_v37`, the voucher totals for `VEV_4000` through `VEV_5500` reproduced the `v24` totals almost exactly.
   - That means the reusable hybrid core successfully captured the part of `v24` that matters most.

2. Replacing `v24` underliers with `trader_v19` underliers was a clear downgrade.
   - `trader_v37` and `trader_v38` were still strong, but they gave up a large amount of `HYDROGEL_PACK` and `VELVETFRUIT_EXTRACT` PnL versus `v24`.
   - Conclusion: `trader_v19` is a good internal benchmark, but `v24`'s underliers are better in this backtester.

3. The `v25` extras did not add value once the underliers were replaced.
   - `trader_v38` underperformed `trader_v37`.
   - The aggressive skewed quoting and flow-adjusted fair value were not enough to beat the cleaner `v24`-style midpoint quote engine.

4. The `v22` Black-Scholes anchor idea did not transfer well into this aggressive outright framework.
   - `trader_v39` and `trader_v40` were much worse than the pure running-anchor versions.
   - Result: the BS anchor may be useful as a diagnostic or regularizer, but in this family it reduced realized edge materially.

5. The guardrail idea was directionally sensible but too restrictive.
   - `trader_v40` was built explicitly from the failures of `trader_v14`, `trader_v20`, `v23`, and `v35`.
   - It protected the dangerous middle and upper-middle region, but it also shut down too much good voucher flow.

## Batch 2: Additive Far-Strike Test

After batch 1, the main open question was simple:
- if `v24` is already the best core book, can `v27`'s far-strike regime be added on top without damaging anything?

That produced the next three variants.

| Version | Total PnL | Difference vs `v24` | Change |
| --- | ---: | ---: | --- |
| `trader_v42` | 602,642 | +900 | full `v24` book + `v27` far-strike passive 0/1 logic |
| `trader_v43` | 602,642 | +900 | same as `v42`, but far-strike quote size raised to 15 |
| `trader_v44` | 602,642 | +900 | same as `v42`, but far-strike quote size raised to 30 |

### Batch 2 findings

1. The additive hypothesis was correct.
   - `trader_v42` beat `v24` by exactly `900`.
   - That came from adding `VEV_6000: +450` and `VEV_6500: +450` while leaving the rest of the `v24` book intact.

2. The far-strike regime is real, but size-insensitive in this backtest.
   - `trader_v42`, `trader_v43`, and `trader_v44` all produced the exact same total.
   - That means the `VEV_6000` / `VEV_6500` passive edge appears to be fill-limited by the environment rather than by our posted size.

3. This was a clean win because it did not require changing the profitable core.
   - No degradation in `HYDROGEL_PACK`
   - No degradation in `VELVETFRUIT_EXTRACT`
   - No degradation in `VEV_4000` through `VEV_5500`
   - Only additive far-strike improvement

## Best Hybrid So Far

Current best hybrid:
- `trader_v42`: `602,642`

It is now the best model tested in this workspace.

Aggregate product PnL for `trader_v42`:
- `HYDROGEL_PACK`: 137,772
- `VELVETFRUIT_EXTRACT`: 87,908
- `VEV_4000`: 44,785
- `VEV_4500`: 49,563
- `VEV_5000`: 86,591
- `VEV_5100`: 83,634
- `VEV_5200`: 65,860
- `VEV_5300`: 25,847
- `VEV_5400`: 17,513
- `VEV_5500`: 2,269
- `VEV_6000`: 450
- `VEV_6500`: 450

## Final Read On The Hybrid Exercise

1. The strongest reusable core is the `v24` core, not a blend or a safer rewrite.

2. `v27` contributed one thing that was genuinely additive: the passive 0/1 far-strike regime.

3. `trader_v19` was useful for diagnosis but not for replacing the best open-source underlier engine.

4. The catastrophic models were still useful. They pointed toward where not to add complexity:
   - middle-cluster relative-value overlays
   - aggressive local residual mean reversion
   - inventory-skew overlays in the upper-middle strip

5. The best result from this full hybrid pass was not a complicated synthesis. It was:
   - keep the `v24` book intact
   - add the one `v27` component that was clearly orthogonal and profitable

## Files Added In This Iteration

- [hybrid_round3_core.py](/Users/pranavkapur2/Code/prosperity-trading/src/round3/hybrid_round3_core.py)
- [trader_v37.py](/Users/pranavkapur2/Code/prosperity-trading/src/round3/trader_v37.py)
- [trader_v38.py](/Users/pranavkapur2/Code/prosperity-trading/src/round3/trader_v38.py)
- [trader_v39.py](/Users/pranavkapur2/Code/prosperity-trading/src/round3/trader_v39.py)
- [trader_v40.py](/Users/pranavkapur2/Code/prosperity-trading/src/round3/trader_v40.py)
- [trader_v41.py](/Users/pranavkapur2/Code/prosperity-trading/src/round3/trader_v41.py)
- [trader_v42.py](/Users/pranavkapur2/Code/prosperity-trading/src/round3/trader_v42.py)
- [trader_v43.py](/Users/pranavkapur2/Code/prosperity-trading/src/round3/trader_v43.py)
- [trader_v44.py](/Users/pranavkapur2/Code/prosperity-trading/src/round3/trader_v44.py)
