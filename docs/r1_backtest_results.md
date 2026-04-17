# Round 1 Strategy Comparison Results

This document summarizes the backtest performance of 8 open-sourced trader implementations on Round 1 data (days -2, -1, 0).

**Important caveat:** These backtests run on historical training data. The actual competition uses completely separate test data, so strategies that appear optimal here may be overfit to training data patterns.

---

## Overall Rankings

| Rank | Trader | Source | Osmium | Pepper Root | Total |
|------|--------|--------|--------|-------------|-------|
| 1 | copy1-1 | slu-imc-prosperity-4 | 55,235 | 238,338 | **293,573** |
| 2 | copy1-4 | Xa4-wi/Prosperity | 51,420 | 238,409 | **289,829** |
| 3 | copy1-6 | ANAIprosperity | 46,786 | 238,054 | **284,840** |
| 4 | copy1-5 | kernel_trick | 36,598 | 238,054 | **274,652** |
| 5 | copy1-2 | prosperity_4_squad_gang | 5,572 | 238,054 | **243,626** |
| 6 | copy1-3 | darwinian-alpha | 21,670 | 63,926 | **85,596** |
| 7 | copy1-7 | squilliam34 | 20,317 | 13,905 | **34,223** |
| 8 | copy1-8 | Nicholas-Lucky | 0 | -220,998 | **-220,998** |

---

## Per-Day Breakdown

### Day -2
| Trader | Osmium | Pepper Root | Total |
|--------|--------|-------------|-------|
| copy1-1 | 18,114 | 79,649 | 97,763 |
| copy1-4 | 16,998 | 79,644 | 96,642 |
| copy1-6 | 14,350 | 79,543 | 93,893 |
| copy1-5 | 11,621 | 79,543 | 91,164 |
| copy1-2 | 1,667 | 79,543 | 81,210 |
| copy1-3 | 6,606 | 20,989 | 27,595 |
| copy1-7 | 7,126 | 4,702 | 11,829 |
| copy1-8 | 0 | -74,920 | -74,920 |

### Day -1
| Trader | Osmium | Pepper Root | Total |
|--------|--------|-------------|-------|
| copy1-1 | 19,816 | 79,308 | 99,124 |
| copy1-4 | 17,371 | 79,368 | 96,739 |
| copy1-6 | 17,958 | 79,192 | 97,150 |
| copy1-5 | 13,310 | 79,192 | 92,502 |
| copy1-2 | 2,271 | 79,192 | 81,463 |
| copy1-3 | 7,824 | 21,541 | 29,365 |
| copy1-7 | 6,725 | 4,686 | 11,411 |
| copy1-8 | 0 | -74,317 | -74,317 |

### Day 0
| Trader | Osmium | Pepper Root | Total |
|--------|--------|-------------|-------|
| copy1-1 | 17,305 | 79,381 | 96,686 |
| copy1-4 | 17,051 | 79,397 | 96,448 |
| copy1-6 | 14,478 | 79,319 | 93,797 |
| copy1-5 | 11,667 | 79,319 | 90,986 |
| copy1-2 | 1,634 | 79,319 | 80,953 |
| copy1-3 | 7,240 | 21,396 | 28,636 |
| copy1-7 | 6,466 | 4,517 | 10,983 |
| copy1-8 | 0 | -71,761 | -71,761 |

---

## INTARIAN_PEPPER_ROOT Analysis

### Market Structure
- **Behavior:** Linear upward trend, +1000 ticks/day (slope ~0.001/timestamp)
- **Optimal strategy:** Buy-and-hold at max position (80 units)
- **Expected daily PnL:** ~80,000 (80 units × 1000 tick drift)

### Strategy Comparison

| Tier | Traders | Pepper PnL | Approach |
|------|---------|------------|----------|
| **Optimal** | copy1-1, copy1-2, copy1-4, copy1-5, copy1-6 | ~238,000 | Max long, aggressive accumulation |
| **Suboptimal** | copy1-3 | 63,926 | Position limit set to 20 instead of 80 |
| **Broken** | copy1-7 | 13,905 | Barely trades, likely bug or over-conservative |
| **Inverted** | copy1-8 | -220,998 | Appears to be shorting a trending product |

