"""
Round 3 Manual Trading Challenge - EV Analysis
"The Celestial Gardeners' Guild"

Mechanics:
- Reserve prices: uniformly distributed 670-920 in increments of 5 (51 values)
- Submit two bids: b1 (lowest) and b2 (highest), where b1 <= b2
- Sell price next day: 920

Trade outcomes for each reserve price r:
1. If b1 >= r: trade at b1, profit = 920 - b1
2. If b1 < r <= b2 AND b2 > mean: trade at b2, profit = 920 - b2
3. If b1 < r <= b2 AND b2 <= mean: trade at b2 with penalty
   penalty = ((920 - mean) / (920 - b2))^3
   profit = (920 - b2) * penalty
4. If b2 < r: no trade, profit = 0
"""

import numpy as np
import pandas as pd
from typing import Tuple

# Constants
RESERVE_MIN = 670
RESERVE_MAX = 920
RESERVE_STEP = 5
SELL_PRICE = 920

RESERVES = np.arange(RESERVE_MIN, RESERVE_MAX + 1, RESERVE_STEP)
N_RESERVES = len(RESERVES)  # 51 values


def calculate_profit_per_reserve(b1: float, b2: float, mean: float, r: float) -> float:
    """
    Calculate profit for a single reserve price.

    Args:
        b1: first (lowest) bid
        b2: second (highest) bid
        mean: mean of other players' second bids
        r: reserve price

    Returns:
        profit from this reserve price scenario
    """
    if b1 >= r:
        # Scenario 1: first bid covers reserve
        return SELL_PRICE - b1
    elif b2 >= r:
        # b1 < r <= b2
        if b2 > mean:
            # Scenario 2: second bid beats mean
            return SELL_PRICE - b2
        else:
            # Scenario 3: second bid at or below mean - penalty applies
            if b2 >= SELL_PRICE:
                return 0  # edge case: no profit possible
            penalty = ((SELL_PRICE - mean) / (SELL_PRICE - b2)) ** 3
            return (SELL_PRICE - b2) * penalty
    else:
        # Scenario 4: both bids below reserve
        return 0


def calculate_ev(b1: float, b2: float, mean: float) -> float:
    """
    Calculate expected value for a bid pair given a mean.

    Each reserve price is equally likely (uniform distribution).
    """
    total_profit = sum(calculate_profit_per_reserve(b1, b2, mean, r) for r in RESERVES)
    return total_profit / N_RESERVES


def calculate_ev_breakdown(b1: float, b2: float, mean: float) -> dict:
    """
    Return detailed breakdown of EV by scenario.
    """
    scenario1_profit = 0
    scenario1_count = 0
    scenario2_profit = 0
    scenario2_count = 0
    scenario3_profit = 0
    scenario3_count = 0
    no_trade_count = 0

    for r in RESERVES:
        if b1 >= r:
            scenario1_profit += SELL_PRICE - b1
            scenario1_count += 1
        elif b2 >= r:
            if b2 > mean:
                scenario2_profit += SELL_PRICE - b2
                scenario2_count += 1
            else:
                if b2 < SELL_PRICE:
                    penalty = ((SELL_PRICE - mean) / (SELL_PRICE - b2)) ** 3
                    scenario3_profit += (SELL_PRICE - b2) * penalty
                scenario3_count += 1
        else:
            no_trade_count += 1

    return {
        "b1": b1,
        "b2": b2,
        "mean": mean,
        "scenario1_trades": scenario1_count,
        "scenario1_ev": scenario1_profit / N_RESERVES,
        "scenario2_trades": scenario2_count,
        "scenario2_ev": scenario2_profit / N_RESERVES,
        "scenario3_trades": scenario3_count,
        "scenario3_ev": scenario3_profit / N_RESERVES,
        "no_trade_count": no_trade_count,
        "total_ev": (scenario1_profit + scenario2_profit + scenario3_profit) / N_RESERVES,
    }


