import numpy as np
import pandas as pd
from itertools import product
from math import erf, exp, log, sqrt
from pathlib import Path
import json
import os
import time

os.environ.setdefault("MPLCONFIGDIR", str((Path.cwd() / ".mplcache").resolve()))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# -----------------------------
# Market setup
# -----------------------------

S0 = 50.0
SIGMA = 2.51
DRIFT = 0.0
TRADING_DAYS_PER_YEAR = 252
STEPS_PER_DAY = 4
STEPS_PER_YEAR = TRADING_DAYS_PER_YEAR * STEPS_PER_DAY


def weeks_to_years(weeks: float) -> float:
    return (weeks * 5.0) / TRADING_DAYS_PER_YEAR


def steps_for_weeks(weeks: float) -> int:
    return int(round(weeks * 5.0 * STEPS_PER_DAY))


DAYS_2W = 10
DAYS_3W = 15
CHOOSER_DAY = 10

N_STEPS_2W = steps_for_weeks(2)
N_STEPS_3W = steps_for_weeks(3)
CHOOSER_STEP = steps_for_weeks(2)

DT = 1.0 / STEPS_PER_YEAR

SCRIPT_DIR = Path(__file__).resolve().parent
OUT_DIR = SCRIPT_DIR / "bruteforce_output"


# -----------------------------
# Products from the screen
# Positive position = buy
# Negative position = sell
# -----------------------------

MARKET = {
    "AC":        {"bid": 49.975, "ask": 50.025, "max_vol": 200, "type": "underlying"},

    "AC_50_P":  {"bid": 12.00,  "ask": 12.05,  "max_vol": 50,  "type": "put",  "strike": 50, "days": DAYS_3W},
    "AC_50_C":  {"bid": 12.00,  "ask": 12.05,  "max_vol": 50,  "type": "call", "strike": 50, "days": DAYS_3W},
    "AC_35_P":  {"bid": 4.33,   "ask": 4.35,   "max_vol": 50,  "type": "put",  "strike": 35, "days": DAYS_3W},
    "AC_40_P":  {"bid": 6.50,   "ask": 6.55,   "max_vol": 50,  "type": "put",  "strike": 40, "days": DAYS_3W},
    "AC_45_P":  {"bid": 9.05,   "ask": 9.10,   "max_vol": 50,  "type": "put",  "strike": 45, "days": DAYS_3W},
    "AC_60_C":  {"bid": 8.80,   "ask": 8.85,   "max_vol": 50,  "type": "call", "strike": 60, "days": DAYS_3W},

    "AC_50_P_2": {"bid": 9.70,  "ask": 9.75,   "max_vol": 50,  "type": "put",  "strike": 50, "days": DAYS_2W},
    "AC_50_C_2": {"bid": 9.70,  "ask": 9.75,   "max_vol": 50,  "type": "call", "strike": 50, "days": DAYS_2W},

    "AC_50_CO": {"bid": 22.20, "ask": 22.30,  "max_vol": 50,  "type": "chooser", "strike": 50},

    "AC_40_BP": {"bid": 5.00,  "ask": 5.10,   "max_vol": 50,  "type": "binary_put", "strike": 40, "payout": 10},

    "AC_45_KO": {"bid": 0.15,  "ask": 0.175,  "max_vol": 500, "type": "ko_put", "strike": 45, "barrier": 35},
}


FULL_COARSE_GRID = {
    "AC": [-200, -150, -100, -50, 0, 50, 100, 150, 200],
    "AC_45_KO": [-500, -375, -250, -125, 0],
    "AC_40_BP": [-50, -25, 0, 25],
    "AC_50_CO": [-50, -25, 0, 25],
    "AC_50_C_2": [0, 25, 50],
    "AC_50_P_2": [0, 25, 50],
    "AC_35_P": [-50, 0, 50],
    "AC_40_P": [-50, 0, 50],
    "AC_45_P": [-50, 0, 50],
    "AC_50_P": [-50, 0, 50],
    "AC_50_C": [-50, 0, 50],
    "AC_60_C": [-50, 0, 50],
}

ALL_PRODUCTS = list(FULL_COARSE_GRID.keys())
PRODUCT_INDEX = {product_name: i for i, product_name in enumerate(ALL_PRODUCTS)}

CORE_PRODUCTS = [
    "AC",
    "AC_45_KO",
    "AC_40_BP",
    "AC_50_CO",
    "AC_50_C_2",
    "AC_50_P_2",
]

HEDGE_PRODUCTS = [
    "AC_35_P",
    "AC_40_P",
    "AC_45_P",
    "AC_50_P",
    "AC_50_C",
    "AC_60_C",
]

REFINE_STEPS = {
    "AC": 25,
    "AC_45_KO": 25,
    "AC_40_BP": 5,
    "AC_50_CO": 5,
    "AC_50_C_2": 5,
    "AC_50_P_2": 5,
    "AC_35_P": 5,
    "AC_40_P": 5,
    "AC_45_P": 5,
    "AC_50_P": 5,
    "AC_50_C": 5,
    "AC_60_C": 5,
}

MAX_VOL = {
    "AC": 200,
    "AC_45_KO": 500,
    "AC_40_BP": 50,
    "AC_50_CO": 50,
    "AC_50_C_2": 50,
    "AC_50_P_2": 50,
    "AC_35_P": 50,
    "AC_40_P": 50,
    "AC_45_P": 50,
    "AC_50_P": 50,
    "AC_50_C": 50,
    "AC_60_C": 50,
}

STEP = {
    "AC": 5,
    "AC_45_KO": 10,
    "AC_40_BP": 1,
    "AC_50_CO": 1,
    "AC_50_C_2": 1,
    "AC_50_P_2": 1,
    "AC_35_P": 1,
    "AC_40_P": 1,
    "AC_45_P": 1,
    "AC_50_P": 1,
    "AC_50_C": 1,
    "AC_60_C": 1,
}

PRIOR_CENTER = {
    "AC": -150,
    "AC_45_KO": -400,
    "AC_40_BP": -40,
    "AC_50_CO": 10,
    "AC_50_C_2": 35,
    "AC_50_P_2": 0,
    "AC_35_P": 35,
    "AC_40_P": 0,
    "AC_45_P": 0,
    "AC_50_P": 0,
    "AC_50_C": 35,
    "AC_60_C": 35,
}

BEST_LOCAL_MUTATION_RANGES = {
    "AC": (-30, 30, 5),
    "AC_45_KO": (-80, 80, 10),
    "AC_40_BP": (-14, 14, 2),
    "AC_50_CO": (-15, 15, 2),
    "AC_50_C_2": (-15, 15, 2),
    "AC_50_P_2": (-15, 15, 2),
    "AC_35_P": (-15, 15, 1),
    "AC_50_C": (-15, 15, 1),
    "AC_60_C": (-15, 15, 1),
}

ROUND2_REFINE_GRID = {
    "AC": list(range(-85, -20 + 1, 5)),
    "AC_45_KO": list(range(-360, -220 + 1, 10)),
    "AC_40_BP": list(range(-50, -20 + 1, 2)),
    "AC_50_CO": list(range(-30, 5 + 1, 2)),
    "AC_50_C_2": list(range(20, 50 + 1, 2)),
    "AC_50_P_2": list(range(10, 40 + 1, 2)),
    "AC_35_P": list(range(35, 50 + 1, 1)),
    "AC_40_P": [0],
    "AC_45_P": [0],
    "AC_50_P": [0],
    "AC_50_C": list(range(30, 50 + 1, 1)),
    "AC_60_C": list(range(20, 50 + 1, 1)),
}


# -----------------------------
# Black-Scholes utilities
# -----------------------------

def norm_cdf(x):
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def bs_call(S, K, T, sigma, r=0.0):
    if T <= 0:
        return max(S - K, 0.0)
    if sigma <= 0:
        return max(S - K * exp(-r * T), 0.0)

    d1 = (log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)
    return S * norm_cdf(d1) - K * exp(-r * T) * norm_cdf(d2)


def bs_put(S, K, T, sigma, r=0.0):
    if T <= 0:
        return max(K - S, 0.0)
    if sigma <= 0:
        return max(K * exp(-r * T) - S, 0.0)

    d1 = (log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)
    return K * exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)


# -----------------------------
# Simulate GBM paths
# -----------------------------

def simulate_paths(n_paths=200_000, seed=1, antithetic=True):
    rng = np.random.default_rng(seed)

    if antithetic:
        half = (n_paths + 1) // 2
        z_half = rng.standard_normal((half, N_STEPS_3W))
        z = np.vstack([z_half, -z_half])[:n_paths]
    else:
        z = rng.standard_normal((n_paths, N_STEPS_3W))

    log_returns = (
        (DRIFT - 0.5 * SIGMA ** 2) * DT
        + SIGMA * np.sqrt(DT) * z
    )

    log_paths = np.cumsum(log_returns, axis=1)
    paths = S0 * np.exp(log_paths)

    # Add S0 as time 0 column
    paths = np.concatenate([np.full((n_paths, 1), S0), paths], axis=1)

    return paths


# -----------------------------
# Payoff functions
# -----------------------------

