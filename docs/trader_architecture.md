# Trader Architecture

This file describes the intended structure of the trading system as it evolves. It is a target design, informed by strong prior-team patterns, not a claim that the current code already matches it.

## Design Goals

- Keep the live trader simple, fast, and inspectable.
- Separate product-specific alpha from shared execution and inventory logic where possible.
- Make it easy to add new round products without rewriting everything.
- Keep enough structure that agents can work on one layer at a time.
- Borrow proven patterns from prior public code without inheriting their round-specific assumptions.

## Architecture Decisions

### 1. Compact Structured Logging

- The live trader should not use scattered `print()` statements.
- If logging is needed, use one compact logger that:
  - truncates output safely,
  - emits structured JSON-compatible payloads,
  - can omit bulky fields when needed,
  - keeps logs and `traderData` within size constraints.
- This pattern is clearly reusable from the strong public traders shared from prior years.

Good reusable idea:

```python
class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 2000

    def print(self, *objects, sep=" ", end="\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state, orders, conversions, trader_data) -> None:
        # compress, truncate, print once
        ...
```

Why this is worth keeping:

- One print at the end is controllable.
- Logs can be structured by product or subsystem.
- It avoids noisy debugging statements in the strategy path.

### 2. Shared Product Handler Pattern

- The trader should evolve toward small product handlers built on a thin shared utility layer.
- Prior public code showed a useful pattern:
  - one shared base object for market access and order helpers,
  - one small handler per product or product family,
  - one top-level trader that wires them together.

Good reusable idea:

```python
class ProductTrader:
    def __init__(self, name, state):
        self.name = name
        self.state = state
        self.position_limit = ...
        self.buy_orders, self.sell_orders = self.get_order_depth()
        self.best_bid, self.best_ask = self.get_best_bid_ask()

    def bid(self, price, volume):
        ...

    def ask(self, price, volume):
        ...
```

Why this is worth keeping:

- Shared helpers reduce repeated order-book boilerplate.
- Position-safe order methods make limit handling less error-prone.
- Product-specific logic stays local instead of turning `run()` into a giant switch.

### 3. Minimal Persistent State

- Persist only compact online state through `traderData`.
- Good candidates:
  - recent mid-price or fair-value history,
  - regime flags,
  - lightweight signal state,
  - experiment-specific counters if justified.
- Avoid storing raw long histories if a rolling summary is enough.

### 4. Fair Value First

- A strong repeated theme from prior teams: most good early-round logic was built around a robust fair value estimate, not around a large pile of indicators.
- Fair value estimators may differ by product:
  - fixed fair value for stationary assets,
  - filtered mid or wall mid for products with stable quoting walls,
  - rolling mean / EMA / regression for drifting products,
  - synthetic value for baskets,
  - pricing model for derivatives or conversions later.

## Core Layers

### 1. State Layer

- Restore and persist compact `traderData`.
- Track only what is needed online: recent prices, signal state, inventory metadata, and any compact regime flags.

### 2. Fair Value Layer

- Estimate a fair or reference value per product.
- This is the first thing to get right.
- Round 1 should explicitly test:
  - naive mid-price,
  - filtered mid-price,
  - wall-mid-style proxies,
  - moving averages,
  - rolling regression / trend anchor.

### 3. Alpha Layer

- Decide whether a product currently looks cheap, rich, or neutral versus the chosen reference.
- Product-specific logic belongs here.
- Keep this layer focused on prediction or mispricing detection, not direct order placement.
- Indicators are candidates, not truths.

Useful prior-art examples of candidate signals:

```python
z_score = (mid_price - rolling_mean) / rolling_std
ema_diff = ema_short - ema_long
momentum = mid_price - mid_price.shift(lag)
```

How to use them correctly:

- not as default strategy components,
- but as tests for specific hypotheses:
  - does deviation revert,
  - does trend persist,
  - do spikes reverse,
  - do large trades carry information.

### 4. Execution Layer

- Translate fair value and alpha into orders.
- Preferred baseline schema:
  1. take obvious edge,
  2. clear inventory when sensible,
  3. make passive markets when no better action exists.

This is the most reusable pattern from the strong public Round 1 traders.

Good reusable logic shape:

```python
for ask_price in sorted(order_depth.sell_orders):
    if ask_price <= fair_value - take_width:
        buy(...)

for bid_price in sorted(order_depth.buy_orders, reverse=True):
    if bid_price >= fair_value + take_width:
        sell(...)

quote_bid = fair_value - make_width
quote_ask = fair_value + make_width
```

Important caveat:

- prior teams often also improved on visible quote walls or undercut existing makers;
- that should be used only if the current book actually supports it.

### 5. Inventory and Risk Layer

- Enforce hard limits.
- Apply soft inventory controls before hard limits are reached.
- Skew quoting and sizing based on current position and product behavior.
- Many prior traders won partly because their inventory logic was saner than their competitors’, not because their alpha was much more sophisticated.

Reusable ideas:

- reduce quote size on the side that worsens current inventory,
- allow more size on the side that reduces inventory,
- flatten at low edge when risk capacity is more valuable than holding out for maximum edge,
- separate expected position from current position when coordinated products are traded.

## Product Handler Model

As the challenge grows, each product should have a small handler with:

- fair value logic,
- signal logic,
- execution parameters,
- position limit,
- any product-specific state requirements.

For Round 1, this should stay minimal:

- `PepperRootTrader`
- `OsmiumTrader`
- shared utility helpers
- shared logger

That is enough until the data forces more abstraction.

## What To Borrow From Prior Public Code

Borrow:

- compact logger pattern,
- shared order-book helpers,
- position-safe `bid` / `ask` wrappers,
- take / clear / make execution split,
- filtered fair-value estimation ideas,
- product-specific handler decomposition.

Do not borrow blindly:

- exact thresholds and windows,
- informed-trader logic,
- round-specific bot assumptions,
- hardcoded premiums or coefficients,
- broad multi-round frameworks that solve products we do not have yet.

## Development Priorities

- First: correct behavior and clean evaluation.
- Second: reusable helper functions for repeated patterns.
- Third: deeper abstraction only when at least two products benefit from it.

## Anti-Goals

- Do not over-engineer the architecture before Round 1 alpha is understood.
- Do not turn notebooks into the production code path.
- Do not hide critical execution decisions behind excessive abstraction.
- Do not let “nice-looking indicators” become de facto strategy logic without evidence.