### Key Findings

1. **The trend is the entire edge.** All functioning strategies achieve ~79k/day by simply holding max long. There is no alpha in sophisticated Pepper Root trading beyond "buy everything, hold forever."

2. **Execution differences are noise.** The ~300 tick variance between top performers (238,054 vs 238,409) is negligible execution timing, not strategy alpha.

3. **Position limits matter.** copy1-3 loses ~174k simply by using limit=20 instead of limit=80.

4. **Directional mistakes are catastrophic.** copy1-8 loses ~75k/day by trading against the trend.

### Overfitting Concerns

**Low risk for Pepper Root strategies IF the trend continues on test data.**

The trend-following approach is structurally sound:
- Based on clear market structure (linear drift)
- No parameter tuning involved (just max long)
- Consistent across all 3 training days

**However:** If test data has a different trend (slower, faster, or reversed), all "optimal" strategies will perform identically poorly. The lack of any adaptive mechanism is a double-edged sword.

---

## ASH_COATED_OSMIUM Analysis

### Market Structure
- **Behavior:** Mean-reverting around fair value ~10,000
- **Spread:** ~16 ticks (wide enough for profitable market-making)
- **Autocorrelation:** AR(1) with lag-1 ACF ~-0.50 (mean-reversion)

### Strategy Comparison

| Rank | Trader | Osmium PnL | Fair Value Method | Key Mechanism |
|------|--------|------------|-------------------|---------------|
| 1 | copy1-1 | 55,235 | Kalman filter + micro-price | Smooth adaptive FV tracking |
| 2 | copy1-4 | 51,420 | Multi-signal blend (anchor + wall-mid + micro) | Tiered takes, toxic-book detection |
| 3 | copy1-6 | 46,786 | Fixed 10,000 | Aggressive position-aware edge reduction |
| 4 | copy1-5 | 36,598 | Naive mid (has better options unused) | Basic inventory-skewed MM |
| 5 | copy1-3 | 21,670 | Fixed 10,000 | Limited by position cap (20) |
| 6 | copy1-7 | 20,317 | Unknown | Underperforming |
| 7 | copy1-2 | 5,572 | Fixed 10,000 | Minimal MM, conservative edges |
| 8 | copy1-8 | 0 | N/A | Does not trade Osmium |

### Strategy Deep Dive

#### copy1-1: Kalman Filter (Best)
```
micro = (best_bid × ask_vol + best_ask × bid_vol) / total_vol
kalman_fair = smoothed tracking of micro-price
```
- Uses micro-price as observation signal (PhD-level microstructure)
- Kalman filter provides smooth, responsive fair value
- Conservative take bounds: max(10000, kalman_fair) for buys, min(10000, kalman_fair) for sells
- Clear inventory at fair ± 2 (tightens to ±1 at high inventory)

#### copy1-4: Multi-Signal Blend (Second)
```
fair = 0.42 × anchor(10000) + 0.58 × stable_mid + 0.42 × (micro - mid) + imbalance_bias
reservation = fair - inventory_skew × position - cubic_curve
```
- Sophisticated fair value combining multiple signals
- Tiered takes at edges -1, 1.5, 4.5 with sizes 6, 10, 16
- Toxic-book detection reduces aggression when imbalance is adverse
- Two-level passive ladder with market-join snapping

#### copy1-6: Simple but Effective (Third)
```
fair = 10000 (always)
edge = 0 if |pos| > 25, 1 if |pos| > 8, else 2
```
- Simplest fair value (just the anchor)
- Aggressive unwinding: edge drops to 0 at high inventory
- Proves sophisticated FV isn't required if execution is smart

#### copy1-5: Misconfigured (Fourth)
- Has sophisticated strategies (`hybrid`, `make_rev`) but runs `naive`
- Testing showed `make_rev` is marginally better (+86) but not transformative
- Pure taking (`take` mode) performed 70% worse than making strategies

### Key Findings

1. **Fair value quality is the primary differentiator.** copy1-1's Kalman filter outperforms copy1-4's more complex blend by ~4k.

2. **Market-making dominates taking for Osmium.** copy1-5's `take` mode (pure taking) earned only 11k vs 37k for making strategies. The spread income is more reliable than arbitrage opportunities.

