# External References

This file is a concise map of outside repos, writeups, and code we may draw from. The point is to capture why a source matters and how to use it safely.

## Current Core References

### IMC Wiki / Official Materials

- Use for ground-truth rules, datamodel semantics, and round-specific mechanics.
- Do not infer strategy from official examples; use them for constraints and interface only.

### Mark Brezina Repo

- Useful for high-level framing around alpha, execution, inventory, and prior-round patterns.
- Most valuable as a conceptual index and source list.
- Best use: hypothesis generation and vocabulary, not direct strategy adoption.

### Frankfurt Hedgehogs / 2nd Place

Useful for:

- strong decomposition into product traders,
- compact logger design,
- take / make execution logic,
- careful emphasis on structural reasoning before indicator chasing,
- the repeated idea that “wall mid” or filtered quoting can be a better fair-value proxy than naive mid-price.

Borrow:

- logger pattern,
- product-handler structure,
- fair-value-first mindset,
- execution decomposition,
- caution against overfitting fancy indicators without a market-structure story.

Do not trust directly:

- specific thresholds,
- informed-trader assumptions,
- year-specific bot behaviors,
- any constants fitted to their products.

### CMU Physics / 7th Place

Useful for:

- practical Round 1 notebook diagnostics,
- volatility-spike testing,
- forward-return analysis after unusual moves,
- clear writeup of what failed as well as what worked,
- the lesson that sometimes a product is too unstable for full-size market making.

Borrow:

- notebook workflow,
- spike / reversal diagnostics,
- product-by-product postmortem style,
- emphasis on position sizing and variance control.

Do not trust directly:

- the belief that this year’s dynamic product behaves like last year’s Squid Ink,
- specific z-score windows or thresholds,
- any conclusions drawn from prior trader-ID or anonymous-size signals.

### Alpha Animals / 9th Place

Useful for:

- another concrete logger implementation,
- practical market-making utilities,
- additional examples of basket and option decomposition,
- more evidence that prior teams often reused architecture and adapted only the product logic.

Borrow:

- compact log truncation ideas,
- basic product order helper design,
- idea of keeping inactive products explicitly off,
- evidence that simple filtered fair-value estimation can outperform more elaborate modeling.

Do not trust directly:

- complex all-round trader layout as a Round 1 starting point,
- the very large mixed strategy surface,
- any logic whose profitability depended on products we do not trade yet.

## Shared Lessons From Prior Teams

- The best teams repeatedly started from market structure, not from indicators.
- Fair value estimation and execution quality mattered more than most novice participants expected.
- Inventory handling was often a decisive edge.
- Public code is useful mostly as a pattern library and research accelerator.
- Strong teams documented what failed, which is often as valuable as what worked.

## How To Use External Code

- Extract the idea first.
- Write down what market structure it assumes.
- Test whether that structure exists in current Prosperity data.
- Only then adapt the implementation.

For this repo, external material should be classified as one of:

- reusable framework,
- hypothesis to test,
- year-specific detail to ignore until proven relevant.

## Anti-Patterns

- Do not dump raw links without commentary.
- Do not treat prior-year products as equivalent to current products.
- Do not import external architecture wholesale before understanding the tradeoffs.
- Do not copy exact parameters or thresholds into Round 1 before current-data validation.