def find_optimal_bids(mean: float, b1_range: Tuple[float, float] = None,
                      b2_range: Tuple[float, float] = None,
                      step: float = 5) -> Tuple[float, float, float]:
    """
    Find optimal b1, b2 for a given mean.

    Returns: (optimal_b1, optimal_b2, max_ev)
    """
    if b1_range is None:
        b1_range = (RESERVE_MIN, RESERVE_MAX)
    if b2_range is None:
        b2_range = (RESERVE_MIN, RESERVE_MAX)

    best_ev = -float('inf')
    best_b1, best_b2 = None, None

    for b1 in np.arange(b1_range[0], b1_range[1] + 1, step):
        for b2 in np.arange(max(b1, b2_range[0]), b2_range[1] + 1, step):
            ev = calculate_ev(b1, b2, mean)
            if ev > best_ev:
                best_ev = ev
                best_b1, best_b2 = b1, b2

    return best_b1, best_b2, best_ev


def generate_ev_heatmap(mean: float, step: float = 10) -> pd.DataFrame:
    """
    Generate a heatmap of EV values for different b1, b2 combinations.
    """
    b1_vals = np.arange(RESERVE_MIN, RESERVE_MAX + 1, step)
    b2_vals = np.arange(RESERVE_MIN, RESERVE_MAX + 1, step)

    data = np.zeros((len(b1_vals), len(b2_vals)))

    for i, b1 in enumerate(b1_vals):
        for j, b2 in enumerate(b2_vals):
            if b2 >= b1:
                data[i, j] = calculate_ev(b1, b2, mean)
            else:
                data[i, j] = np.nan  # invalid: b2 must be >= b1

    return pd.DataFrame(data, index=b1_vals, columns=b2_vals)


def analyze_mean_sensitivity(b1: float, b2: float,
                             mean_range: Tuple[float, float] = (700, 900),
                             step: float = 10) -> pd.DataFrame:
    """
    Analyze how EV changes with different mean values.
    """
    means = np.arange(mean_range[0], mean_range[1] + 1, step)
    results = []

    for mean in means:
        breakdown = calculate_ev_breakdown(b1, b2, mean)
        results.append(breakdown)

    return pd.DataFrame(results)


def compare_strategies(means: list, step: float = 5) -> pd.DataFrame:
    """
    Compare optimal strategies across different assumed means.
    """
    results = []
    for mean in means:
        opt_b1, opt_b2, opt_ev = find_optimal_bids(mean, step=step)
        results.append({
            "mean": mean,
            "optimal_b1": opt_b1,
            "optimal_b2": opt_b2,
            "optimal_ev": opt_ev,
            "b2_vs_mean": opt_b2 - mean,
        })
    return pd.DataFrame(results)


def analyze_b2_around_mean(b1: float, mean: float,
                           b2_offsets: list = None) -> pd.DataFrame:
    """
    Analyze EV for b2 values around the mean (since optimal b2 is often near mean).
    """
    if b2_offsets is None:
        b2_offsets = list(range(-50, 55, 5))

    results = []
    for offset in b2_offsets:
        b2 = mean + offset
        if b2 < b1 or b2 < RESERVE_MIN or b2 > RESERVE_MAX:
            continue
        breakdown = calculate_ev_breakdown(b1, b2, mean)
        breakdown["b2_offset_from_mean"] = offset
        results.append(breakdown)

    return pd.DataFrame(results)


