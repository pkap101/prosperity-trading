# Challenge Rules

This file captures stable Prosperity mechanics that materially affect strategy design and implementation.

## Core Runtime Model

- The submission is a Python `Trader` class with a required `run()` method.
- `run()` receives a `TradingState` each iteration and returns `(orders, conversions, traderData)`.
- Final simulation length is longer than local development runs, so strategies must generalize beyond a short sample.

## TradingState Inputs

- `order_depths`: visible buy and sell quotes from bots.
- `own_trades`: fills involving the submission since the previous iteration.
- `market_trades`: trades between other participants since the previous iteration.
- `position`: current signed inventory by product.
- `observations`: optional observation/conversion data.
- `traderData`: serialized state from the previous call.

## Order Mechanics

- Prosperity uses limit orders.
- Positive quantity means buy; negative quantity means sell.
- Crossing visible liquidity fills immediately against the resting quote price.
- Remaining unmatched quantity can rest for the iteration and may be traded on by bots.
- Unfilled player orders are canceled before the next iteration.

## Position Limits

- Limits are enforced per product on absolute position.
- If the aggregate buy or sell orders for a product would breach the limit if fully filled, all orders for that product are rejected for that iteration.
- Position handling must be done per product before sending orders.

## Persistence Constraints

- The environment is effectively stateless across calls except for `traderData`.
- Class/global state should not be trusted across iterations.
- `traderData` should stay well below the platform cut-off to remain restorable and safe.

## Performance Constraints

- `run()` must be lightweight and deterministic enough to finish comfortably within the platform time budget.
- Heavy analysis belongs offline in notebooks or scripts, not inside the live trader.
- Logging must also be lightweight. Raw `print()` debugging in the live trader should be avoided in favor of compact, structured logging.

## Libraries

- Standard Python libraries are supported.
- `pandas`, `numpy`, `statistics`, `math`, `typing`, and `jsonpickle` are allowed.
- External unsupported packages should not be introduced into submission logic.

## Practical Implications

- Separate research code from submission code.
- Treat fair value, execution, and inventory control as first-class concerns.
- Favor simple models that are robust and cheap to compute online.
- Use local backtests for rapid iteration, but do not assume exact parity with the official environment.
- Do not rely on class state unless it is reconstructible from `traderData`.
