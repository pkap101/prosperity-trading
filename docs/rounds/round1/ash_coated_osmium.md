# ASH_COATED_OSMIUM

## Market Read

Working hypothesis: Osmium is the more dynamic Round 1 product and likely requires an adaptive fair value rather than a fixed anchor.

Prior-art analogs to test against:

- drift / trend product,
- volatility-spike reversal product,
- moving-target mean-reversion product,
- product with occasional informed-flow-like trade clusters.

## Evidence To Confirm

- Directionality and persistence of short-horizon moves.
- Whether price changes are better described by drift, momentum, or moving-target mean reversion.
- Fill opportunities from passive quotes versus aggressive taking.
- Whether extreme moves have positive or negative forward returns.
- Whether recurring trade sizes or extrema trades carry predictive information.

## Candidate Strategy Shapes

- Short-horizon trend or drift-aware fair value.
- Mean reversion around a moving average or filtered price estimate.
- Hybrid execution: take obvious extremes, otherwise quote around an adaptive center.

Candidate diagnostics to run:

- rolling z-score around several windows,
- EMA short / EMA long differentials,
- forward-return tests after extreme one-step or multi-step moves,
- large-trade overlays on mid-price,
- lagged return autocorrelation.

## Execution Questions

- Does passive quoting survive adverse selection?
- Is there enough edge in simple moving-average logic, or does it need stronger filtering?
- How much inventory should be tolerated before switching to defensive behavior?
- Is the product too volatile for full-size passive making?

## Risks / Failure Modes

- Using a lagging fair value and repeatedly fading real trend.
- Letting inventory accumulate against persistent movement.
- Mistaking backtester-specific fills for true edge.
- Finding “signal” in a diagnostic only because enough windows were tried.

## Next Experiments

1. Measure short-horizon predictive power of simple moving averages and regression signals.
2. Compare passive versus aggressive variants on the same fair value model.
3. Test spike-reversal and trend-persistence hypotheses explicitly with forward returns.
4. Add explicit inventory stress checks before increasing strategy complexity.