3. **Simplicity can compete.** copy1-6's fixed FV + aggressive unwinding (46k) beats copy1-5's sophisticated microprice model (37k).

4. **Inventory management is critical.** All top performers have clear position-aware adjustments. copy1-6's "edge=0 at |pos|>25" is particularly effective.

5. **Micro-price captures information.** Both top performers (copy1-1, copy1-4) use micro-price weighting to detect order flow pressure.

### Overfitting Concerns

**Moderate to high risk for Osmium strategies.**

Potential overfitting vectors:

| Concern | Risk Level | Affected Strategies |
|---------|------------|---------------------|
| **Kalman parameters** | Medium | copy1-1 (latent_var=0.141, obs_var=6.656) |
| **Tiered take thresholds** | High | copy1-4 (edges -1, 1.5, 4.5 with specific sizes) |
| **Anchor assumption** | Medium | All (assuming FV = 10000 exactly) |
| **Spread assumptions** | Medium | copy1-6 (only makes when spread ≥ 4) |
| **Inventory thresholds** | Low-Medium | copy1-6 (pos > 25, pos > 8) |

**Most likely to generalize:**
- copy1-6: Minimal parameters, structural assumptions (mean-reversion exists, inventory matters)
- copy1-1: Kalman filter is a principled approach, though specific variances may need re-tuning

**Most likely to overfit:**
- copy1-4: Many tuned parameters (30+), highly optimized for training data patterns
- copy1-5 with `hybrid`: The taking thresholds appear miscalibrated even for training data

---

## Cross-Product Observations

### Independence of Strategies
- Pepper Root and Osmium performance appear independent
- No trader shows correlation between product performances
- This suggests separate, product-specific strategies are appropriate

### Complexity vs Performance

| Complexity | Example | Pepper Result | Osmium Result |
|------------|---------|---------------|---------------|
| Minimal | copy1-2 (max long + simple MM) | Optimal | Poor (5.5k) |
| Moderate | copy1-6 (max long + position-aware edges) | Optimal | Good (47k) |
| High | copy1-4 (sophisticated both) | Optimal | Great (51k) |
| Highest | copy1-1 (Kalman + micro-price) | Optimal | Best (55k) |

For Pepper Root, complexity doesn't help (the trend dominates).
For Osmium, complexity helps up to a point, but copy1-6 shows diminishing returns.

---

## Recommendations

### For Pepper Root
1. **Use max-long strategy** - any of the top 5 approaches work
2. **Ensure position limit is 80** - copy1-3's mistake is instructive
3. **No need for sophistication** - the trend is the only edge

### For Osmium
1. **Prioritize fair value estimation** - Kalman or filtered mid beats raw mid
2. **Prefer market-making over taking** - spread income is more reliable
3. **Implement aggressive inventory unwinding** - copy1-6's approach is robust
4. **Be wary of over-tuned parameters** - copy1-4's 30+ parameters are likely overfit

### For Test Data Robustness
1. **Validate trend assumption** - if Pepper doesn't trend on test data, all strategies fail equally
2. **Test Osmium anchor** - if true FV isn't 10000, anchored strategies will underperform
3. **Prefer structural over fitted** - copy1-6's approach (simple FV + smart execution) may generalize better than copy1-1's tuned Kalman

---

## Appendix: Strategy Variant Testing (copy1-5)

copy1-5 has multiple configurable strategies. Testing all variants:

| ACO_STRATEGY | Osmium PnL | vs Naive |
|--------------|------------|----------|
| make_rev | 36,684 | +0.2% |
| naive (default) | 36,598 | baseline |
| make | 35,775 | -2.2% |
| hybrid | 29,327 | -19.9% |
| take | 11,251 | -69.3% |

**Finding:** The "recommended" hybrid strategy actually underperforms naive. Pure making strategies cluster together; pure taking is significantly worse. The microprice-based fair value provides minimal edge over simple mid for this dataset.

---

## File References

- Source traders: `src/copy1-{1-8}.py`
- Backtest script: `scripts/backtest_comparison.py`
- Raw logs: `backtests/comparison/raw/`
- Summary CSV: `backtests/comparison/round1_latest.csv`
