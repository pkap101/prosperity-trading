"""
Monte Carlo Strategy Tester for Round 4 Manual Trading
Tests all 4 team strategies with consistent methodology.
"""

import numpy as np

# ============================================================================
# Market Parameters
# ============================================================================

S0 = 50.0
SIGMA = 2.51  # 251% annualized
DT = 1.0 / (252 * 4)  # 4 steps per trading day

STEPS_2W = 10 * 4   # 40 steps = 2 trading weeks
STEPS_3W = 15 * 4   # 60 steps = 3 trading weeks

# Market prices
MARKET = {
    "AC":        {"bid": 49.975, "ask": 50.025},
    "AC_50_P":   {"bid": 12.00,  "ask": 12.05},
    "AC_50_C":   {"bid": 12.00,  "ask": 12.05},
    "AC_35_P":   {"bid": 4.33,   "ask": 4.35},
    "AC_40_P":   {"bid": 6.50,   "ask": 6.55},
    "AC_45_P":   {"bid": 9.05,   "ask": 9.10},
    "AC_60_C":   {"bid": 8.80,   "ask": 8.85},
    "AC_50_P_2": {"bid": 9.70,   "ask": 9.75},
    "AC_50_C_2": {"bid": 9.70,   "ask": 9.75},
    "AC_50_CO":  {"bid": 22.20,  "ask": 22.30},
    "AC_40_BP":  {"bid": 5.00,   "ask": 5.10},
    "AC_45_KO":  {"bid": 0.15,   "ask": 0.175},
}

# ============================================================================
# Strategy Definitions (positive = BUY, negative = SELL)
# ============================================================================

STRATEGIES = {
    "Team1_manual1py": {
        "AC":        -50,   # SELL 50
        "AC_35_P":   +50,   # BUY 50
        "AC_40_BP":  -50,   # SELL 50
        "AC_40_P":   +50,   # BUY 50
        "AC_45_KO":  -270,  # SELL 270
        "AC_45_P":   +50,   # BUY 50
        "AC_50_C":   +47,   # BUY 47
        "AC_50_CO":  -14,   # SELL 14
        "AC_50_C_2": +38,   # BUY 38
        "AC_50_P":   +50,   # BUY 50
        "AC_50_P_2": +40,   # BUY 40
        "AC_60_C":   +30,   # BUY 30
    },
    "Team2_simple": {
        "AC_50_P_2": +50,   # BUY 50
        "AC_50_C_2": +50,   # BUY 50
        "AC_50_CO":  -50,   # SELL 50
        "AC_40_BP":  -50,   # SELL 50
        "AC_45_KO":  +500,  # BUY 500
    },
    "Team3_cvxpy": {
        # From: AC_60_C=-50, AC_50_P_2=50, AC_50_C_2=50, AC_50_CO=-50, AC_40_BP=-50, AC_45_KO=-500
        "AC_60_C":   -50,   # SELL 50
        "AC_50_P_2": +50,   # BUY 50
        "AC_50_C_2": +50,   # BUY 50
        "AC_50_CO":  -50,   # SELL 50
        "AC_40_BP":  -50,   # SELL 50
        "AC_45_KO":  -500,  # SELL 500
    },
    "Team4_montecarlo": {
        # Arb: SELL 50 CO, BUY 50 C, BUY 50 P_2
        # Plus: AC_50_C_2=50, AC_45_KO=500, Spot_Net=-50 (LONG spot)
        "AC":        +50,   # BUY 50 (Spot_Net=-50 means LONG)
        "AC_50_CO":  -50,   # SELL 50 (arb)
        "AC_50_C":   +50,   # BUY 50 (arb)
        "AC_50_P_2": +50,   # BUY 50 (arb)
        "AC_50_C_2": +50,   # BUY 50 (grid)
        "AC_45_KO":  +500,  # BUY 500 (grid)
    },
}

# ============================================================================
# Simulation
# ============================================================================

