# INTARIAN_PEPPER_ROOT

## Market Read

Working hypothesis: Pepper Root is the more stable Round 1 product, but may be better modeled around a rolling trend or regression line than a flat constant fair value.

Prior-art analogs to test against:

- stationary market-making product,
- filtered-mid or wall-mid market-making product,
- de-trended mean-reversion product.

## Evidence To Confirm

- Mid-price shape over time.
- Spread distribution and quote stability.
- Autocorrelation of returns and mid-price deviations.
- Whether deviations from a short rolling trend revert reliably.
- Whether filtered large-quote mid is more stable than naive mid.
- Whether market trades contain useful directional information or are mostly noise.

## Candidate Strategy Shapes

- Regression-anchored market making.
- Rolling-fair-value mean reversion.
- Simple market taking around a dynamic fair value with passive quotes around it.

Candidate fair-value estimators to compare:

- naive top-of-book mid,
- filtered mid using larger quote sizes,
- wall-mid proxy,
- rolling EMA,
- short rolling regression forecast / trend anchor.

## Execution Questions

- Is the spread stable enough for passive market making?
- Does the best edge come from taking obvious mispricings or leaning on bot fills?
- How aggressively should inventory be flattened?
- Is undercutting / overbidding around visible quote walls consistently profitable?

## Risks / Failure Modes

- Treating a drifting process as stationary around a constant fair value.
- Overfitting the regression window.
- Making passive quotes that get picked off when the local trend shifts.
- Inferring a wall-mid structure that is not actually stable across days.

## Next Experiments

1. Plot mid-price and rolling regression fits across all available days.
2. Test residual mean reversion after de-trending.
3. Compare naive mid against filtered-mid and wall-mid proxies.
4. Build a very simple dynamic-fair-value baseline before adding complexity.