def payoff_product(product, paths):
    info = MARKET[product]
    typ = info["type"]

    S_2w = paths[:, N_STEPS_2W]
    S_3w = paths[:, N_STEPS_3W]
    S_choice = paths[:, CHOOSER_STEP]

    if typ == "underlying":
        return S_3w

    if typ == "call":
        K = info["strike"]
        days = info["days"]
        S_T = S_2w if days == 14 else S_3w
        return np.maximum(S_T - K, 0.0)

    if typ == "put":
        K = info["strike"]
        days = info["days"]
        S_T = S_2w if days == 14 else S_3w
        return np.maximum(K - S_T, 0.0)

    if typ == "binary_put":
        K = info["strike"]
        payout = info["payout"]
        return np.where(S_3w < K, payout, 0.0)

    if typ == "ko_put":
        K = info["strike"]
        barrier = info["barrier"]

        # Knocked out if underlying ever falls below barrier before expiry
        touched_barrier = np.min(paths[:, :N_STEPS_3W + 1], axis=1) < barrier

        vanilla_put_payoff = np.maximum(K - S_3w, 0.0)
        return np.where(touched_barrier, 0.0, vanilla_put_payoff)

    if typ == "chooser":
        K = info["strike"]

        # At day 14, chooser becomes whichever is ITM at that time.
        # If S_choice >= K, choose call. Else choose put.
        choose_call = S_choice >= K

        call_payoff = np.maximum(S_3w - K, 0.0)
        put_payoff = np.maximum(K - S_3w, 0.0)

        return np.where(choose_call, call_payoff, put_payoff)

    raise ValueError(f"Unknown product type: {typ}")


# -----------------------------
# Fair values and buy/sell EV
# -----------------------------

def bs_fair_value(product):
    info = MARKET[product]
    typ = info["type"]

    if typ not in ("call", "put"):
        return None

    K = info["strike"]
    T = info["days"] / TRADING_DAYS_PER_YEAR

    if typ == "call":
        return bs_call(S0, K, T, SIGMA)
    return bs_put(S0, K, T, SIGMA)


def analyze_products(paths):
    rows = []

    for product, info in MARKET.items():
        payoff = payoff_product(product, paths)
        fair = payoff.mean()

        bid = info["bid"]
        ask = info["ask"]

        buy_ev = fair - ask
        sell_ev = bid - fair

        rows.append({
            "product": product,
            "type": info["type"],
            "bid": bid,
            "ask": ask,
            "fair": fair,
            "buy_ev_per_unit": buy_ev,
            "sell_ev_per_unit": sell_ev,
            "best_side": "BUY" if buy_ev > sell_ev else "SELL",
            "best_ev_per_unit": max(buy_ev, sell_ev),
            "max_vol": info["max_vol"],
            "max_expected_pnl": max(buy_ev, sell_ev) * info["max_vol"],
        })

    return pd.DataFrame(rows).sort_values("max_expected_pnl", ascending=False)


def analyze_with_black_scholes_and_mc(paths):
    rows = []

    for product, info in MARKET.items():
        mc_payoff = payoff_product(product, paths)
        mc_fair = float(mc_payoff.mean())
        bs_fair = bs_fair_value(product)

        used_fair = bs_fair if bs_fair is not None else mc_fair
        bid = info["bid"]
        ask = info["ask"]
        buy_ev = used_fair - ask
        sell_ev = bid - used_fair

        rows.append({
            "product": product,
            "type": info["type"],
            "bid": bid,
            "ask": ask,
            "bs_fair": bs_fair,
            "mc_fair": mc_fair,
            "mc_minus_bs": None if bs_fair is None else mc_fair - bs_fair,
            "used_fair": used_fair,
            "buy_ev": buy_ev,
            "sell_ev": sell_ev,
            "best_side": "BUY" if buy_ev > sell_ev else "SELL",
            "best_ev": max(buy_ev, sell_ev),
            "max_vol": info["max_vol"],
            "max_expected_pnl": max(buy_ev, sell_ev) * info["max_vol"],
        })

    return pd.DataFrame(rows).sort_values("max_expected_pnl", ascending=False)


# -----------------------------
# Portfolio PnL simulation
# -----------------------------

def portfolio_pnl(paths, positions):
    """
    positions:
        positive = buy volume
        negative = sell volume
    """
    total = np.zeros(paths.shape[0])

    for product, qty in positions.items():
        if qty == 0:
            continue

        info = MARKET[product]
        payoff = payoff_product(product, paths)

        if qty > 0:
            # Buy at ask
            total += qty * (payoff - info["ask"])
        else:
            # Sell at bid
            total += (-qty) * (info["bid"] - payoff)

    return total


def summarize_pnl(pnl):
    return {
        "mean": np.mean(pnl),
        "std": np.std(pnl),
        "min": np.min(pnl),
        "p01": np.percentile(pnl, 1),
        "p05": np.percentile(pnl, 5),
        "p50": np.percentile(pnl, 50),
        "p95": np.percentile(pnl, 95),
        "p99": np.percentile(pnl, 99),
    }


def official_score_distribution(pnl, n_batches=20_000, batch_size=100, seed=123):
    rng = np.random.default_rng(seed)
    n = len(pnl)
    idx = rng.integers(0, n, size=(n_batches, batch_size))
    return np.mean(pnl[idx], axis=1)


def official_score_stats(pnl, n_batches=20_000, batch_size=100, seed=123):
    scores = official_score_distribution(
        pnl,
        n_batches=n_batches,
        batch_size=batch_size,
        seed=seed,
    )
    return {
        "official_mean": float(np.mean(scores)),
        "official_std": float(np.std(scores)),
        "official_p05": float(np.percentile(scores, 5)),
        "official_p01": float(np.percentile(scores, 1)),
        "official_prob_loss": float(np.mean(scores < 0)),
        "official_score": float(np.mean(scores) + 0.25 * np.percentile(scores, 5)),
    }


def exotic_diagnostics(paths):
    S_3w = paths[:, N_STEPS_3W]
    S_choice = paths[:, CHOOSER_STEP]
    min_path = np.min(paths[:, :N_STEPS_3W + 1], axis=1)

    return {
        "prob_final_below_40": np.mean(S_3w < 40),
        "prob_final_below_45": np.mean(S_3w < 45),
        "prob_ko_barrier_hit": np.mean(min_path < 35),
        "prob_ko_pays": np.mean((S_3w < 45) & (min_path >= 35)),
        "prob_chooser_call": np.mean(S_choice >= 50),
        "prob_chooser_put": np.mean(S_choice < 50),
    }


def scenario_breakdown(paths, pnl):
    S_T = paths[:, N_STEPS_3W]
    S_14 = paths[:, CHOOSER_STEP]
    min_path = np.min(paths[:, :N_STEPS_3W + 1], axis=1)

    scenarios = {
        "final_below_35": S_T < 35,
        "final_35_40": (S_T >= 35) & (S_T < 40),
        "final_40_45": (S_T >= 40) & (S_T < 45),
        "final_45_50": (S_T >= 45) & (S_T < 50),
        "final_50_60": (S_T >= 50) & (S_T < 60),
        "final_above_60": S_T >= 60,
        "ko_barrier_hit": min_path < 35,
        "chooser_call": S_14 >= 50,
        "chooser_put": S_14 < 50,
    }

    rows = []
    for name, mask in scenarios.items():
        if not np.any(mask):
            continue
        rows.append(
            {
                "scenario": name,
                "prob": float(np.mean(mask)),
                "mean_pnl": float(np.mean(pnl[mask])),
                "p05_pnl": float(np.percentile(pnl[mask], 5)),
                "p01_pnl": float(np.percentile(pnl[mask], 1)),
                "count": int(np.sum(mask)),
            }
        )

    return pd.DataFrame(rows).sort_values("mean_pnl")


def validate_positions(positions):
    for product, qty in positions.items():
        if product not in MARKET:
            raise KeyError(f"Unknown product: {product}")
        if abs(qty) > MARKET[product]["max_vol"]:
            raise ValueError(
                f"{product}: qty {qty} exceeds max_vol {MARKET[product]['max_vol']}"
            )


def evaluate_pnl_vector(pnl, name=None):
    score_std_100 = float(np.std(pnl) / np.sqrt(100))
    summary = {
        "mean": float(np.mean(pnl)),
        "median": float(np.median(pnl)),
        "std": float(np.std(pnl)),
        "score_std_100": score_std_100,
        "score_std_100_sims": score_std_100,
        "mean_ci95_100_sims": float(2.0 * score_std_100),
        "p_loss": float(np.mean(pnl < 0)),
        "p05": float(np.percentile(pnl, 5)),
        "p01": float(np.percentile(pnl, 1)),
        "worst": float(np.min(pnl)),
        "best": float(np.max(pnl)),
    }
    summary["score_p05_10"] = summary["mean"] + 0.10 * summary["p05"]
    summary["score_p05_25"] = summary["mean"] + 0.25 * summary["p05"]
    if name is not None:
        summary["name"] = name
    return summary


def evaluate_pnl_matrix(pnl_matrix):
    means = np.mean(pnl_matrix, axis=1)
    medians = np.median(pnl_matrix, axis=1)
    stds = np.std(pnl_matrix, axis=1)
    score_std_100 = stds / np.sqrt(100)
    p_loss = np.mean(pnl_matrix < 0, axis=1)
    p05 = np.percentile(pnl_matrix, 5, axis=1)
    p01 = np.percentile(pnl_matrix, 1, axis=1)
    worst = np.min(pnl_matrix, axis=1)
    best = np.max(pnl_matrix, axis=1)

    rows = []
    for i in range(pnl_matrix.shape[0]):
        stats = {
            "mean": float(means[i]),
            "median": float(medians[i]),
            "std": float(stds[i]),
            "score_std_100": float(score_std_100[i]),
            "score_std_100_sims": float(score_std_100[i]),
            "mean_ci95_100_sims": float(2.0 * score_std_100[i]),
            "p_loss": float(p_loss[i]),
            "p05": float(p05[i]),
            "p01": float(p01[i]),
            "worst": float(worst[i]),
            "best": float(best[i]),
        }
        stats["score_p05_10"] = stats["mean"] + 0.10 * stats["p05"]
        stats["score_p05_25"] = stats["mean"] + 0.25 * stats["p05"]
        stats["score"] = score_stats(stats)
        stats.update(calculate_scores(stats))
        rows.append(stats)
    return rows


