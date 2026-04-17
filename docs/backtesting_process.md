# Backtesting Process

This file defines how experiments should be run and recorded so iteration stays disciplined.

## Purpose

Backtests are for ranking hypotheses, catching regressions, and inspecting behavior. They are not a perfect forecast of official submission PnL.

## Evidence Hierarchy

Use evidence in this order:

1. structural reasoning about how the market was likely generated,
2. descriptive notebook analysis,
3. targeted fast backtests in notebooks or scripts,
4. full trader runs in the local backtester,
5. official website behavior when local tooling cannot model the important interaction.

This ordering is deliberate. Strong prior teams repeatedly stressed that blindly optimizing indicators against historic data is a fast route to overfitting.

## Minimum Experiment Loop

1. State the hypothesis before editing code.
2. Make the smallest change that tests it.
3. Run local backtests on all available days for the round.
4. Review per-product and total results.
5. Record the outcome in the experiment log.

## What To Check

- Total PnL across days.
- Per-day consistency.
- Per-product contribution.
- Signs of limit rejections or pathological inventory behavior.
- Whether profit depends on a narrow corner case.
- Whether the result still makes sense under a simple story of market structure.

## Analysis Rules

- Start with a hypothesis stated in plain English.
- Use indicators to test hypotheses, not to generate them after the fact.
- Prefer a small number of diagnostics that answer real questions.
- Test alternative explanations before concluding that a pattern is real.
- Explicitly look for failure cases that would invalidate the strategy.

Examples:

- rolling z-score: does deviation from a rolling reference actually revert?
- EMA crossover: is there real short-horizon directional persistence?
- forward returns after spikes: are shocks reversed or continued?
- large-trade analysis: do specific sizes or trade locations carry predictive information?

## Comparison Rules

- Compare against the current baseline, not memory.
- Change one thing at a time when possible.
- Keep notes on parameters that were tried and rejected.
- If a result improves one day and collapses another, treat it as unstable until explained.
- Prefer stable parameter regions over sharp maxima.

## Logging Standard

Each meaningful test should record:

- what changed,
- what was expected,
- what happened,
- whether the hypothesis survived,
- the next action.

## Submission Standard

A strategy is a plausible submission candidate if it:

- beats the current local baseline,
- does not rely on obvious rule violations or fragile assumptions,
- behaves sanely across all available days,
- has no known limit-handling bug,
- has a clear reason for why it should work.

## Practical Notes

- Notebook exploration can be noisy; the experiment log should contain only decisions.
- If backtester behavior differs materially from the official environment, document the uncertainty explicitly.
- Keep old logs; they are useful when a future change accidentally recreates a previously rejected idea.
- Use the official environment as a secondary validation tool when bot interaction or fill behavior is central.
