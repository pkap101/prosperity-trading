"""
Round 4 Manual Trading Challenge - Exotic Options Analysis
"Vanilla Just Isn't Exotic Enough"

Underlying: AETHER_CRYSTAL at S=50
Volatility: 251% annualized
Drift: 0 (risk-neutral)
Time steps: 4 per trading day, 252 trading days/year
"""

import numpy as np
from scipy.stats import norm
from typing import Tuple

# Parameters
S0 = 50.0  # Current price
SIGMA = 2.51  # 251% annualized volatility
R = 0.0  # Risk-free rate (zero drift)
TRADING_DAYS_PER_YEAR = 252
STEPS_PER_DAY = 4
CONTRACT_SIZE = 3000

# Time periods
T_2WEEK = 14 / TRADING_DAYS_PER_YEAR  # 2 weeks in years
T_3WEEK = 21 / TRADING_DAYS_PER_YEAR  # 3 weeks in years
T_1WEEK = 7 / TRADING_DAYS_PER_YEAR   # 1 week in years


def black_scholes_call(S, K, T, sigma, r=0):
    """Black-Scholes call price."""
    if T <= 0:
        return max(0, S - K)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)


def black_scholes_put(S, K, T, sigma, r=0):
    """Black-Scholes put price."""
    if T <= 0:
        return max(0, K - S)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def binary_put_price(S, K, T, sigma, payout, r=0):
    """Binary/Digital put: pays fixed amount if S_T < K."""
    if T <= 0:
        return payout if S < K else 0
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    # Probability that S_T < K under risk-neutral measure
    prob_below = norm.cdf(-d2)
    return payout * np.exp(-r * T) * prob_below


def knock_out_put_price_mc(S, K, barrier, T, sigma, r=0, n_sims=100000, n_steps=None):
    """
    Knock-Out Put via Monte Carlo.
    Knocked out if price ever falls BELOW barrier.
    """
    if n_steps is None:
        n_steps = int(T * TRADING_DAYS_PER_YEAR * STEPS_PER_DAY)

    dt = T / n_steps
    sqrt_dt = np.sqrt(dt)

    # Simulate paths
    np.random.seed(42)
    Z = np.random.randn(n_sims, n_steps)

    log_S = np.log(S)
    drift = (r - 0.5 * sigma**2) * dt
    diffusion = sigma * sqrt_dt

    # Track minimum price for barrier
    paths = np.zeros((n_sims, n_steps + 1))
    paths[:, 0] = S

    log_paths = log_S + np.cumsum(drift + diffusion * Z, axis=1)
    paths[:, 1:] = np.exp(log_paths)

    # Check if barrier was breached (price went BELOW barrier)
    min_prices = np.min(paths, axis=1)
    knocked_out = min_prices < barrier

    # Final payoff (put payoff if not knocked out)
    final_prices = paths[:, -1]
    put_payoff = np.maximum(K - final_prices, 0)
    payoff = np.where(knocked_out, 0, put_payoff)

    return np.mean(payoff) * np.exp(-r * T)


def chooser_option_price_mc(S, K, T_choice, T_expiry, sigma, r=0, n_sims=100000):
    """
    Chooser Option via Monte Carlo.
    At T_choice, holder picks call or put (whichever is ITM).
    Option then expires at T_expiry.
    """
    n_steps_to_choice = int(T_choice * TRADING_DAYS_PER_YEAR * STEPS_PER_DAY)
    n_steps_to_expiry = int(T_expiry * TRADING_DAYS_PER_YEAR * STEPS_PER_DAY)

    dt = T_expiry / n_steps_to_expiry
    sqrt_dt = np.sqrt(dt)

    np.random.seed(42)
    Z = np.random.randn(n_sims, n_steps_to_expiry)

    log_S = np.log(S)
    drift = (r - 0.5 * sigma**2) * dt
    diffusion = sigma * sqrt_dt

    log_paths = log_S + np.cumsum(drift + diffusion * Z, axis=1)
    paths = np.exp(log_paths)

    # Price at choice time
    S_choice = paths[:, n_steps_to_choice - 1]
    # Price at expiry
    S_expiry = paths[:, -1]

    # At choice time, pick call if S > K, else put
    # (Actually: pick whichever is ITM, which is call if S > K, put if S < K)
    chose_call = S_choice >= K

    # Payoff depends on choice
    call_payoff = np.maximum(S_expiry - K, 0)
    put_payoff = np.maximum(K - S_expiry, 0)

    payoff = np.where(chose_call, call_payoff, put_payoff)

    return np.mean(payoff) * np.exp(-r * T_expiry)