def evaluate_strategy(name, paths, positions):
    validate_positions(positions)
    pnl = portfolio_pnl(paths, positions)
    row = evaluate_pnl_vector(pnl, name=name)
    row["positions"] = ", ".join(
        f"{product}:{qty}" for product, qty in positions.items() if qty != 0
    )
    return row


def build_strategy_table(paths, strategies):
    rows = [evaluate_strategy(name, paths, positions) for name, positions in strategies.items()]
    return pd.DataFrame(rows).sort_values(
        ["score_p05_25", "mean"], ascending=False
    )


def build_volume_pnl_cache(paths, product_grids):
    n_paths = paths.shape[0]
    zero = np.zeros(n_paths)
    cache = {}

    for product_name, grid in product_grids.items():
        payoff = payoff_product(product_name, paths)
        info = MARKET[product_name]
        long_unit = payoff - info["ask"]
        short_unit = info["bid"] - payoff

        cache[product_name] = {0: zero}
        for qty in sorted(set(grid)):
            if qty == 0:
                continue
            if qty > 0:
                cache[product_name][qty] = qty * long_unit
            else:
                cache[product_name][qty] = (-qty) * short_unit

    return cache


def brute_force_search(paths, product_grids, base_positions=None, top_n=10):
    base_positions = base_positions or {}
    validate_positions(base_positions)

    for product_name, grid in product_grids.items():
        for qty in grid:
            if abs(qty) > MARKET[product_name]["max_vol"]:
                raise ValueError(
                    f"{product_name}: grid qty {qty} exceeds max_vol {MARKET[product_name]['max_vol']}"
                )

    products = list(product_grids.keys())
    cache = build_volume_pnl_cache(paths, product_grids)
    base_pnl = portfolio_pnl(paths, base_positions) if base_positions else np.zeros(paths.shape[0])

    rows = []
    for combo in product(*[product_grids[p] for p in products]):
        positions = dict(base_positions)
        total = base_pnl.copy()

        for product_name, qty in zip(products, combo):
            if qty != 0:
                positions[product_name] = positions.get(product_name, 0) + qty
                total += cache[product_name][qty]

        validate_positions(positions)
        row = evaluate_pnl_vector(total)
        row["positions"] = ", ".join(
            f"{product_name}:{qty}" for product_name, qty in positions.items() if qty != 0
        )
        for product_name in products:
            row[product_name] = positions.get(product_name, 0)
        rows.append(row)

    return pd.DataFrame(rows).sort_values(
        ["score_p05_25", "mean"], ascending=False
    ).head(top_n)


def make_output_paths(run_name):
    run_dir = OUT_DIR / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    return {
        "dir": run_dir,
        "results_csv": run_dir / "bruteforce_results.csv",
        "top_csv": run_dir / "top_portfolios.csv",
        "best_json": run_dir / "best_portfolio.json",
        "checkpoint_json": run_dir / "checkpoint.json",
        "progress_png": run_dir / "progress.png",
        "progress_csv": run_dir / "progress.csv",
        "best_dist_png": run_dir / "best_pnl_distribution.png",
        "official_dist_png": run_dir / "official_score_distribution.png",
        "scenario_csv": run_dir / "best_scenario_breakdown.csv",
        "summary_txt": run_dir / "summary.txt",
        "reeval_csv": run_dir / "finalist_reevaluation.csv",
    }


def append_result(row, results_csv):
    df = pd.DataFrame([row])
    write_header = not results_csv.exists()
    df.to_csv(results_csv, mode="a", header=write_header, index=False)


def append_results(rows, results_csv):
    if not rows:
        return
    df = pd.DataFrame(rows)
    write_header = not results_csv.exists()
    df.to_csv(results_csv, mode="a", header=write_header, index=False)


def append_progress_row(row, progress_csv):
    df = pd.DataFrame([row])
    write_header = not progress_csv.exists()
    df.to_csv(progress_csv, mode="a", header=write_header, index=False)


def save_progress_plot(progress_csv, progress_png):
    if not progress_csv.exists():
        return

    df = pd.read_csv(progress_csv)
    if df.empty:
        return

    plt.figure(figsize=(10, 5))
    plt.plot(df["run_id"], df["best_score"])
    plt.xlabel("Run ID")
    plt.ylabel("Best score so far")
    plt.title("Brute-force optimization progress")
    plt.tight_layout()
    plt.savefig(progress_png, dpi=150)
    plt.close()


def save_best_distribution(paths, best_positions, best_dist_png):
    pnl = portfolio_pnl(paths, best_positions)

    plt.figure(figsize=(10, 5))
    plt.hist(pnl, bins=80)
    plt.xlabel("PnL")
    plt.ylabel("Frequency")
    plt.title("Best portfolio PnL distribution")
    plt.tight_layout()
    plt.savefig(best_dist_png, dpi=150)
    plt.close()


def plot_official_score_distribution(pnl, out_path, n_batches=20_000, batch_size=100, seed=123):
    scores = official_score_distribution(
        pnl,
        n_batches=n_batches,
        batch_size=batch_size,
        seed=seed,
    )

    plt.figure(figsize=(10, 5))
    plt.hist(scores, bins=80)
    plt.axvline(np.mean(scores), linestyle="--", label=f"mean={np.mean(scores):.2f}")
    plt.axvline(np.percentile(scores, 5), linestyle="--", label=f"p05={np.percentile(scores, 5):.2f}")
    plt.axvline(0.0, linestyle="--", label="zero")
    plt.title("Official-style 100-simulation average score distribution")
    plt.xlabel("Average PnL over 100 simulations")
    plt.ylabel("Frequency")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()

    return {
        "official_mean": float(np.mean(scores)),
        "official_p05": float(np.percentile(scores, 5)),
        "official_p01": float(np.percentile(scores, 1)),
        "official_prob_loss": float(np.mean(scores < 0)),
    }


def save_best_risk_reports(
    paths,
    best_positions,
    output_paths,
    official_batches=20_000,
    official_batch_size=100,
    official_seed=123,
):
    save_best_distribution(paths, best_positions, output_paths["best_dist_png"])
    pnl = portfolio_pnl(paths, best_positions)
    plot_official_score_distribution(
        pnl,
        output_paths["official_dist_png"],
        n_batches=official_batches,
        batch_size=official_batch_size,
        seed=official_seed,
    )
    scenario_df = scenario_breakdown(paths, pnl)
    scenario_df.to_csv(output_paths["scenario_csv"], index=False)


def save_top_results(top_rows, top_csv, top_n=50):
    if not top_rows:
        return
    top = sorted(top_rows, key=lambda x: x["score"], reverse=True)[:top_n]
    pd.DataFrame(top).to_csv(top_csv, index=False)


def save_best_json(best_row, best_positions, best_json):
    payload = dict(best_row)
    payload["positions"] = best_positions
    with open(best_json, "w") as f:
        json.dump(payload, f, indent=2)


def save_checkpoint(checkpoint_json, run_id, best_row):
    best_score = None
    best_mean = None
    if best_row is not None:
        best_score = best_row.get("score", best_row.get("final_score"))
        best_mean = best_row.get("mean", best_row.get("avg_official_mean"))

    payload = {
        "last_run_id": run_id,
        "best_score": best_score,
        "best_mean": best_mean,
        "updated_at": time.time(),
    }
    with open(checkpoint_json, "w") as f:
        json.dump(payload, f, indent=2)


def load_resume_state(output_paths, resume=True):
    if not resume:
        for key, path in output_paths.items():
            if key == "dir":
                continue
            if path.exists():
                path.unlink()
        return 0, [], None, None

    last_run_id = 0
    top_rows = []
    best_row = None
    best_positions = None

    if output_paths["checkpoint_json"].exists():
        with open(output_paths["checkpoint_json"]) as f:
            checkpoint = json.load(f)
        last_run_id = int(checkpoint.get("last_run_id", 0))

    if output_paths["top_csv"].exists():
        top_rows = pd.read_csv(output_paths["top_csv"]).to_dict("records")

    if output_paths["best_json"].exists():
        with open(output_paths["best_json"]) as f:
            best_payload = json.load(f)
        best_positions = best_payload.pop("positions", {})
        best_row = best_payload

    return last_run_id, top_rows, best_row, best_positions


def generate_portfolios(product_grids):
    products = list(product_grids.keys())
    grids = [product_grids[p] for p in products]

    for values in product(*grids):
        positions = dict(zip(products, values))
        yield {p: q for p, q in positions.items() if q != 0}


def build_grid_pnl_cache(paths, product_grids):
    n_paths = paths.shape[0]
    zero = np.zeros(n_paths)
    cache = {}

    for product_name, grid in product_grids.items():
        payoff = payoff_product(product_name, paths)
        info = MARKET[product_name]
        long_unit = payoff - info["ask"]
        short_unit = info["bid"] - payoff

        cache[product_name] = {0: zero}
        for qty in sorted(set(grid)):
            if qty == 0:
                continue
            cache[product_name][qty] = qty * long_unit if qty > 0 else (-qty) * short_unit

    return cache


def build_unit_pnl_cache(paths, products):
    cache = {}
    for product_name in products:
        payoff = payoff_product(product_name, paths)
        info = MARKET[product_name]
        cache[product_name] = {
            "long_unit": payoff - info["ask"],
            "short_unit": info["bid"] - payoff,
        }
    return cache


def build_unit_pnl_matrices(paths, products):
    long_units = []
    short_units = []
    for product_name in products:
        payoff = payoff_product(product_name, paths)
        info = MARKET[product_name]
        long_units.append(payoff - info["ask"])
        short_units.append(info["bid"] - payoff)
    return np.vstack(long_units), np.vstack(short_units)


def score_stats(stats):
    return (
        stats["mean"]
        + 0.15 * stats["p05"]
        - 0.50 * stats["score_std_100_sims"]
    )


