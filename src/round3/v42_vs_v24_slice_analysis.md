# `v42` vs `v24` Timestamp-Slice Analysis

## Executive Summary

`v42` differs from `v24` in exactly one economically meaningful way:
- `v42` adds a passive far-strike regime on `VEV_6000` and `VEV_6500`
- `v24` does not trade those names at all

On the default backtester settings, that adds exactly `+900` total PnL.
On stricter trade matching settings, it adds `0`.

## Exact Code Difference

`v24` trades:
- `HYDROGEL_PACK`
- `VELVETFRUIT_EXTRACT`
- `VEV_4000` through `VEV_5500`

Reference:
- [v24.py](/Users/pranavkapur2/Code/prosperity-trading/src/round3/v24.py#L238)
- [v24.py](/Users/pranavkapur2/Code/prosperity-trading/src/round3/v24.py#L261)

`v42` reproduces that full book and adds:
- `VEV_6000: {"wide_quote_size": 7}`
- `VEV_6500: {"wide_quote_size": 7}`

Reference:
- [trader_v42.py](/Users/pranavkapur2/Code/prosperity-trading/src/round3/trader_v42.py#L47)

The added logic is implemented here:
- [hybrid_round3_core.py](/Users/pranavkapur2/Code/prosperity-trading/src/round3/hybrid_round3_core.py#L352)

That routine:
1. checks whether the far-strike book is exactly `bid=0`, `ask=1`
2. if yes, posts a buy at `0`
3. if yes, also posts a sell at `1`
4. if not, does nothing

## Backtester Robustness Check

Using the same code on different backtester matching modes:

| Matching mode | `v24` | `v42` | Delta |
| --- | ---: | ---: | ---: |
| `all` | 601,742 | 602,642 | +900 |
| `worse` | 598,558 | 598,558 | 0 |
| `none` | 587,297 | 587,297 | 0 |

Interpretation:
- the `v42` improvement is not coming from a broader improvement in valuation or execution
- it comes specifically from the default `match_trades=all` convention in the backtester

Relevant backtester settings and behavior:
- default matching mode is `all`: [__main__.py](/Users/pranavkapur2/Code/prosperity-trading/backtester/prosperity3bt/__main__.py#L193)
- buy orders can match market sells at the same price under `all`: [runner.py](/Users/pranavkapur2/Code/prosperity-trading/backtester/prosperity3bt/runner.py#L175)
- positions are marked to mid price every timestamp: [runner.py](/Users/pranavkapur2/Code/prosperity-trading/backtester/prosperity3bt/runner.py#L91)

## What The Far-Strike Data Actually Looks Like

For both `VEV_6000` and `VEV_6500` across all three days:
- the best bid is always `0`
- the best ask is always `1`
- the mid price is always `0.5`
- every recorded market trade is at price `0`
- there are no recorded market trades at price `1`

This is a highly degenerate microstructure regime, not a rich sample of many states.

Even more unusually:
- `VEV_6000` and `VEV_6500` have identical trade tapes on each day

That means the far-strike add-on is not learning a nuanced surface effect. It is exploiting one repeated tape pattern twice.

## Timestamp Slice Path For The Added Regime

Assume the exact `v42` logic:
- post buy `7 @ 0`
- post sell `7 @ 1`
- cap position at `300`

Since market prints are only at `0`, the relevant side is the bid at `0`.

### `VEV_6000` and `VEV_6500` day 0
- first trade timestamp: `2,900`
- fill path by time slice:
  - `250,000`: position `99`, mark PnL `49.5`
  - `500,000`: position `162`, mark PnL `81.0`
  - `750,000`: position `236`, mark PnL `118.0`
  - `999,900`: position `300`, mark PnL `150.0`
- cap reached at timestamp: `941,200`

### Day 1
- first trade timestamp: `4,500`
- fill path by time slice:
  - `250,000`: position `97`, mark PnL `48.5`
  - `500,000`: position `151`, mark PnL `75.5`
  - `750,000`: position `260`, mark PnL `130.0`
  - `999,900`: position `300`, mark PnL `150.0`
- cap reached at timestamp: `851,200`

### Day 2
- first trade timestamp: `13,100`
- fill path by time slice:
  - `250,000`: position `72`, mark PnL `36.0`
  - `500,000`: position `187`, mark PnL `93.5`
  - `750,000`: position `266`, mark PnL `133.0`
  - `999,900`: position `300`, mark PnL `150.0`
- cap reached at timestamp: `898,600`

## Why Quote Size 7, 15, And 30 All Produced The Same Result

We tested that in `trader_v42`, `trader_v43`, and `trader_v44`.
They all finished at `602,642`.

Reason:
- each day has 91 to 98 trade timestamps in the far strikes
- to reach the `300` cap by end of day, the strategy only needs quote size `4`
- any quote size above that saturates the cap anyway

So these all collapse to the same effective behavior:
- buy until `300`
- hold until day end
- mark inventory at `0.5`

## What Happens If There Are More Samples In Actual Testing

This depends on what "more samples" means.

### Case 1: More timestamps, same regime
If the future scenario is still:
- book always `0/1`
- trades always at `0`

then the current logic will:
- keep buying at `0`
- hit the `300` cap
- stop gaining from extra trade flow after the cap is reached

So more observations of the same regime do not create unlimited upside.
They only make it easier to reach the same capped outcome sooner.

### Case 2: Still `0/1`, but trades start occurring at `1`
Then the posted ask at `1` could start filling.
In that regime the strategy would become a real two-sided market maker instead of a pure inventory accumulator.

Current data gives no evidence for this regime, so we do not know whether it would help or hurt.

### Case 3: The book stops being exactly `0/1`
The current logic turns off entirely.
That is by design.

This makes the rule robust to one kind of model error:
- it does not pretend to know fair value once the dead-market pattern breaks

But it also means:
- it cannot adapt if the far strikes start behaving like real options

### Case 4: Same trade tape, but different matching rules
This already happened in our robustness test.
Under `worse` and `none`, the edge disappears.

So this regime is sensitive not just to market state, but also to the simulator's matching convention.

## Practical Interpretation

`v42` is better than `v24` in the current default backtester.
But the improvement is narrow:
- no core-book improvement
- no underlier improvement
- no middle-strike improvement
- only a far-strike add-on that depends on a persistent `0/1` market and equal-price trade matching

The safest way to think about it is:
- `v24` is the stronger structural benchmark
- `v42` is the stronger backtester-optimized candidate
