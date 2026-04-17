#!/usr/bin/env python3
"""
Backtest comparison script for Round 1 trader strategies.

Runs all copy1-*.py traders through the backtester and aggregates results
into a summary CSV for easy comparison.

Usage:
    python scripts/backtest_comparison.py
    python scripts/backtest_comparison.py --round 1
    python scripts/backtest_comparison.py --traders copy1-1.py copy1-2.py
"""

import subprocess
import re
import csv
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Paths
REPO_ROOT = Path(__file__).parent.parent
SRC_DIR = REPO_ROOT / "src" / "round1"
RESULTS_DIR = REPO_ROOT / "backtests" / "comparison"
VENV_ACTIVATE = REPO_ROOT / ".venv" / "bin" / "activate"

# Products for Round 1
ROUND1_PRODUCTS = ["ASH_COATED_OSMIUM", "INTARIAN_PEPPER_ROOT"]


def find_traders(pattern: str = "copy1-*.py") -> list[Path]:
    """Find all trader files matching the pattern."""
    traders = sorted(SRC_DIR.glob(pattern))
    return traders


def run_backtest(trader_path: Path, round_num: int) -> tuple[str, int]:
    """Run prosperity3bt on a trader file and return (stdout, return_code)."""
    cmd = f"source {VENV_ACTIVATE} && prosperity3bt {trader_path} {round_num} 2>&1"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, executable="/bin/bash")
    return result.stdout, result.returncode


def parse_backtest_output(output: str, products: list[str]) -> list[dict]:
    """
    Parse backtest output and extract per-day results.

    Returns a list of dicts, one per day:
        {"day": int, "product_pnl": {product: pnl}, "total": int}
    """
    results = []
    current_day = None
    current_result = None

    lines = output.split("\n")

    for line in lines:
        # Stop parsing when we hit the summary section
        if "Profit summary:" in line:
            break

        # Match day header: "Backtesting ... on round X day Y"
        day_match = re.search(r"round (\d+) day (-?\d+)", line)
        if day_match:
            if current_result is not None:
                results.append(current_result)
            current_day = int(day_match.group(2))
            current_result = {"day": current_day, "product_pnl": {}, "total": 0}
            continue

        # Match product PnL: "PRODUCT_NAME: 1,234" or "PRODUCT_NAME: -1,234"
        for product in products:
            pnl_match = re.match(rf"^{re.escape(product)}:\s*([-\d,]+)", line)
            if pnl_match and current_result is not None:
                pnl_str = pnl_match.group(1).replace(",", "")
                current_result["product_pnl"][product] = int(pnl_str)
                break

        # Match total: "Total profit: 1,234"
        total_match = re.match(r"^Total profit:\s*([-\d,]+)", line)
        if total_match and current_result is not None:
            total_str = total_match.group(1).replace(",", "")
            current_result["total"] = int(total_str)

    # Don't forget the last day
    if current_result is not None and current_result["total"] != 0:
        results.append(current_result)

    return results


def run_all_backtests(
    traders: list[Path],
    round_num: int,
    products: list[str]
) -> tuple[list[dict], dict[str, str]]:
    """
    Run backtests for all traders and collect results.

    Returns:
        - List of result rows for CSV
        - Dict of trader_name -> raw_output for logging
    """
    all_results = []
    raw_outputs = {}

    for trader_path in traders:
        trader_name = trader_path.stem
        print(f"Running {trader_name}...", end=" ", flush=True)

        output, return_code = run_backtest(trader_path, round_num)
        raw_outputs[trader_name] = output

        if return_code != 0 or "Traceback" in output:
            print("FAILED")
            # Add error row
            all_results.append({
                "trader": trader_name,
                "round": round_num,
                "day": "ERROR",
                **{p: "ERROR" for p in products},
                "total": "ERROR",
                "error": output[:200] if "Traceback" in output else "Unknown error"
            })
            continue

        day_results = parse_backtest_output(output, products)

        if not day_results:
            print("NO DATA")
            continue

        # Calculate totals across all days
        total_by_product = {p: 0 for p in products}
        grand_total = 0

        for dr in day_results:
            # Add per-day row
            row = {
                "trader": trader_name,
                "round": round_num,
                "day": dr["day"],
                **{p: dr["product_pnl"].get(p, 0) for p in products},
                "total": dr["total"]
            }
            all_results.append(row)

            # Accumulate totals
            for p in products:
                total_by_product[p] += dr["product_pnl"].get(p, 0)
            grand_total += dr["total"]

        # Add summary row for this trader
        all_results.append({
            "trader": trader_name,
            "round": round_num,
            "day": "TOTAL",
            **total_by_product,
            "total": grand_total
        })

        print(f"OK (total: {grand_total:,})")

    return all_results, raw_outputs