def calculate_scores(stats):
    mean = stats["mean"]
    p05 = stats["p05"]
    std100 = stats["score_std_100_sims"]

    return {
        "score_aggressive": mean + 0.05 * p05 - 0.25 * std100,
        "score_balanced": mean + 0.15 * p05 - 0.50 * std100,
        "score_safe": mean + 0.25 * p05 - 1.00 * std100,
        "score_mean_only": mean,
    }


def nonzero_count(positions, products):
    return sum(1 for p in products if positions.get(p, 0) != 0)


def valid_portfolio_broad(pos):
    if (
        pos.get("AC_45_KO", 0) == 0
        and pos.get("AC_40_BP", 0) == 0
        and pos.get("AC_50_CO", 0) == 0
    ):
        return False

    if nonzero_count(pos, HEDGE_PRODUCTS) > 2:
        return False

    if pos.get("AC_45_KO", 0) > 0:
        return False

    if pos.get("AC_50_CO", 0) > 25:
        return False

    if pos.get("AC_40_BP", 0) > 25:
        return False

    gross_options = sum(abs(q) for p, q in pos.items() if p != "AC")
    if gross_options == 0 and pos.get("AC", 0) != 0:
        return False

    return True


def valid_portfolio_coverage(pos):
    if (
        pos.get("AC_45_KO", 0) == 0
        and pos.get("AC_40_BP", 0) == 0
        and pos.get("AC_50_CO", 0) == 0
    ):
        return False

    # Broader than the initial broad search: allow up to four hedge legs so
    # all vanilla products have a realistic chance to appear.
    if nonzero_count(pos, HEDGE_PRODUCTS) > 4:
        return False

    if pos.get("AC_45_KO", 0) > 0:
        return False

    if pos.get("AC_50_CO", 0) > 25:
        return False

    if pos.get("AC_40_BP", 0) > 25:
        return False

    gross_options = sum(abs(q) for p, q in pos.items() if p != "AC")
    if gross_options == 0 and pos.get("AC", 0) != 0:
        return False

    # Keep the first-pass coverage search finite: avoid portfolios with too
    # many active lines all at once.
    if nonzero_count(pos, ALL_PRODUCTS) > 8:
        return False

    return True


def valid_portfolio_random(pos):
    if (
        pos.get("AC_45_KO", 0) == 0
        and pos.get("AC_40_BP", 0) == 0
        and pos.get("AC_50_CO", 0) == 0
    ):
        return False

    hedge_products = [
        "AC_35_P",
        "AC_40_P",
        "AC_45_P",
        "AC_50_P",
        "AC_50_C",
        "AC_60_C",
        "AC_50_C_2",
        "AC_50_P_2",
    ]
    if sum(pos.get(p, 0) != 0 for p in hedge_products) > 5:
        return False

    if pos.get("AC_45_KO", 0) > 0:
        return False

    if pos.get("AC_50_CO", 0) > 25:
        return False

    if pos.get("AC_40_BP", 0) > 25:
        return False

    gross_options = sum(abs(q) for p, q in pos.items() if p != "AC")
    if gross_options == 0 and pos.get("AC", 0) != 0:
        return False

    return True


def generate_full_coarse_portfolios():
    core_grids = [FULL_COARSE_GRID[p] for p in CORE_PRODUCTS]
    hedge_grids = [FULL_COARSE_GRID[p] for p in HEDGE_PRODUCTS]

    for core_values in product(*core_grids):
        core_pos = dict(zip(CORE_PRODUCTS, core_values))

        for hedge_values in product(*hedge_grids):
            pos = dict(core_pos)
            pos.update(dict(zip(HEDGE_PRODUCTS, hedge_values)))
            pos = {p: int(q) for p, q in pos.items() if q != 0}

            if valid_portfolio_broad(pos):
                yield pos


def generate_full_coverage_portfolios():
    core_grids = [FULL_COARSE_GRID[p] for p in CORE_PRODUCTS]
    hedge_grids = [FULL_COARSE_GRID[p] for p in HEDGE_PRODUCTS]

    for core_values in product(*core_grids):
        core_pos = dict(zip(CORE_PRODUCTS, core_values))

        for hedge_values in product(*hedge_grids):
            pos = dict(core_pos)
            pos.update(dict(zip(HEDGE_PRODUCTS, hedge_values)))
            pos = {p: int(q) for p, q in pos.items() if q != 0}

            if valid_portfolio_coverage(pos):
                yield pos


def count_portfolios(portfolio_generator):
    return sum(1 for _ in portfolio_generator())


def expand_positions(positions):
    full = {product_name: 0 for product_name in ALL_PRODUCTS}
    full.update(positions)
    return full


def quantize(x, step, lo, hi):
    x = int(round(x / step) * step)
    return max(lo, min(hi, x))


def sample_volume(product_name, rng):
    max_vol = MAX_VOL[product_name]
    step = STEP[product_name]

    if rng.random() < 0.60:
        x = rng.normal(0.0, 0.35 * max_vol)
    else:
        x = rng.uniform(-max_vol, max_vol)

    return quantize(x, step, -max_vol, max_vol)


def generate_random_portfolio(rng):
    while True:
        pos = {}
        for product_name in ALL_PRODUCTS:
            q = sample_volume(product_name, rng)
            if q != 0:
                pos[product_name] = q
        if valid_portfolio_random(pos):
            return pos


def sample_biased_portfolio(rng):
    while True:
        pos = {}
        for product_name, center in PRIOR_CENTER.items():
            max_vol = MAX_VOL[product_name]
            step = STEP[product_name]
            x = rng.normal(center, 0.25 * max_vol)
            q = quantize(x, step, -max_vol, max_vol)
            if q != 0:
                pos[product_name] = q
        if valid_portfolio_random(pos):
            return pos


def generate_mixed_portfolio(rng):
    if rng.random() < 0.65:
        return generate_random_portfolio(rng)
    return sample_biased_portfolio(rng)


def mutate_portfolio(base_pos, rng, scale=0.12):
    while True:
        pos = {}
        for product_name in ALL_PRODUCTS:
            current = base_pos.get(product_name, 0)
            max_vol = MAX_VOL[product_name]
            step = STEP[product_name]
            noise = rng.normal(0.0, scale * max_vol)
            q = quantize(current + noise, step, -max_vol, max_vol)
            if q != 0:
                pos[product_name] = q
        if valid_portfolio_random(pos):
            return pos


def positions_to_vector(positions, products):
    return np.array([positions.get(product_name, 0) for product_name in products], dtype=np.float64)


def sample_portfolio_batch(rng, batch_size, products, mode="mixed"):
    pos_dicts = []
    pos_vectors = np.zeros((batch_size, len(products)), dtype=np.float64)

    for i in range(batch_size):
        if mode == "mixed":
            positions = generate_mixed_portfolio(rng)
        elif mode == "biased":
            positions = sample_biased_portfolio(rng)
        else:
            positions = generate_random_portfolio(rng)
        pos_dicts.append(positions)
        pos_vectors[i, :] = positions_to_vector(positions, products)

    return pos_dicts, pos_vectors


def sample_volume_array(product_name, rng, n):
    max_vol = MAX_VOL[product_name]
    step = STEP[product_name]

    mask = rng.random(n) < 0.60
    normal_draws = rng.normal(0.0, 0.35 * max_vol, size=n)
    uniform_draws = rng.uniform(-max_vol, max_vol, size=n)
    vals = np.where(mask, normal_draws, uniform_draws)
    q = np.rint(vals / step) * step
    q = np.clip(q, -max_vol, max_vol)
    return q.astype(np.int16)


def sample_biased_array(product_name, rng, n):
    max_vol = MAX_VOL[product_name]
    step = STEP[product_name]
    center = PRIOR_CENTER[product_name]
    vals = rng.normal(center, 0.25 * max_vol, size=n)
    q = np.rint(vals / step) * step
    q = np.clip(q, -max_vol, max_vol)
    return q.astype(np.int16)


def valid_portfolio_random_mask(pos_matrix, products):
    idx = {p: i for i, p in enumerate(products)}

    exotic_active = (
        (pos_matrix[:, idx["AC_45_KO"]] != 0)
        | (pos_matrix[:, idx["AC_40_BP"]] != 0)
        | (pos_matrix[:, idx["AC_50_CO"]] != 0)
    )

    hedge_products = [
        "AC_35_P",
        "AC_40_P",
        "AC_45_P",
        "AC_50_P",
        "AC_50_C",
        "AC_60_C",
        "AC_50_C_2",
        "AC_50_P_2",
    ]
    hedge_count = np.sum(
        np.column_stack([pos_matrix[:, idx[p]] != 0 for p in hedge_products]),
        axis=1,
    )

    gross_options = np.sum(np.abs(pos_matrix[:, 1:]), axis=1)

    mask = exotic_active
    mask &= hedge_count <= 5
    mask &= pos_matrix[:, idx["AC_45_KO"]] <= 0
    mask &= pos_matrix[:, idx["AC_50_CO"]] <= 25
    mask &= pos_matrix[:, idx["AC_40_BP"]] <= 25
    mask &= ~((gross_options == 0) & (pos_matrix[:, idx["AC"]] != 0))
    return mask


def sample_portfolio_batch_fast(rng, batch_size, products, mode="mixed", oversample=4):
    accepted = []

    while len(accepted) < batch_size:
        n = max(batch_size * oversample, 512)
        random_mat = np.column_stack([sample_volume_array(p, rng, n) for p in products])
        biased_mat = np.column_stack([sample_biased_array(p, rng, n) for p in products])

        if mode == "mixed":
            row_mask = (rng.random(n) < 0.65)[:, None]
            pos_matrix = np.where(row_mask, random_mat, biased_mat)
        elif mode == "biased":
            pos_matrix = biased_mat
        else:
            pos_matrix = random_mat

        valid_mask = valid_portfolio_random_mask(pos_matrix, products)
        valid_rows = pos_matrix[valid_mask]
        if len(valid_rows) == 0:
            continue

        needed = batch_size - len(accepted)
        accepted.extend(valid_rows[:needed])

    pos_vectors = np.array(accepted[:batch_size], dtype=np.float64)
    pos_dicts = []
    for row in pos_vectors.astype(int):
        positions = {
            product_name: int(qty)
            for product_name, qty in zip(products, row)
            if qty != 0
        }
        pos_dicts.append(positions)

    return pos_dicts, pos_vectors