def analyze_all_options():
    """Analyze all available options and compare to market prices."""

    print("=" * 80)
    print("ROUND 4 MANUAL OPTIONS ANALYSIS")
    print("=" * 80)
    print(f"\nUnderlying: S = {S0}")
    print(f"Volatility: σ = {SIGMA * 100}% annualized")
    print(f"Risk-free rate: r = {R}")
    print(f"2-week = {T_2WEEK:.4f} years, 3-week = {T_3WEEK:.4f} years")

    # Market data from the challenge
    options = [
        # (name, type, strike, expiry_years, bid, ask, extra_params)
        ("AC_50_P", "put", 50, T_3WEEK, 12.00, 12.05, {}),
        ("AC_50_C", "call", 50, T_3WEEK, 12.00, 12.05, {}),
        ("AC_35_P", "put", 35, T_3WEEK, 4.33, 4.35, {}),
        ("AC_40_P", "put", 40, T_3WEEK, 6.50, 6.55, {}),
        ("AC_45_P", "put", 45, T_3WEEK, 9.05, 9.10, {}),
        ("AC_60_C", "call", 60, T_3WEEK, 8.80, 8.85, {}),
        ("AC_50_P_2", "put", 50, T_2WEEK, 9.70, 9.75, {}),
        ("AC_50_C_2", "call", 50, T_2WEEK, 9.70, 9.75, {}),
        ("AC_50_CO", "chooser", 50, T_3WEEK, 22.20, 22.30, {"T_choice": T_2WEEK}),
        ("AC_40_BP", "binary_put", 40, T_3WEEK, 5.00, 5.10, {"payout": 10}),
        ("AC_45_KO", "ko_put", 45, T_3WEEK, 0.15, 0.175, {"barrier": 35}),
    ]

    print("\n" + "=" * 80)
    print("THEORETICAL vs MARKET PRICES")
    print("=" * 80)
    print(f"\n{'Option':<12} {'Type':<12} {'K':<6} {'Bid':<8} {'Ask':<8} {'Theo':<8} {'Edge':<8} {'Action':<8} {'Vol':<6}")
    print("-" * 85)

    results = []

    for name, opt_type, K, T, bid, ask, params in options:
        mid = (bid + ask) / 2

        if opt_type == "call":
            theo = black_scholes_call(S0, K, T, SIGMA, R)
        elif opt_type == "put":
            theo = black_scholes_put(S0, K, T, SIGMA, R)
        elif opt_type == "binary_put":
            theo = binary_put_price(S0, K, T, SIGMA, params["payout"], R)
        elif opt_type == "chooser":
            theo = chooser_option_price_mc(S0, K, params["T_choice"], T, SIGMA, R)
        elif opt_type == "ko_put":
            theo = knock_out_put_price_mc(S0, K, params["barrier"], T, SIGMA, R)
        else:
            theo = 0

        # Edge: positive means underpriced (buy), negative means overpriced (sell)
        buy_edge = theo - ask  # If we buy at ask
        sell_edge = bid - theo  # If we sell at bid

        if buy_edge > 0:
            action = "BUY"
            edge = buy_edge
        elif sell_edge > 0:
            action = "SELL"
            edge = sell_edge
        else:
            action = "HOLD"
            edge = 0

        vol = 50 if "KO" not in name else 500

        print(f"{name:<12} {opt_type:<12} {K:<6} {bid:<8.2f} {ask:<8.2f} {theo:<8.2f} {edge:+8.2f} {action:<8} {vol:<6}")

        results.append({
            "name": name,
            "type": opt_type,
            "K": K,
            "T": T,
            "bid": bid,
            "ask": ask,
            "theo": theo,
            "buy_edge": buy_edge,
            "sell_edge": sell_edge,
            "action": action,
            "edge": edge,
            "volume": vol,
        })

    # Calculate optimal portfolio
    print("\n" + "=" * 80)
    print("RECOMMENDED TRADES")
    print("=" * 80)

    total_edge = 0
    print(f"\n{'Option':<12} {'Action':<8} {'Volume':<8} {'Edge/unit':<10} {'Total Edge':<12}")
    print("-" * 55)

    for r in results:
        if r["action"] != "HOLD":
            vol = r["volume"]
            edge_total = r["edge"] * vol * CONTRACT_SIZE
            total_edge += edge_total
            print(f"{r['name']:<12} {r['action']:<8} {vol:<8} {r['edge']:+10.2f} {edge_total:+12.0f}")

    print("-" * 55)
    print(f"{'TOTAL EXPECTED EDGE':<30} {'':<18} {total_edge:+12.0f}")

    # Risk analysis
    print("\n" + "=" * 80)
    print("HEDGING CONSIDERATIONS")
    print("=" * 80)

    print("""
Key considerations:
1. High volatility (251%) means large price swings are likely
2. Unhedged positions can have high variance
3. Consider delta-hedging with the underlying
4. Put-call parity can help identify arbitrage
""")

    return results