def write_results(
    results: list[dict],
    raw_outputs: dict[str, str],
    round_num: int,
    products: list[str]
):
    """Write results to CSV and raw logs."""
    # Ensure output directory exists
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    raw_dir = RESULTS_DIR / "raw"
    raw_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Write summary CSV
    csv_path = RESULTS_DIR / f"round{round_num}_summary_{timestamp}.csv"
    fieldnames = ["trader", "round", "day"] + products + ["total"]

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    print(f"\nSummary written to: {csv_path}")

    # Write raw outputs
    for trader_name, output in raw_outputs.items():
        log_path = raw_dir / f"{trader_name}_round{round_num}_{timestamp}.log"
        with open(log_path, "w") as f:
            f.write(output)

    print(f"Raw logs written to: {raw_dir}/")

    # Also write a "latest" symlink-style copy for easy access
    latest_csv = RESULTS_DIR / f"round{round_num}_latest.csv"
    with open(latest_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    print(f"Latest copy: {latest_csv}")


def print_summary_table(results: list[dict], products: list[str]):
    """Print a summary table of TOTAL rows only."""
    totals = [r for r in results if r.get("day") == "TOTAL"]

    if not totals:
        return

    # Sort by total PnL descending
    totals.sort(key=lambda x: x.get("total", 0) if isinstance(x.get("total"), int) else 0, reverse=True)

    print("\n" + "=" * 70)
    print("SUMMARY (sorted by total PnL)")
    print("=" * 70)

    # Header
    header = f"{'Trader':<12}"
    for p in products:
        short_name = p[:8]  # Truncate product names
        header += f" {short_name:>10}"
    header += f" {'Total':>12}"
    print(header)
    print("-" * 70)

    # Rows
    for row in totals:
        line = f"{row['trader']:<12}"
        for p in products:
            val = row.get(p, 0)
            if isinstance(val, int):
                line += f" {val:>10,}"
            else:
                line += f" {str(val):>10}"
        total = row.get("total", 0)
        if isinstance(total, int):
            line += f" {total:>12,}"
        else:
            line += f" {str(total):>12}"
        print(line)

    print("=" * 70)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run backtest comparison for multiple traders")
    parser.add_argument("--round", type=int, default=1, help="Round number to backtest (default: 1)")
    parser.add_argument("--traders", nargs="*", help="Specific trader files to test (default: all copy1-*.py)")
    args = parser.parse_args()

    round_num = args.round

    # Determine products based on round
    if round_num == 0:
        products = ["EMERALDS", "TOMATOES"]
    elif round_num == 1:
        products = ROUND1_PRODUCTS
    else:
        print(f"Warning: Unknown products for round {round_num}, using Round 1 products")
        products = ROUND1_PRODUCTS

    # Find traders
    if args.traders:
        traders = [SRC_DIR / t for t in args.traders]
        # Verify they exist
        for t in traders:
            if not t.exists():
                print(f"Error: Trader file not found: {t}")
                sys.exit(1)
    else:
        traders = find_traders("copy1-*.py")

    if not traders:
        print("No trader files found!")
        sys.exit(1)

    print(f"Found {len(traders)} traders to test on round {round_num}")
    print(f"Products: {', '.join(products)}")
    print("-" * 50)

    # Run all backtests
    results, raw_outputs = run_all_backtests(traders, round_num, products)

    # Write results
    write_results(results, raw_outputs, round_num, products)

    # Print summary table
    print_summary_table(results, products)


if __name__ == "__main__":
    main()