def sample_discrete_grid_array(values, center, rng, n, local_prob=0.70):
    values = np.array(sorted(set(values)), dtype=np.int16)
    if len(values) == 1:
        return np.full(n, values[0], dtype=np.int16)

    uniform_vals = values[rng.integers(0, len(values), size=n)]
    span = float(values[-1] - values[0])
    sigma = max(span / 6.0, 1.0)
    draws = rng.normal(center, sigma, size=n)
    nearest_idx = np.abs(draws[:, None] - values[None, :]).argmin(axis=1)
    local_vals = values[nearest_idx]
    use_local = rng.random(n) < local_prob
    return np.where(use_local, local_vals, uniform_vals).astype(np.int16)


def sample_refine_batch_fast(
    rng,
    batch_size,
    refine_grid,
    center_positions,
    products,
):
    pos_matrix = np.column_stack(
        [
            sample_discrete_grid_array(
                refine_grid[product_name],
                int(center_positions.get(product_name, 0)),
                rng,
                batch_size,
            )
            for product_name in products
        ]
    )

    pos_vectors = pos_matrix.astype(np.float64)
    pos_dicts = []
    for row in pos_matrix:
        positions = {
            product_name: int(qty)
            for product_name, qty in zip(products, row)
            if qty != 0
        }
        pos_dicts.append(positions)

    return pos_dicts, pos_vectors


def sample_mutation_batch_fast(
    rng,
    batch_size,
    base_positions,
    products,
    delta_ranges=None,
):
    if delta_ranges is None:
        delta_ranges = BEST_LOCAL_MUTATION_RANGES

    base = np.array([int(base_positions.get(product_name, 0)) for product_name in products], dtype=np.int16)
    pos_matrix = np.tile(base, (batch_size, 1))

    for j, product_name in enumerate(products):
        if product_name not in delta_ranges:
            pos_matrix[:, j] = 0 if base[j] == 0 else base[j]
            continue

        lo_delta, hi_delta, step = delta_ranges[product_name]
        delta_values = np.arange(lo_delta, hi_delta + 1, step, dtype=np.int16)
        delta = delta_values[rng.integers(0, len(delta_values), size=batch_size)]
        vals = pos_matrix[:, j].astype(np.int32) + delta
        vals = np.clip(vals, -MAX_VOL[product_name], MAX_VOL[product_name])
        pos_matrix[:, j] = vals.astype(np.int16)

    pos_vectors = pos_matrix.astype(np.float64)
    pos_dicts = []
    for row in pos_matrix:
        positions = {
            product_name: int(qty)
            for product_name, qty in zip(products, row)
            if qty != 0
        }
        pos_dicts.append(positions)

    return pos_dicts, pos_vectors


def build_refine_grid(best_positions, radius_steps=2):
    refined = {}

    for product_name, base_grid in FULL_COARSE_GRID.items():
        center = int(best_positions.get(product_name, 0))
        step = REFINE_STEPS[product_name]
        lo = max(min(base_grid), center - radius_steps * step)
        hi = min(max(base_grid), center + radius_steps * step)
        refined[product_name] = list(range(lo, hi + 1, step))

    return refined


def run_resumable_bruteforce(
    paths,
    product_grids,
    run_name="broad",
    save_every=1000,
    top_n=100,
    resume=True,
    max_runs=None,
):
    output_paths = make_output_paths(run_name)

    for product_name, grid in product_grids.items():
        for qty in grid:
            if abs(qty) > MARKET[product_name]["max_vol"]:
                raise ValueError(
                    f"{product_name}: grid qty {qty} exceeds max_vol {MARKET[product_name]['max_vol']}"
                )

    last_run_id, top_rows, best_row, best_positions = load_resume_state(
        output_paths, resume=resume
    )
    best_score = best_row["score"] if best_row is not None else -1e18

    products = list(product_grids.keys())
    cache = build_grid_pnl_cache(paths, product_grids)
    processed_this_session = 0
    start_time = time.time()

    for run_id, values in enumerate(product(*[product_grids[p] for p in products]), start=1):
        if run_id <= last_run_id:
            continue

        positions = {}
        total = np.zeros(paths.shape[0])

        for product_name, qty in zip(products, values):
            if qty != 0:
                positions[product_name] = qty
                total += cache[product_name][qty]

        stats = evaluate_pnl_vector(total)
        stats["score"] = score_stats(stats)
        stats.update(calculate_scores(stats))

        row = {
            "run_id": run_id,
            **stats,
            "positions": json.dumps(positions, sort_keys=True),
        }
        row.update(expand_positions(positions))

        append_result(row, output_paths["results_csv"])

        if stats["score"] > best_score:
            best_score = stats["score"]
            best_row = row
            best_positions = positions
            save_best_json(best_row, best_positions, output_paths["best_json"])
            save_best_distribution(paths, best_positions, output_paths["best_dist_png"])

        top_rows.append(row)
        if len(top_rows) > top_n * 5:
            top_rows = sorted(top_rows, key=lambda x: x["score"], reverse=True)[:top_n]

        processed_this_session += 1

        if run_id % save_every == 0:
            elapsed = time.time() - start_time
            progress_row = {
                "run_id": run_id,
                "best_score": best_score,
                "elapsed_seconds": elapsed,
            }
            append_progress_row(progress_row, output_paths["progress_csv"])
            save_top_results(top_rows, output_paths["top_csv"], top_n=top_n)
            save_progress_plot(output_paths["progress_csv"], output_paths["progress_png"])
            save_checkpoint(output_paths["checkpoint_json"], run_id, best_row)
            print(
                f"[{run_name}] run {run_id:,} | "
                f"best score {best_score:.2f} | "
                f"best mean {best_row['mean']:.2f} | "
                f"p05 {best_row['p05']:.2f}"
            )

        if max_runs is not None and processed_this_session >= max_runs:
            break

    if best_row is not None:
        save_top_results(top_rows, output_paths["top_csv"], top_n=top_n)
        save_progress_plot(output_paths["progress_csv"], output_paths["progress_png"])
        save_checkpoint(output_paths["checkpoint_json"], best_row["run_id"], best_row)
        write_summary(best_row, output_paths["summary_txt"])

    return best_row, best_positions, output_paths


def run_generated_bruteforce(
    paths,
    product_grids,
    portfolio_generator,
    run_name="generated",
    save_every=1000,
    top_n=100,
    resume=True,
    max_runs=None,
):
    output_paths = make_output_paths(run_name)

    for product_name, grid in product_grids.items():
        for qty in grid:
            if abs(qty) > MARKET[product_name]["max_vol"]:
                raise ValueError(
                    f"{product_name}: grid qty {qty} exceeds max_vol {MARKET[product_name]['max_vol']}"
                )

    last_run_id, top_rows, best_row, best_positions = load_resume_state(
        output_paths, resume=resume
    )
    best_score = best_row["score"] if best_row is not None else -1e18

    cache = build_grid_pnl_cache(paths, product_grids)
    processed_this_session = 0
    start_time = time.time()

    for run_id, positions in enumerate(portfolio_generator(), start=1):
        if run_id <= last_run_id:
            continue

        validate_positions(positions)
        total = np.zeros(paths.shape[0])
        for product_name, qty in positions.items():
            total += cache[product_name][qty]

        stats = evaluate_pnl_vector(total)
        stats["score"] = score_stats(stats)
        stats.update(calculate_scores(stats))
        row = {
            "run_id": run_id,
            **stats,
            "positions": json.dumps(positions, sort_keys=True),
        }
        row.update(expand_positions(positions))

        append_result(row, output_paths["results_csv"])

        if stats["score"] > best_score:
            best_score = stats["score"]
            best_row = row
            best_positions = positions
            save_best_json(best_row, best_positions, output_paths["best_json"])
            save_best_distribution(paths, best_positions, output_paths["best_dist_png"])

        top_rows.append(row)
        if len(top_rows) > top_n * 5:
            top_rows = sorted(top_rows, key=lambda x: x["score"], reverse=True)[:top_n]

        processed_this_session += 1

        if run_id % save_every == 0:
            elapsed = time.time() - start_time
            progress_row = {
                "run_id": run_id,
                "best_score": best_score,
                "elapsed_seconds": elapsed,
            }
            append_progress_row(progress_row, output_paths["progress_csv"])
            save_top_results(top_rows, output_paths["top_csv"], top_n=top_n)
            save_progress_plot(output_paths["progress_csv"], output_paths["progress_png"])
            save_checkpoint(output_paths["checkpoint_json"], run_id, best_row)
            print(
                f"[{run_name}] run {run_id:,} | "
                f"best score {best_score:.2f} | "
                f"best mean {best_row['mean']:.2f} | "
                f"p05 {best_row['p05']:.2f}"
            )

        if max_runs is not None and processed_this_session >= max_runs:
            break

    if best_row is not None:
        save_top_results(top_rows, output_paths["top_csv"], top_n=top_n)
        save_progress_plot(output_paths["progress_csv"], output_paths["progress_png"])
        save_checkpoint(output_paths["checkpoint_json"], best_row["run_id"], best_row)
        write_summary(best_row, output_paths["summary_txt"])

    return best_row, best_positions, output_paths


def run_full_coarse_broad_search(
    paths,
    run_name="broad",
    save_every=1000,
    top_n=100,
    resume=True,
    max_runs=None,
):
    return run_generated_bruteforce(
        paths,
        FULL_COARSE_GRID,
        generate_full_coarse_portfolios,
        run_name=run_name,
        save_every=save_every,
        top_n=top_n,
        resume=resume,
        max_runs=max_runs,
    )


