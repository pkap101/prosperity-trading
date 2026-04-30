"""
Round 5 Manual Trading Optimizer

Calculates optimal percentage allocations based on expected returns,
accounting for quadratic fee structure.

Fee formula: fee = (percentage/100)² × budget
Optimal allocation (unconstrained): w* = expected_return / 2
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional

BUDGET = 1_000_000

# =============================================================================
# CONFIGURATION - Edit these values to test different scenarios
# =============================================================================

@dataclass
class Product:
    name: str
    direction: str  # "BUY", "SELL", or "SKIP"
    expected_return: float  # As decimal (0.20 = 20%)
    low_estimate: Optional[float] = None  # For range analysis
    high_estimate: Optional[float] = None  # For range analysis

    def __post_init__(self):
        if self.low_estimate is None:
            self.low_estimate = self.expected_return * 0.7
        if self.high_estimate is None:
            self.high_estimate = self.expected_return * 1.3

# Define products with expected returns (EDIT THESE)
PRODUCTS = [
    # Format: Product(name, direction, expected_return, low_estimate, high_estimate)

    # Strong bullish
    Product("Thermalite Core", "BUY", 0.29, 0.20, 0.30),
    Product("Sulfur Reactor", "BUY", 0.17, 0.10, 0.22),  # Disagreement: you say 22%, I say 10-15%
    Product("Magma Ink", "BUY", 0.18, 0.12, 0.22),

    # Strong bearish
    Product("Lava Cake", "SELL", 0.40, 0.35, 0.50),
    Product("Pyroflex Cells", "SELL", 0.21, 0.15, 0.25),
    Product("Obsidian Cutlery", "BUY", 0.10, 0.10, 0.20),

    # Uncertain bearish
    Product("Ashes of Phoenix", "SELL", 0.08, -0.05, 0.10),  # Note: negative low = could go wrong way

    # Skip (no edge)
    Product("Volcanic Incense", "SKIP", 0.00, -0.15, 0.10),
    Product("Scoria Paste", "SKIP", 0.00, -0.10, 0.10),
]


# =============================================================================
# OPTIMIZER FUNCTIONS
# =============================================================================

def calculate_fee(allocation_pct: float) -> float:
    """Calculate fee for a given allocation percentage."""
    return (allocation_pct / 100) ** 2 * BUDGET


def optimal_allocation_unconstrained(expected_return: float) -> float:
    """
    Calculate theoretically optimal allocation (unconstrained).

    Derivation:
    - Profit = allocation * expected_return * budget - fee
    - Profit = w * r * B - (w)² * B
    - d(Profit)/dw = r * B - 2w * B = 0
    - w* = r / 2

    Returns allocation as percentage (0-100).
    """
    if expected_return <= 0:
        return 0.0
    return (expected_return / 2) * 100  # Convert to percentage


def calculate_expected_profit(allocation_pct: float, expected_return: float) -> float:
    """Calculate expected profit for a given allocation and return."""
    if allocation_pct <= 0:
        return 0.0
    investment = (allocation_pct / 100) * BUDGET
    gross_profit = investment * expected_return
    fee = calculate_fee(allocation_pct)
    return gross_profit - fee


def optimize_single_product(product: Product) -> dict:
    """Calculate optimal allocation for a single product."""
    if product.direction == "SKIP" or product.expected_return <= 0:
        return {
            "name": product.name,
            "direction": product.direction,
            "expected_return": product.expected_return,
            "optimal_allocation": 0,
            "fee": 0,
            "expected_profit": 0,
            "profit_if_correct": 0,
        }

    # Unconstrained optimal
    optimal_pct = optimal_allocation_unconstrained(product.expected_return)

    # Round to integer (constraint)
    optimal_pct_int = round(optimal_pct)

    # Calculate metrics
    fee = calculate_fee(optimal_pct_int)
    expected_profit = calculate_expected_profit(optimal_pct_int, product.expected_return)

    return {
        "name": product.name,
        "direction": product.direction,
        "expected_return": product.expected_return,
        "optimal_allocation": optimal_pct_int,
        "fee": fee,
        "expected_profit": expected_profit,
    }


def optimize_portfolio(products: list[Product], max_total_allocation: float = 100.0) -> list[dict]:
    """
    Optimize allocation across all products with total constraint.

    If sum of optimal allocations exceeds max_total_allocation,
    scale down proportionally.
    """
    results = []

    # First pass: get unconstrained optimal allocations
    for product in products:
        result = optimize_single_product(product)
        results.append(result)

    # Check total allocation
    total_allocation = sum(r["optimal_allocation"] for r in results)

    if total_allocation > max_total_allocation:
        # Scale down proportionally
        scale_factor = max_total_allocation / total_allocation
        for result in results:
            result["optimal_allocation"] = round(result["optimal_allocation"] * scale_factor)
            result["fee"] = calculate_fee(result["optimal_allocation"])
            result["expected_profit"] = calculate_expected_profit(
                result["optimal_allocation"],
                result["expected_return"]
            )

    return results


def run_scenario_analysis(products: list[Product]) -> dict:
    """Run analysis for low, mid, and high scenarios."""
    scenarios = {}

    # Mid scenario (base case)
    scenarios["mid"] = optimize_portfolio(products)

    # Low scenario
    low_products = [
        Product(p.name, p.direction, p.low_estimate, p.low_estimate, p.high_estimate)
        for p in products
    ]
    scenarios["low"] = optimize_portfolio(low_products)

    # High scenario
    high_products = [
        Product(p.name, p.direction, p.high_estimate, p.low_estimate, p.high_estimate)
        for p in products
    ]
    scenarios["high"] = optimize_portfolio(high_products)

    return scenarios


def print_results(results: list[dict], title: str = "Optimal Allocations"):
    """Pretty print optimization results."""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)

    print(f"\n{'Product':<22} {'Dir':<6} {'E[R]':>8} {'Alloc%':>8} {'Fee':>12} {'E[Profit]':>12}")
    print("-" * 80)

    total_allocation = 0
    total_fee = 0
    total_profit = 0

    # Sort by expected profit descending
    sorted_results = sorted(results, key=lambda x: x["expected_profit"], reverse=True)

    for r in sorted_results:
        if r["optimal_allocation"] > 0:
            print(f"{r['name']:<22} {r['direction']:<6} {r['expected_return']:>7.1%} "
                  f"{r['optimal_allocation']:>7}% {r['fee']:>11,.0f} {r['expected_profit']:>11,.0f}")
            total_allocation += r["optimal_allocation"]
            total_fee += r["fee"]
            total_profit += r["expected_profit"]

    print("-" * 80)
    print(f"{'TOTAL':<22} {'':<6} {'':<8} {total_allocation:>7}% {total_fee:>11,.0f} {total_profit:>11,.0f}")
    print(f"\nRemaining budget: {100 - total_allocation}%")
    print(f"Budget used: {total_allocation * BUDGET / 100:,.0f} / {BUDGET:,}")


def print_scenario_comparison(scenarios: dict):
    """Print comparison across scenarios."""
    print("\n" + "=" * 80)
    print(" SCENARIO COMPARISON")
    print("=" * 80)

    print(f"\n{'Scenario':<12} {'Total Alloc':>12} {'Total Fee':>12} {'E[Profit]':>12}")
    print("-" * 50)

    for scenario_name, results in scenarios.items():
        total_alloc = sum(r["optimal_allocation"] for r in results)
        total_fee = sum(r["fee"] for r in results)
        total_profit = sum(r["expected_profit"] for r in results)
        print(f"{scenario_name.upper():<12} {total_alloc:>11}% {total_fee:>11,.0f} {total_profit:>11,.0f}")


def sensitivity_analysis(product_name: str, return_range: tuple = (0.05, 0.50), steps: int = 10):
    """Show how optimal allocation changes with expected return for a single product."""
    print(f"\n{'=' * 60}")
    print(f" SENSITIVITY: {product_name}")
    print(f"{'=' * 60}")

    print(f"\n{'E[Return]':>10} {'Optimal%':>10} {'Fee':>12} {'E[Profit]':>12} {'ROI':>10}")
    print("-" * 60)

    for r in np.linspace(return_range[0], return_range[1], steps):
        opt_pct = round(optimal_allocation_unconstrained(r))
        fee = calculate_fee(opt_pct)
        profit = calculate_expected_profit(opt_pct, r)
        roi = profit / (opt_pct * BUDGET / 100) * 100 if opt_pct > 0 else 0
        print(f"{r:>9.1%} {opt_pct:>9}% {fee:>11,.0f} {profit:>11,.0f} {roi:>9.1f}%")


def what_if_analysis(products: list[Product], overrides: dict[str, float]):
    """
    Run analysis with specific return overrides.

    overrides: dict mapping product name to new expected return
    Example: {"Lava Cake": 0.50, "Thermalite Core": 0.30}
    """
    modified_products = []
    for p in products:
        if p.name in overrides:
            modified_products.append(Product(
                p.name, p.direction, overrides[p.name], p.low_estimate, p.high_estimate
            ))
        else:
            modified_products.append(p)

    results = optimize_portfolio(modified_products)
    print_results(results, f"What-If Analysis: {overrides}")
    return results


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("\n" + "#" * 80)
    print(" ROUND 5 MANUAL TRADING OPTIMIZER")
    print("#" * 80)

    # Show current configuration
    print("\n" + "=" * 80)
    print(" CURRENT ESTIMATES")
    print("=" * 80)
    print(f"\n{'Product':<22} {'Direction':<6} {'Low':>8} {'Mid':>8} {'High':>8}")
    print("-" * 60)
    for p in PRODUCTS:
        print(f"{p.name:<22} {p.direction:<6} {p.low_estimate:>7.0%} {p.expected_return:>7.0%} {p.high_estimate:>7.0%}")

    # Base case optimization
    results = optimize_portfolio(PRODUCTS)
    print_results(results, "BASE CASE (Mid Estimates)")

    # Scenario analysis
    scenarios = run_scenario_analysis(PRODUCTS)
    print_scenario_comparison(scenarios)

    # Sensitivity for key products
    print("\n" + "#" * 80)
    print(" SENSITIVITY ANALYSIS")
    print("#" * 80)
    sensitivity_analysis("Lava Cake", (0.30, 0.60), 7)
    sensitivity_analysis("Thermalite Core", (0.15, 0.35), 5)

    # Example what-if
    print("\n" + "#" * 80)
    print(" WHAT-IF SCENARIOS")
    print("#" * 80)

    # What if Lava Cake is as bad as Quantum Coffee?
    what_if_analysis(PRODUCTS, {"Lava Cake": 0.55})

    # What if we're more conservative on Sulfur Reactor?
    what_if_analysis(PRODUCTS, {"Sulfur Reactor": 0.12})
