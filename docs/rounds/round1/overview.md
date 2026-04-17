# Round 1 Overview

Round 1 currently appears to introduce two products with different market structures:

- `INTARIAN_PEPPER_ROOT`
- `ASH_COATED_OSMIUM`

## Working Read

- `INTARIAN_PEPPER_ROOT`: likely the more stationary or tightly modeled product, but not necessarily around a flat constant fair value. Current working idea is a stable process with a trend or regression-style reference.
- `ASH_COATED_OSMIUM`: likely the more dynamic or drifting product that will need an adaptive fair value or directional component.

## Prior-Art Expectations To Test

From strong previous teams, the most useful carryover expectations are:

- one Round 1 product may still reward classic market taking plus passive making around a robust fair value estimate,
- the other may require a moving or filtered anchor rather than a fixed fair value,
- filtered order-book signals such as wall mid or large-quote mid can be more useful than raw mid-price,
- volatility spikes or anonymous large trades may matter, but should be treated as secondary tests rather than primary assumptions.

## Current State Of The Repo

- The local backtester already contains Round 1 price and trade data.
- The current active trader in `src/trader.py` is still tutorial-oriented.
- The Round 1 notebook exists but is only a stub and needs proper analysis.

## Immediate Goals

1. Confirm the basic structure of each product from data.
2. Build a simple but defensible baseline strategy for each product.
3. Separate product-specific notes so strategy work does not collapse into one generic document.

## Key Unknowns

- Whether Pepper Root is best handled by fixed-fair market making, rolling regression, or another simple reference model.
- Whether Osmium is primarily drift, mean reversion around a moving target, or something more microstructure-driven.
- Whether market-taking or passive quoting dominates the edge for each product.
- Whether filtered quote walls exist strongly enough to justify wall-mid-style fair values.
- Whether any recurring trade-size or trade-location pattern carries informational value.

## Analysis Rules For This Round

- Start from descriptive plots and market-structure questions.
- Use indicators only to test concrete hypotheses.
- Actively look for disconfirming evidence.
- Prefer simple explanations that survive across all available days.
- Do not let prior-year product analogies override current-year evidence.

## Linked Notes

- `active_plan.md`
- `intarian_pepper_root.md`
- `ash_coated_osmium.md`
- `experiment_log.md`