def run_full_coverage_search(
    paths,
    run_name="coverage",
    save_every=1000,
    top_n=100,
    resume=True,
    max_runs=None,
):
    return run_generated_bruteforce(
        paths,
        FULL_COARSE_GRID,
        generate_full_coverage_portfolios,
        run_name=run_name,
        save_every=save_every,
        top_n=top_n,
        resume=resume,
        max_runs=max_runs,
    )


def run_random_broad_search(
    paths,
    n_runs,
    run_name="random_broad",
    seed=123,
    save_every=1000,
    top_n=100,
    resume=True,
    mode="mixed",
):
    output_paths = make_output_paths(run_name)
    last_run_id, top_rows, best_row, best_positions = load_resume_state(
        output_paths, resume=resume
    )
    best_score = best_row["score"] if best_row is not None else -1e18

    rng = np.random.default_rng(seed)
    cache = build_unit_pnl_cache(paths, ALL_PRODUCTS)
    start_time = time.time()
    pending_rows = []

    for run_id in range(1, n_runs + 1):
        if mode == "mixed":
            positions = generate_mixed_portfolio(rng)
        elif mode == "biased":
            positions = sample_biased_portfolio(rng)
        else:
            positions = generate_random_portfolio(rng)

        if run_id <= last_run_id:
            continue

        total = np.zeros(paths.shape[0])
        for product_name, qty in positions.items():
            if qty > 0:
                total += qty * cache[product_name]["long_unit"]
            else:
                total += (-qty) * cache[product_name]["short_unit"]

        stats = evaluate_pnl_vector(total)
        stats["score"] = score_stats(stats)
        stats.update(calculate_scores(stats))

        row = {
            "run_id": run_id,
            **stats,
            "positions": json.dumps(positions, sort_keys=True),
        }
        row.update(expand_positions(positions))

        pending_rows.append(row)

        if stats["score"] > best_score:
            best_score = stats["score"]
            best_row = row
            best_positions = positions
            save_best_json(best_row, best_positions, output_paths["best_json"])
            save_best_distribution(paths, best_positions, output_paths["best_dist_png"])

        top_rows.append(row)
        if len(top_rows) > top_n * 5:
            top_rows = sorted(top_rows, key=lambda x: x["score"], reverse=True)[:top_n]

        if run_id % save_every == 0:
            append_results(pending_rows, output_paths["results_csv"])
            pending_rows = []
            elapsed = time.time() - start_time
            progress_row = {
                "run_id": run_id,
                "best_score": best_score,
                "elapsed_seconds": elapsed,
            }
            append_progress_row(progress_row, output_paths["progress_csv"])
            save_top_results(top_rows, output_paths["top_csv"], top_n=top_n)
            save_progress_plot(output_paths["progress_csv"], output_paths["progress_png"])
            save_checkpoint(output_paths["checkpoint_json"], run_id, best_row)
            print(
                f"[{run_name}] run {run_id:,} | "
                f"best score {best_score:.2f} | "
                f"best mean {best_row['mean']:.2f} | "
                f"p05 {best_row['p05']:.2f}"
            )

    append_results(pending_rows, output_paths["results_csv"])
    if best_row is not None:
        save_top_results(top_rows, output_paths["top_csv"], top_n=top_n)
        save_progress_plot(output_paths["progress_csv"], output_paths["progress_png"])
        save_checkpoint(output_paths["checkpoint_json"], n_runs, best_row)
        write_summary(best_row, output_paths["summary_txt"])

    return best_row, best_positions, output_paths


def run_random_broad_search_batched(
    paths,
    n_runs,
    run_name="random_broad_batched",
    seed=123,
    save_every=1000,
    top_n=100,
    resume=True,
    mode="mixed",
    batch_size=256,
):
    output_paths = make_output_paths(run_name)
    last_run_id, top_rows, best_row, best_positions = load_resume_state(
        output_paths, resume=resume
    )
    best_score = best_row["score"] if best_row is not None else -1e18

    rng = np.random.default_rng(seed)
    products = ALL_PRODUCTS
    long_units, short_units = build_unit_pnl_matrices(paths, products)
    start_time = time.time()
    pending_rows = []

    for batch_start in range(1, n_runs + 1, batch_size):
        current_batch = min(batch_size, n_runs - batch_start + 1)
        pos_dicts, pos_vectors = sample_portfolio_batch_fast(rng, current_batch, products, mode=mode)

        if batch_start + current_batch - 1 <= last_run_id:
            continue

        pos_pos = np.clip(pos_vectors, 0.0, None)
        pos_neg = np.clip(-pos_vectors, 0.0, None)
        with np.errstate(all="ignore"):
            pnl_matrix = pos_pos @ long_units + pos_neg @ short_units
        stats_rows = evaluate_pnl_matrix(pnl_matrix)

        for i in range(current_batch):
            run_id = batch_start + i
            if run_id <= last_run_id:
                continue

            positions = pos_dicts[i]
            stats = stats_rows[i]
            row = {
                "run_id": run_id,
                **stats,
                "positions": json.dumps(positions, sort_keys=True),
            }
            row.update(expand_positions(positions))
            pending_rows.append(row)

            if stats["score"] > best_score:
                best_score = stats["score"]
                best_row = row
                best_positions = positions
                save_best_json(best_row, best_positions, output_paths["best_json"])
                save_best_distribution(paths, best_positions, output_paths["best_dist_png"])

            top_rows.append(row)
            if len(top_rows) > top_n * 5:
                top_rows = sorted(top_rows, key=lambda x: x["score"], reverse=True)[:top_n]

        last_processed = batch_start + current_batch - 1
        if last_processed % save_every < current_batch or last_processed == n_runs:
            append_results(pending_rows, output_paths["results_csv"])
            pending_rows = []
            elapsed = time.time() - start_time
            progress_row = {
                "run_id": last_processed,
                "best_score": best_score,
                "elapsed_seconds": elapsed,
            }
            append_progress_row(progress_row, output_paths["progress_csv"])
            save_top_results(top_rows, output_paths["top_csv"], top_n=top_n)
            save_progress_plot(output_paths["progress_csv"], output_paths["progress_png"])
            save_checkpoint(output_paths["checkpoint_json"], last_processed, best_row)
            print(
                f"[{run_name}] run {last_processed:,} | "
                f"best score {best_score:.2f} | "
                f"best mean {best_row['mean']:.2f} | "
                f"p05 {best_row['p05']:.2f}"
            )

    append_results(pending_rows, output_paths["results_csv"])
    if best_row is not None:
        save_top_results(top_rows, output_paths["top_csv"], top_n=top_n)
        save_progress_plot(output_paths["progress_csv"], output_paths["progress_png"])
        save_checkpoint(output_paths["checkpoint_json"], n_runs, best_row)
        write_summary(best_row, output_paths["summary_txt"])

    return best_row, best_positions, output_paths


def run_local_refine_search_batched(
    paths,
    center_positions,
    refine_grid,
    n_runs,
    run_name="random_refine_round2",
    seed=456,
    save_every=1000,
    top_n=100,
    resume=True,
    batch_size=1024,
):
    output_paths = make_output_paths(run_name)
    last_run_id, top_rows, best_row, best_positions = load_resume_state(
        output_paths, resume=resume
    )
    best_score = best_row["score"] if best_row is not None else -1e18

    rng = np.random.default_rng(seed)
    products = ALL_PRODUCTS
    long_units, short_units = build_unit_pnl_matrices(paths, products)
    start_time = time.time()
    pending_rows = []

    for batch_start in range(1, n_runs + 1, batch_size):
        current_batch = min(batch_size, n_runs - batch_start + 1)
        pos_dicts, pos_vectors = sample_refine_batch_fast(
            rng,
            current_batch,
            refine_grid,
            center_positions,
            products,
        )

        if batch_start + current_batch - 1 <= last_run_id:
            continue

        pos_pos = np.clip(pos_vectors, 0.0, None)
        pos_neg = np.clip(-pos_vectors, 0.0, None)
        with np.errstate(all="ignore"):
            pnl_matrix = pos_pos @ long_units + pos_neg @ short_units
        stats_rows = evaluate_pnl_matrix(pnl_matrix)

        for i in range(current_batch):
            run_id = batch_start + i
            if run_id <= last_run_id:
                continue

            positions = pos_dicts[i]
            stats = stats_rows[i]
            row = {
                "run_id": run_id,
                **stats,
                "positions": json.dumps(positions, sort_keys=True),
            }
            row.update(expand_positions(positions))
            pending_rows.append(row)

            if stats["score"] > best_score:
                best_score = stats["score"]
                best_row = row
                best_positions = positions
                save_best_json(best_row, best_positions, output_paths["best_json"])
                save_best_distribution(paths, best_positions, output_paths["best_dist_png"])

            top_rows.append(row)
            if len(top_rows) > top_n * 5:
                top_rows = sorted(top_rows, key=lambda x: x["score"], reverse=True)[:top_n]

        last_processed = batch_start + current_batch - 1
        if last_processed % save_every < current_batch or last_processed == n_runs:
            append_results(pending_rows, output_paths["results_csv"])
            pending_rows = []
            elapsed = time.time() - start_time
            progress_row = {
                "run_id": last_processed,
                "best_score": best_score,
                "elapsed_seconds": elapsed,
            }
            append_progress_row(progress_row, output_paths["progress_csv"])
            save_top_results(top_rows, output_paths["top_csv"], top_n=top_n)
            save_progress_plot(output_paths["progress_csv"], output_paths["progress_png"])
            save_checkpoint(output_paths["checkpoint_json"], last_processed, best_row)
            print(
                f"[{run_name}] run {last_processed:,} | "
                f"best score {best_score:.2f} | "
                f"best mean {best_row['mean']:.2f} | "
                f"p05 {best_row['p05']:.2f}"
            )

    append_results(pending_rows, output_paths["results_csv"])
    if best_row is not None:
        save_top_results(top_rows, output_paths["top_csv"], top_n=top_n)
        save_progress_plot(output_paths["progress_csv"], output_paths["progress_png"])
        save_checkpoint(output_paths["checkpoint_json"], n_runs, best_row)
        write_summary(best_row, output_paths["summary_txt"])

    return best_row, best_positions, output_paths