def simulate_paths(n_paths=100000, seed=42):
    """Simulate GBM paths with antithetic variates."""
    np.random.seed(seed)

    Z_half = np.random.standard_normal((n_paths // 2, STEPS_3W))
    Z = np.vstack([Z_half, -Z_half])

    log_ret = -0.5 * SIGMA**2 * DT + SIGMA * np.sqrt(DT) * Z
    price_paths = S0 * np.cumprod(np.exp(log_ret), axis=1)

    return price_paths

def compute_payoffs(paths):
    """Compute payoff for each product at expiry."""
    S_2w = paths[:, STEPS_2W - 1]
    S_3w = paths[:, STEPS_3W - 1]
    path_min = np.min(paths, axis=1)

    payoffs = {}

    # Underlying (payoff = final price for long position)
    payoffs["AC"] = S_3w

    # 3-week vanilla options
    payoffs["AC_50_P"] = np.maximum(50 - S_3w, 0)
    payoffs["AC_50_C"] = np.maximum(S_3w - 50, 0)
    payoffs["AC_35_P"] = np.maximum(35 - S_3w, 0)
    payoffs["AC_40_P"] = np.maximum(40 - S_3w, 0)
    payoffs["AC_45_P"] = np.maximum(45 - S_3w, 0)
    payoffs["AC_60_C"] = np.maximum(S_3w - 60, 0)

    # 2-week vanilla options
    payoffs["AC_50_P_2"] = np.maximum(50 - S_2w, 0)
    payoffs["AC_50_C_2"] = np.maximum(S_2w - 50, 0)

    # Chooser: at 2w, pick call or put (whichever is ITM at that moment)
    # Then it becomes that option for the remaining week
    # At day 14, holder picks max(call_7d, put_7d)
    # For simplicity with r=0: chooser payoff = max(S_3w - 50, 0) if S_2w >= 50, else max(50 - S_3w, 0)
    chose_call = S_2w >= 50
    payoffs["AC_50_CO"] = np.where(chose_call,
                                    np.maximum(S_3w - 50, 0),  # call payoff
                                    np.maximum(50 - S_3w, 0))  # put payoff

    # Binary put: pays 10 if S_3w < 40
    payoffs["AC_40_BP"] = np.where(S_3w < 40, 10.0, 0.0)

    # Knock-out put: pays max(45 - S_3w, 0) if barrier never hit
    survived = path_min >= 35.0
    payoffs["AC_45_KO"] = np.where(survived, np.maximum(45 - S_3w, 0), 0.0)

    return payoffs

def compute_pnl(positions, payoffs):
    """Compute PnL for a strategy."""
    n_paths = len(payoffs["AC"])
    pnl = np.zeros(n_paths)

    for product, qty in positions.items():
        if qty == 0:
            continue

        payoff = payoffs[product]

        if product == "AC":
            # Special handling for underlying
            if qty > 0:  # LONG (buy at ask)
                pnl += qty * (payoff - MARKET[product]["ask"])
            else:  # SHORT (sell at bid)
                pnl += (-qty) * (MARKET[product]["bid"] - payoff)
        else:
            # Options
            if qty > 0:  # BUY (pay ask, receive payoff)
                pnl += qty * (payoff - MARKET[product]["ask"])
            else:  # SELL (receive bid, pay payoff)
                pnl += (-qty) * (MARKET[product]["bid"] - payoff)

    return pnl

def analyze_strategy(name, pnl):
    """Compute statistics for a PnL distribution."""
    return {
        "name": name,
        "mean": np.mean(pnl),
        "std": np.std(pnl),
        "sharpe": np.mean(pnl) / np.std(pnl) if np.std(pnl) > 0 else 0,
        "p_loss": np.mean(pnl < 0),
        "p05": np.percentile(pnl, 5),
        "p01": np.percentile(pnl, 1),
        "worst": np.min(pnl),
        "best": np.max(pnl),
        "median": np.median(pnl),
    }

# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    print("=" * 100)
    print("ROUND 4 MANUAL TRADING - STRATEGY COMPARISON")
    print("=" * 100)
    print(f"\nSimulating {100000:,} paths...")

    paths = simulate_paths(n_paths=100000, seed=42)
    payoffs = compute_payoffs(paths)

    print("\n" + "=" * 100)
    print("STRATEGY POSITIONS")
    print("=" * 100)

    for name, positions in STRATEGIES.items():
        print(f"\n{name}:")
        for prod, qty in sorted(positions.items()):
            action = "BUY" if qty > 0 else "SELL"
            print(f"  {prod:12} {action:4} {abs(qty):3}")

    print("\n" + "=" * 100)
    print("STRATEGY RESULTS")
    print("=" * 100)

    results = []
    for name, positions in STRATEGIES.items():
        pnl = compute_pnl(positions, payoffs)
        stats = analyze_strategy(name, pnl)
        results.append(stats)

    # Print comparison table
    print(f"\n{'Strategy':<22} {'Mean':>10} {'Std':>10} {'Sharpe':>8} {'P(loss)':>8} {'P05':>12} {'Worst':>12} {'Best':>12}")
    print("-" * 110)

    for r in sorted(results, key=lambda x: -x['mean']):
        print(f"{r['name']:<22} {r['mean']:>10.2f} {r['std']:>10.2f} {r['sharpe']:>8.4f} {r['p_loss']:>8.2%} {r['p05']:>12.2f} {r['worst']:>12.2f} {r['best']:>12.2f}")

    print("\n" + "=" * 100)
    print("KEY INSIGHTS")
    print("=" * 100)

    # Sort by mean
    by_mean = sorted(results, key=lambda x: -x['mean'])
    print(f"\nHighest Expected PnL: {by_mean[0]['name']} (E[PnL] = {by_mean[0]['mean']:.2f})")

    # Sort by Sharpe
    by_sharpe = sorted(results, key=lambda x: -x['sharpe'])
    print(f"Best Risk-Adjusted: {by_sharpe[0]['name']} (Sharpe = {by_sharpe[0]['sharpe']:.4f})")

    # Sort by P05 (less negative = better downside)
    by_p05 = sorted(results, key=lambda x: -x['p05'])
    print(f"Best Downside (P05): {by_p05[0]['name']} (P05 = {by_p05[0]['p05']:.2f})")

    # Sort by P(loss)
    by_ploss = sorted(results, key=lambda x: x['p_loss'])
    print(f"Lowest P(loss): {by_ploss[0]['name']} (P(loss) = {by_ploss[0]['p_loss']:.2%})")

    # Print detailed breakdown for each strategy
    print("\n" + "=" * 100)
    print("DETAILED PNL DISTRIBUTIONS")
    print("=" * 100)

    for name, positions in STRATEGIES.items():
        pnl = compute_pnl(positions, payoffs)
        print(f"\n{name}:")
        print(f"  Percentiles: 1%={np.percentile(pnl, 1):.2f}, 5%={np.percentile(pnl, 5):.2f}, "
              f"25%={np.percentile(pnl, 25):.2f}, 50%={np.percentile(pnl, 50):.2f}, "
              f"75%={np.percentile(pnl, 75):.2f}, 95%={np.percentile(pnl, 95):.2f}, 99%={np.percentile(pnl, 99):.2f}")