# ============================================================================
# Main analysis
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("ROUND 3 MANUAL TRADING CHALLENGE - EV ANALYSIS")
    print("=" * 80)

    # 1. Optimal strategies for different assumed means
    print("\n" + "=" * 80)
    print("1. OPTIMAL STRATEGIES FOR DIFFERENT ASSUMED MEANS")
    print("=" * 80)

    test_means = [750, 775, 795, 800, 810, 820, 830, 840, 850, 860, 870]
    optimal_df = compare_strategies(test_means, step=5)
    print(optimal_df.to_string(index=False))

    # 2. EV breakdown for some specific strategies
    print("\n" + "=" * 80)
    print("2. DETAILED BREAKDOWN FOR SAMPLE STRATEGIES")
    print("=" * 80)

    # Conservative strategy: low b1, b2 just above expected mean
    sample_strategies = [
        (700, 810, 800, "Conservative: low b1, b2 above mean=800"),
        (750, 810, 800, "Moderate: mid b1, b2 above mean=800"),
        (800, 810, 800, "Aggressive: high b1, b2 above mean=800"),
        (700, 850, 840, "Conservative with higher mean=840"),
        (750, 850, 840, "Moderate with higher mean=840"),
        (700, 795, 800, "b2 below mean - penalty scenario"),
    ]

    for b1, b2, mean, desc in sample_strategies:
        print(f"\n{desc}")
        print(f"  b1={b1}, b2={b2}, assumed mean={mean}")
        bd = calculate_ev_breakdown(b1, b2, mean)
        print(f"  Scenario 1 (b1>=r): {bd['scenario1_trades']} trades, EV contribution: {bd['scenario1_ev']:.2f}")
        print(f"  Scenario 2 (b2>r, b2>mean): {bd['scenario2_trades']} trades, EV contribution: {bd['scenario2_ev']:.2f}")
        print(f"  Scenario 3 (b2>r, b2<=mean, penalty): {bd['scenario3_trades']} trades, EV contribution: {bd['scenario3_ev']:.2f}")
        print(f"  No trade: {bd['no_trade_count']} reserves")
        print(f"  TOTAL EV: {bd['total_ev']:.2f}")

    # 3. Sensitivity of a fixed strategy to mean
    print("\n" + "=" * 80)
    print("3. SENSITIVITY ANALYSIS: HOW DOES EV CHANGE WITH MEAN?")
    print("=" * 80)

    # Test a moderate strategy across different means
    test_b1, test_b2 = 750, 830
    print(f"\nStrategy: b1={test_b1}, b2={test_b2}")
    print("How does EV change as the actual mean varies?\n")

    sensitivity_df = analyze_mean_sensitivity(test_b1, test_b2, (750, 870), 10)
    print(sensitivity_df[["mean", "scenario1_ev", "scenario2_ev", "scenario3_ev", "total_ev"]].to_string(index=False))

    # 4. B2 optimization around the mean
    print("\n" + "=" * 80)
    print("4. B2 OPTIMIZATION AROUND MEAN (for fixed b1)")
    print("=" * 80)

    for mean in [790, 810, 830, 850]:
        print(f"\nMean = {mean}, b1 = 750")
        b2_analysis = analyze_b2_around_mean(750, mean)
        # Show just the key columns
        print(b2_analysis[["b2", "b2_offset_from_mean", "scenario2_ev", "scenario3_ev", "total_ev"]].to_string(index=False))

    # 5. Impact of b1 choice
    print("\n" + "=" * 80)
    print("5. IMPACT OF B1 CHOICE (for fixed mean and optimal b2)")
    print("=" * 80)

    mean = 820
    print(f"\nAssume mean = {mean}")
    print("For each b1, find optimal b2 and show EV:\n")

    b1_analysis = []
    for b1 in range(680, 830, 10):
        _, opt_b2, ev = find_optimal_bids(mean, b1_range=(b1, b1), step=5)
        b1_analysis.append({"b1": b1, "optimal_b2": opt_b2, "ev": ev})

    b1_df = pd.DataFrame(b1_analysis)
    print(b1_df.to_string(index=False))

    # 6. Robustness analysis - what if we're wrong about the mean?
    print("\n" + "=" * 80)
    print("6. ROBUSTNESS: WHAT IF WE'RE WRONG ABOUT THE MEAN?")
    print("=" * 80)

    print("\nCompare strategies optimized for different means, evaluated across actual means:\n")

    assumed_means = [790, 810, 830]
    actual_means = [780, 800, 820, 840, 860]

    robustness_data = []
    for assumed in assumed_means:
        opt_b1, opt_b2, _ = find_optimal_bids(assumed, step=5)
        row = {"strategy": f"opt for mean={assumed}", "b1": opt_b1, "b2": opt_b2}
        for actual in actual_means:
            ev = calculate_ev(opt_b1, opt_b2, actual)
            row[f"EV@mean={actual}"] = round(ev, 1)
        robustness_data.append(row)

    robustness_df = pd.DataFrame(robustness_data)
    print(robustness_df.to_string(index=False))

    # 7. Penalty deep dive
    print("\n" + "=" * 80)
    print("7. PENALTY DEEP DIVE: WHEN b2 <= mean")
    print("=" * 80)

    print("\nPenalty formula: ((920 - mean) / (920 - b2))^3")
    print("When b2 <= mean, this reduces profit significantly.\n")

    mean = 830
    print(f"Mean = {mean}")
    print(f"Effective profit multiplier for different b2 values:\n")

    for b2 in range(800, 835, 5):
        if b2 < SELL_PRICE:
            penalty = ((SELL_PRICE - mean) / (SELL_PRICE - b2)) ** 3
            base_profit = SELL_PRICE - b2
            effective_profit = base_profit * penalty
            print(f"  b2={b2}: base_profit={base_profit}, penalty={penalty:.3f}, effective={effective_profit:.2f}")

    # 8. Quick reference - EV heatmap for a specific mean
    print("\n" + "=" * 80)
    print("8. EV HEATMAP (mean=820, step=20 for readability)")
    print("=" * 80)
    print("Rows = b1, Columns = b2")

    heatmap = generate_ev_heatmap(820, step=20)
    print(heatmap.round(1).to_string())

    # 9. Floor guarantee analysis (inspired by French team)
    print("\n" + "=" * 80)
    print("9. FLOOR GUARANTEE ANALYSIS")
    print("=" * 80)

    # The (791, 920) strategy guarantees profit regardless of mean
    floor_b1, floor_b2 = 791, 920
    floor_profit = calculate_ev(floor_b1, floor_b2, 920) * N_RESERVES  # Total, not per-reserve
    print(f"\nFloor strategy (b1={floor_b1}, b2={floor_b2}):")
    print(f"  Guaranteed total profit: {floor_profit:.0f} (regardless of mean)")

    # For each strategy, calculate how much mean can exceed b2 before we lose to floor
    print("\nRobustness analysis: max mean before losing to floor strategy")
    print("(Higher = more robust)\n")

    test_strategies = [
        (750, 835, "Dashboard/my analysis"),
        (751, 836, "Level-0 optimal"),
        (771, 879, "French team"),
        (776, 891, "Teammate"),
        (760, 860, "Middle ground"),
        (770, 875, "Slight adjustment"),
    ]

    for b1, b2, desc in test_strategies:
        # Find max mean where we still beat floor
        max_mean = b2
        for test_mean in range(b2, 921):
            ev_total = calculate_ev(b1, b2, test_mean) * N_RESERVES
            if ev_total < floor_profit:
                max_mean = test_mean - 1
                break
            max_mean = test_mean

        ev_at_b2 = calculate_ev(b1, b2, b2) * N_RESERVES
        ev_at_max = calculate_ev(b1, b2, max_mean) * N_RESERVES
        margin = max_mean - b2

        print(f"  ({b1}, {b2}) {desc}")
        print(f"    EV if mean={b2}: {ev_at_b2:.0f}, Max mean before floor beats us: {max_mean}, Margin: +{margin}")

    # 10. Level-k simulation
    print("\n" + "=" * 80)
    print("10. LEVEL-K REASONING SIMULATION")
    print("=" * 80)

    print("\nStarting from level-0 (ignore penalty), iterate best responses:\n")

    level_results = []
    # Level 0: optimal ignoring penalty (find it)
    best_ev_l0 = -float('inf')
    best_l0 = (750, 835)
    for b1 in range(670, 921, 5):
        for b2 in range(b1, 921, 5):
            # Calculate EV assuming we always beat the mean (no penalty)
            ev = sum(
                (SELL_PRICE - b1) if b1 >= r else
                (SELL_PRICE - b2) if b2 >= r else
                0
                for r in RESERVES
            ) / N_RESERVES
            if ev > best_ev_l0:
                best_ev_l0 = ev
                best_l0 = (b1, b2)

    level_results.append(("Level-0 (no penalty)", best_l0[0], best_l0[1], best_ev_l0))
    prev_b2 = best_l0[1]

    # Iterate levels
    for level in range(1, 6):
        assumed_mean = prev_b2
        opt_b1, opt_b2, opt_ev = find_optimal_bids(assumed_mean, step=5)
        level_results.append((f"Level-{level} (mean={assumed_mean})", opt_b1, opt_b2, opt_ev))

        if opt_b2 == prev_b2:
            print(f"Converged at level {level}!")
            break
        prev_b2 = opt_b2

    print(f"{'Level':<25} {'b1':<6} {'b2':<6} {'EV':<8}")
    print("-" * 50)
    for name, b1, b2, ev in level_results:
        print(f"{name:<25} {b1:<6} {b2:<6} {ev:<8.2f}")

    # 11. What if field is mixture of levels?
    print("\n" + "=" * 80)
    print("11. FIELD MIXTURE ANALYSIS")
    print("=" * 80)

    print("\nIf the field is a mixture of different sophistication levels:")
    print("(Estimating what the actual mean b2 might be)\n")

    # Get b2 values from level-k
    level_b2s = {i: level_results[i][2] for i in range(len(level_results))}

    mixtures = [
        ("Mostly naive (L0:50%, L1:30%, L2:20%)", {0: 0.5, 1: 0.3, 2: 0.2}),
        ("Balanced (L0:33%, L1:33%, L2:33%)", {0: 0.33, 1: 0.34, 2: 0.33}),
        ("Sophisticated (L0:20%, L1:30%, L2:50%)", {0: 0.2, 1: 0.3, 2: 0.5}),
        ("Very sophisticated + some naive 920", {0: 0.1, 1: 0.2, 2: 0.4, "naive_920": 0.3}),
    ]

    for name, weights in mixtures:
        weighted_b2 = 0
        total_w = sum(weights.values())
        for k, w in weights.items():
            if k == "naive_920":
                weighted_b2 += (w / total_w) * 920
            elif k < len(level_b2s):
                weighted_b2 += (w / total_w) * level_b2s[k]

        print(f"  {name}")
        print(f"    Estimated field mean b2: {weighted_b2:.0f}")

        # What's optimal given this mean?
        opt_b1, opt_b2, opt_ev = find_optimal_bids(weighted_b2, step=5)
        print(f"    Optimal response: b1={opt_b1}, b2={opt_b2}, EV={opt_ev:.1f}")
        print()

    print("\n" + "=" * 80)
    print("SUMMARY INSIGHTS")
    print("=" * 80)
    print("""
Key observations:
1. Optimal b2 is typically 5-15 above the mean (to capture scenario 2 without penalty)
2. Lower b1 gives higher per-trade profit but fewer guaranteed trades
3. The penalty for b2 <= mean is severe (cubic), making scenario 3 rarely profitable
4. Strategy robustness: if uncertain about mean, slightly higher b2 is safer
   (better to be in scenario 2 than scenario 3)
5. Most EV typically comes from scenario 1 (guaranteed trades at b1)

Recommended approach:
- Estimate the mean of competitors' b2 (likely 800-850 range)
- Set b2 = mean + 5 to 15 (ensures scenario 2, not 3)
- Set b1 based on risk tolerance:
  - Lower b1 = higher profit per trade, fewer guaranteed trades
  - Higher b1 = lower profit per trade, more guaranteed trades
""")