def run_local_mutation_search_batched(
    paths,
    base_positions,
    n_runs,
    run_name="random_local_mutation",
    seed=789,
    save_every=1000,
    top_n=100,
    resume=True,
    batch_size=1024,
    delta_ranges=None,
):
    output_paths = make_output_paths(run_name)
    last_run_id, top_rows, best_row, best_positions = load_resume_state(
        output_paths, resume=resume
    )
    best_score = best_row["score"] if best_row is not None else -1e18

    rng = np.random.default_rng(seed)
    products = ALL_PRODUCTS
    long_units, short_units = build_unit_pnl_matrices(paths, products)
    start_time = time.time()
    pending_rows = []

    for batch_start in range(1, n_runs + 1, batch_size):
        current_batch = min(batch_size, n_runs - batch_start + 1)
        pos_dicts, pos_vectors = sample_mutation_batch_fast(
            rng,
            current_batch,
            base_positions,
            products,
            delta_ranges=delta_ranges,
        )

        if batch_start + current_batch - 1 <= last_run_id:
            continue

        pos_pos = np.clip(pos_vectors, 0.0, None)
        pos_neg = np.clip(-pos_vectors, 0.0, None)
        with np.errstate(all="ignore"):
            pnl_matrix = pos_pos @ long_units + pos_neg @ short_units
        stats_rows = evaluate_pnl_matrix(pnl_matrix)

        for i in range(current_batch):
            run_id = batch_start + i
            if run_id <= last_run_id:
                continue

            positions = pos_dicts[i]
            stats = stats_rows[i]
            row = {
                "run_id": run_id,
                **stats,
                "positions": json.dumps(positions, sort_keys=True),
            }
            row.update(expand_positions(positions))
            pending_rows.append(row)

            if stats["score"] > best_score:
                best_score = stats["score"]
                best_row = row
                best_positions = positions
                save_best_json(best_row, best_positions, output_paths["best_json"])
                save_best_risk_reports(paths, best_positions, output_paths)

            top_rows.append(row)
            if len(top_rows) > top_n * 5:
                top_rows = sorted(top_rows, key=lambda x: x["score"], reverse=True)[:top_n]

        last_processed = batch_start + current_batch - 1
        if last_processed % save_every < current_batch or last_processed == n_runs:
            append_results(pending_rows, output_paths["results_csv"])
            pending_rows = []
            elapsed = time.time() - start_time
            progress_row = {
                "run_id": last_processed,
                "best_score": best_score,
                "elapsed_seconds": elapsed,
            }
            append_progress_row(progress_row, output_paths["progress_csv"])
            save_top_results(top_rows, output_paths["top_csv"], top_n=top_n)
            save_progress_plot(output_paths["progress_csv"], output_paths["progress_png"])
            save_checkpoint(output_paths["checkpoint_json"], last_processed, best_row)
            print(
                f"[{run_name}] run {last_processed:,} | "
                f"best score {best_score:.2f} | "
                f"best mean {best_row['mean']:.2f} | "
                f"p05 {best_row['p05']:.2f}"
            )

    append_results(pending_rows, output_paths["results_csv"])
    if best_row is not None:
        save_top_results(top_rows, output_paths["top_csv"], top_n=top_n)
        save_progress_plot(output_paths["progress_csv"], output_paths["progress_png"])
        save_checkpoint(output_paths["checkpoint_json"], n_runs, best_row)
        write_summary(best_row, output_paths["summary_txt"])
        save_best_risk_reports(paths, best_positions, output_paths)

    return best_row, best_positions, output_paths


def refine_top_portfolios(
    paths,
    top_rows,
    n_mutations_per_parent=500,
    run_name="random_refine",
    seed=123,
    save_every=1000,
    top_n=100,
    resume=False,
):
    output_paths = make_output_paths(run_name)
    if not resume:
        load_resume_state(output_paths, resume=False)

    rng = np.random.default_rng(seed)
    best_score = -1e18
    best_row = None
    best_positions = None
    top_results = []
    start_time = time.time()
    run_id = 0
    cache = build_unit_pnl_cache(paths, ALL_PRODUCTS)
    pending_rows = []

    for parent in top_rows:
        base_pos = json.loads(parent["positions"])
        for _ in range(n_mutations_per_parent):
            run_id += 1
            positions = mutate_portfolio(base_pos, rng, scale=0.12)
            total = np.zeros(paths.shape[0])
            for product_name, qty in positions.items():
                if qty > 0:
                    total += qty * cache[product_name]["long_unit"]
                else:
                    total += (-qty) * cache[product_name]["short_unit"]

            stats = evaluate_pnl_vector(total)
            stats["score"] = score_stats(stats)
            stats.update(calculate_scores(stats))
            row = {
                "run_id": run_id,
                **stats,
                "positions": json.dumps(positions, sort_keys=True),
            }
            row.update(expand_positions(positions))
            pending_rows.append(row)

            if stats["score"] > best_score:
                best_score = stats["score"]
                best_row = row
                best_positions = positions
                save_best_json(best_row, best_positions, output_paths["best_json"])
                save_best_distribution(paths, best_positions, output_paths["best_dist_png"])

            top_results.append(row)
            if len(top_results) > top_n * 5:
                top_results = sorted(top_results, key=lambda x: x["score"], reverse=True)[:top_n]

            if run_id % save_every == 0:
                append_results(pending_rows, output_paths["results_csv"])
                pending_rows = []
                elapsed = time.time() - start_time
                progress_row = {
                    "run_id": run_id,
                    "best_score": best_score,
                    "elapsed_seconds": elapsed,
                }
                append_progress_row(progress_row, output_paths["progress_csv"])
                save_top_results(top_results, output_paths["top_csv"], top_n=top_n)
                save_progress_plot(output_paths["progress_csv"], output_paths["progress_png"])
                save_checkpoint(output_paths["checkpoint_json"], run_id, best_row)
                print(
                    f"[{run_name}] run {run_id:,} | "
                    f"best score {best_score:.2f} | "
                    f"best mean {best_row['mean']:.2f} | "
                    f"p05 {best_row['p05']:.2f}"
                )

    append_results(pending_rows, output_paths["results_csv"])
    if best_row is not None:
        save_top_results(top_results, output_paths["top_csv"], top_n=top_n)
        save_progress_plot(output_paths["progress_csv"], output_paths["progress_png"])
        save_checkpoint(output_paths["checkpoint_json"], run_id, best_row)
        write_summary(best_row, output_paths["summary_txt"])

    return best_row, best_positions, output_paths


def reevaluate_on_new_seeds(finalists, n_paths=300_000, seeds=(101, 202, 303, 404, 505)):
    rows = []

    for candidate_id, row in enumerate(finalists):
        positions = json.loads(row["positions"]) if isinstance(row["positions"], str) else row["positions"]

        seed_stats = []
        for seed in seeds:
            paths = simulate_paths(n_paths=n_paths, seed=seed, antithetic=True)
            stats = evaluate_strategy(f"candidate_{candidate_id}", paths, positions)
            stats["score"] = score_stats(stats)
            stats.update(calculate_scores(stats))
            seed_stats.append(stats)

        rows.append({
            "candidate_id": candidate_id,
            "avg_mean": np.mean([s["mean"] for s in seed_stats]),
            "avg_p05": np.mean([s["p05"] for s in seed_stats]),
            "worst_p05": np.min([s["p05"] for s in seed_stats]),
            "avg_score": np.mean([s["score"] for s in seed_stats]),
            "avg_score_safe": np.mean([s["score_safe"] for s in seed_stats]),
            "avg_score_aggressive": np.mean([s["score_aggressive"] for s in seed_stats]),
            "positions": json.dumps(positions, sort_keys=True),
        })

    return pd.DataFrame(rows).sort_values("avg_score", ascending=False)


def load_top_candidate_rows(top_csv_paths, top_n_each=10):
    seen = set()
    rows = []

    for csv_path in top_csv_paths:
        df = pd.read_csv(csv_path).head(top_n_each)
        for row in df.to_dict("records"):
            positions = row["positions"]
            if positions in seen:
                continue
            seen.add(positions)
            rows.append(row)

    return rows


