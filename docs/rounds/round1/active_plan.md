# Round 1 Active Plan

## Priority Now

1. Analyze Round 1 price and trade data in the notebook.
2. Confirm the baseline behavior of Pepper Root and Osmium.
3. Test fair-value candidates before deciding on strategy shape.
4. Translate the first credible hypotheses into a Round 1 trader baseline.

## After That

1. Backtest product-specific baselines independently and together.
2. Refine execution and inventory handling after alpha is roughly correct.
3. Snapshot meaningful strategy milestones in `strategies/`.
4. Add compact structured logging before debugging more complex live behavior.

## Blocked / Waiting

- Additional external code and writeups from prior teams are still to be added and reviewed.
- Strategy architecture should stay lightweight until the Round 1 products are better understood.

## Submission Criteria

- Round 1 strategy should beat the tutorial baseline adapted to new products.
- Behavior should be consistent across available Round 1 days.
- No obvious position-limit handling mistakes.
- Each product should have a written explanation for why the chosen logic matches the data.
- Indicators used in the final strategy should each have a documented reason to exist.