def put_call_parity_check():
    """Check put-call parity for arbitrage opportunities."""
    print("\n" + "=" * 80)
    print("PUT-CALL PARITY CHECK")
    print("=" * 80)

    # P + S = C + K*exp(-rT) for r=0: P + S = C + K
    # So C - P = S - K

    print("\nFor ATM options (K=50, S=50): C - P should = 0")
    print()

    # 3-week ATM
    c3 = 12.025  # mid of 12.00-12.05
    p3 = 12.025
    print(f"3-week: C={c3}, P={p3}, C-P={c3-p3:.3f} (should be 0)")

    # 2-week ATM
    c2 = 9.725
    p2 = 9.725
    print(f"2-week: C={c2}, P={p2}, C-P={c2-p2:.3f} (should be 0)")

    print("\n✓ Put-call parity holds - no obvious arbitrage there")


def monte_carlo_validation(n_sims=100000):
    """Validate our pricing with Monte Carlo."""
    print("\n" + "=" * 80)
    print(f"MONTE CARLO VALIDATION ({n_sims:,} simulations)")
    print("=" * 80)

    T = T_3WEEK
    n_steps = int(T * TRADING_DAYS_PER_YEAR * STEPS_PER_DAY)
    dt = T / n_steps

    np.random.seed(42)
    Z = np.random.randn(n_sims, n_steps)

    log_S = np.log(S0)
    drift = (R - 0.5 * SIGMA**2) * dt
    diffusion = SIGMA * np.sqrt(dt)

    log_paths = log_S + np.cumsum(drift + diffusion * Z, axis=1)
    S_T = np.exp(log_paths[:, -1])

    # All paths for barrier checking
    paths = np.exp(np.column_stack([np.full(n_sims, log_S), log_paths]))

    print(f"\nSimulation stats:")
    print(f"  E[S_T] = {np.mean(S_T):.2f} (should be ~50)")
    print(f"  Std[S_T] = {np.std(S_T):.2f}")
    print(f"  Min = {np.min(S_T):.2f}, Max = {np.max(S_T):.2f}")

    # Vanilla options
    print(f"\n{'Option':<15} {'MC Price':<10} {'BS Price':<10} {'Diff':<10}")
    print("-" * 50)

    for K in [35, 40, 45, 50, 60]:
        # Put
        put_payoff = np.maximum(K - S_T, 0)
        mc_put = np.mean(put_payoff)
        bs_put = black_scholes_put(S0, K, T, SIGMA, R)
        print(f"Put K={K:<6} {mc_put:<10.3f} {bs_put:<10.3f} {mc_put-bs_put:<+10.3f}")

        # Call
        call_payoff = np.maximum(S_T - K, 0)
        mc_call = np.mean(call_payoff)
        bs_call = black_scholes_call(S0, K, T, SIGMA, R)
        print(f"Call K={K:<5} {mc_call:<10.3f} {bs_call:<10.3f} {mc_call-bs_call:<+10.3f}")

    # Binary put
    K = 40
    payout = 10
    binary_payoff = np.where(S_T < K, payout, 0)
    mc_binary = np.mean(binary_payoff)
    bs_binary = binary_put_price(S0, K, T, SIGMA, payout, R)
    print(f"\nBinary Put K=40, payout=10:")
    print(f"  MC: {mc_binary:.3f}, Closed-form: {bs_binary:.3f}")

    # Knock-out put
    K = 45
    barrier = 35
    min_prices = np.min(paths, axis=1)
    knocked_out = min_prices < barrier
    ko_payoff = np.where(knocked_out, 0, np.maximum(K - S_T, 0))
    mc_ko = np.mean(ko_payoff)
    print(f"\nKnock-out Put K=45, barrier=35:")
    print(f"  MC: {mc_ko:.3f}")
    print(f"  Knock-out rate: {np.mean(knocked_out)*100:.1f}%")


if __name__ == "__main__":
    results = analyze_all_options()
    put_call_parity_check()
    monte_carlo_validation()