def reevaluate_candidates(
    candidates,
    n_paths=100_000,
    seeds=(11, 22, 33, 44, 55),
    official_batches=5_000,
    official_batch_size=100,
):
    rows = []

    for candidate_id, row in enumerate(candidates):
        positions = json.loads(row["positions"]) if isinstance(row["positions"], str) else row["positions"]
        seed_results = []

        for seed in seeds:
            paths = simulate_paths(n_paths=n_paths, seed=seed, antithetic=True)
            pnl = portfolio_pnl(paths, positions)
            stats = evaluate_pnl_vector(pnl)
            official = official_score_stats(
                pnl,
                n_batches=official_batches,
                batch_size=official_batch_size,
                seed=seed + 1000,
            )
            seed_results.append({**stats, **official})

        rows.append(
            {
                "candidate_id": candidate_id,
                "avg_mean": float(np.mean([x["mean"] for x in seed_results])),
                "avg_p05": float(np.mean([x["p05"] for x in seed_results])),
                "avg_p01": float(np.mean([x["p01"] for x in seed_results])),
                "worst_p05": float(np.min([x["p05"] for x in seed_results])),
                "avg_official_mean": float(np.mean([x["official_mean"] for x in seed_results])),
                "avg_official_p05": float(np.mean([x["official_p05"] for x in seed_results])),
                "avg_official_p01": float(np.mean([x["official_p01"] for x in seed_results])),
                "worst_official_p05": float(np.min([x["official_p05"] for x in seed_results])),
                "avg_official_prob_loss": float(np.mean([x["official_prob_loss"] for x in seed_results])),
                "avg_official_score": float(np.mean([x["official_score"] for x in seed_results])),
                "positions": json.dumps(positions, sort_keys=True),
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["avg_official_score", "avg_official_mean"],
        ascending=False,
    )


def evaluate_candidate_official_runs(
    name,
    positions,
    seeds,
    batch_size=100,
    antithetic=True,
):
    official_scores = []

    for seed in seeds:
        paths = simulate_paths(n_paths=batch_size, seed=seed, antithetic=antithetic)
        pnl = portfolio_pnl(paths, positions)
        official_scores.append(float(np.mean(pnl)))

    official_scores = np.array(official_scores, dtype=float)
    official_p05 = float(np.percentile(official_scores, 5))
    official_p01 = float(np.percentile(official_scores, 1))
    prob_loss = float(np.mean(official_scores < 0))

    return {
        "name": name,
        "avg_official_mean": float(np.mean(official_scores)),
        "avg_official_std": float(np.std(official_scores)),
        "avg_official_p05": official_p05,
        "avg_official_p01": official_p01,
        "avg_official_prob_loss": prob_loss,
        "worst_official_score": float(np.min(official_scores)),
        "final_score": float(
            np.mean(official_scores)
            + 0.30 * official_p05
            - 50.0 * prob_loss
        ),
        "scores": official_scores,
    }


def run_final_robustness_compare(
    candidates,
    run_name="final_robustness_compare",
    n_seeds=300,
    seed_start=10_000,
    batch_size=100,
):
    output_paths = make_output_paths(run_name)
    seeds = tuple(range(seed_start, seed_start + n_seeds))

    summary_rows = []
    seed_rows = []
    best_row = None
    best_positions = None

    for name, positions in candidates.items():
        validate_positions(positions)
        result = evaluate_candidate_official_runs(
            name,
            positions,
            seeds=seeds,
            batch_size=batch_size,
            antithetic=True,
        )
        scores = result.pop("scores")
        row = {
            **result,
            "positions": json.dumps(positions, sort_keys=True),
        }
        row.update(expand_positions(positions))
        summary_rows.append(row)

        for seed, score in zip(seeds, scores):
            seed_rows.append(
                {
                    "candidate": name,
                    "seed": seed,
                    "official_score": float(score),
                }
            )

        if best_row is None or row["final_score"] > best_row["final_score"]:
            best_row = row
            best_positions = positions

    summary_df = pd.DataFrame(summary_rows).sort_values(
        ["final_score", "avg_official_mean"],
        ascending=False,
    )
    summary_df.to_csv(output_paths["top_csv"], index=False)
    pd.DataFrame(seed_rows).to_csv(output_paths["results_csv"], index=False)

    if best_row is not None:
        save_best_json(best_row, best_positions, output_paths["best_json"])
        paths = simulate_paths(n_paths=100_000, seed=seed_start, antithetic=True)
        save_best_risk_reports(paths, best_positions, output_paths)
        write_summary(best_row, output_paths["summary_txt"])
        save_checkpoint(output_paths["checkpoint_json"], n_seeds, best_row)

    return summary_df, best_row, best_positions, output_paths


def write_summary(best_row, summary_path):
    if best_row is None:
        return

    positions_value = best_row["positions"]
    if isinstance(positions_value, str):
        positions = json.loads(positions_value)
    else:
        positions = positions_value

    with open(summary_path, "w") as f:
        f.write("Best portfolio found\n")
        f.write("====================\n\n")
        preferred_keys = [
            "score",
            "final_score",
            "mean",
            "median",
            "std",
            "score_std_100",
            "p05",
            "p01",
            "worst",
            "p_loss",
            "avg_official_mean",
            "avg_official_std",
            "avg_official_p05",
            "avg_official_p01",
            "avg_official_prob_loss",
            "worst_official_score",
        ]
        for key in preferred_keys:
            if key in best_row:
                f.write(f"{key}: {best_row[key]}\n")

        f.write("\nPositions:\n")
        for product_name, qty in positions.items():
            f.write(f"{product_name}: {qty}\n")


def refine_grid(best_positions):
    refined = {}

    for product_name, max_vol in {
        "AC": 200,
        "AC_50_CO": 50,
        "AC_50_C_2": 50,
        "AC_50_P_2": 50,
        "AC_40_BP": 50,
        "AC_45_KO": 500,
        "AC_35_P": 50,
        "AC_40_P": 50,
        "AC_45_P": 50,
    }.items():
        center = int(best_positions.get(product_name, 0))

        if product_name == "AC_45_KO":
            values = range(max(-500, center - 100), min(500, center + 100) + 1, 25)
        elif product_name == "AC":
            values = range(max(-200, center - 100), min(200, center + 100) + 1, 25)
        else:
            values = range(max(-50, center - 20), min(50, center + 20) + 1, 5)

        refined[product_name] = list(values)

    return refined


# -----------------------------
# Example usage
# -----------------------------

if __name__ == "__main__":
    paths = simulate_paths(n_paths=300_000, seed=42, antithetic=True)

    table = analyze_with_black_scholes_and_mc(paths)
    print(table.to_string(index=False))

    print("\nExotic diagnostics:")
    print(pd.Series(exotic_diagnostics(paths)))

    strategies = {
        "sell_ko_naked": {
            "AC_45_KO": -500,
        },
        "sell_binary_naked": {
            "AC_40_BP": -50,
        },
        "sell_chooser_naked": {
            "AC_50_CO": -50,
        },
        "chooser_vs_2w_straddle": {
            "AC_50_CO": -50,
            "AC_50_C_2": 50,
            "AC_50_P_2": 50,
        },
        "binary_hedged": {
            "AC_40_BP": -25,
            "AC_45_P": 50,
            "AC_40_P": -50,
        },
        "ko_partial_hedge": {
            "AC_45_KO": -500,
            "AC_45_P": 50,
            "AC_35_P": -50,
        },
        "combined_candidate": {
            "AC_45_KO": -500,
            "AC_40_BP": -50,
            "AC_50_CO": -50,
            "AC_50_C_2": 50,
            "AC_50_P_2": 50,
        },
    }

    strategy_table = build_strategy_table(paths, strategies)
    print("\nStrategy comparison:")
    print(
        strategy_table[
            [
                "name",
                "mean",
                "median",
                "p_loss",
                "p05",
                "p01",
                "worst",
                "score_p05_10",
                "score_p05_25",
                "score_std_100_sims",
            ]
        ].to_string(index=False)
    )

    candidate = strategies["combined_candidate"]
    pnl = portfolio_pnl(paths, candidate)
    print("\nCombined candidate:")
    print(candidate)
    print("\nCombined candidate PnL summary:")
    print(pd.Series(summarize_pnl(pnl)))

    # Use fewer antithetic paths for the grid search so the optimizer stays fast enough
    # to iterate on, while still remaining stable.
    search_paths = simulate_paths(n_paths=80_000, seed=43, antithetic=True)

    core_search_grids = {
        "AC_50_CO": [-50, -25, 0, 25, 50],
        "AC_50_C_2": [-50, -25, 0, 25, 50],
        "AC_50_P_2": [-50, -25, 0, 25, 50],
        "AC_40_BP": [-50, -25, 0, 25, 50],
        "AC_45_KO": [-500, -250, 0, 250, 500],
    }
    core_search = brute_force_search(search_paths, core_search_grids, top_n=10)
    print("\nTop portfolios from core search:")
    print(
        core_search[
            [
                "mean",
                "p_loss",
                "p05",
                "p01",
                "worst",
                "score_p05_10",
                "score_p05_25",
                "AC_50_CO",
                "AC_50_C_2",
                "AC_50_P_2",
                "AC_40_BP",
                "AC_45_KO",
            ]
        ].to_string(index=False)
    )

    hedge_overlay_grids = {
        "AC_45_P": [-50, -25, 0, 25, 50],
        "AC_40_P": [-50, -25, 0, 25, 50],
        "AC_35_P": [-50, -25, 0, 25, 50],
    }
    hedge_search = brute_force_search(
        search_paths,
        hedge_overlay_grids,
        base_positions=candidate,
        top_n=10,
    )
    print("\nTop hedge overlays on combined candidate:")
    print(
        hedge_search[
            [
                "mean",
                "p_loss",
                "p05",
                "p01",
                "worst",
                "score_p05_10",
                "score_p05_25",
                "AC_45_P",
                "AC_40_P",
                "AC_35_P",
            ]
        ].to_string(index=False)
    )

    smoke_grids = {
        "AC_50_CO": [-50, 0, 50],
        "AC_40_BP": [-50, 0, 50],
        "AC_45_KO": [-500, 0, 500],
    }
    smoke_paths = simulate_paths(n_paths=20_000, seed=44, antithetic=True)
    best_row, best_positions, output_paths = run_resumable_bruteforce(
        smoke_paths,
        smoke_grids,
        run_name="smoke",
        save_every=5,
        top_n=10,
        resume=False,
    )
    print("\nSmoke brute-force run:")
    print(output_paths["dir"])
    if best_row is not None:
        print(
            f"Best smoke score {best_row['score']:.2f} | "
            f"mean {best_row['mean']:.2f} | "
            f"p05 {best_row['p05']:.2f}"
        )

    print("\nSuggested full runner setup:")
    print("broad grids: AC / chooser / 2w straddle / binary / KO / 35P / 40P / 45P")
    print("use run_resumable_bruteforce(..., run_name='broad') for the coarse pass")
    print("then refine_grid(best_positions) and run_resumable_bruteforce(..., run_name='refine')")