"""
Round 2 manual challenge optimizer: Invest & Expand.

This round is not a pure deterministic optimization problem because the
"Speed" pillar is rank-based across all players. Without a model for what
other players do with Speed, there is no single exact optimum.

This script handles that explicitly:
1. It defines a few plausible opponent-speed scenarios.
2. It computes the expected Speed multiplier for each of our candidate
   speed allocations under each scenario.
3. It brute-forces all integer allocations (Research, Scale, Speed)
   with total <= 100 and reports:
   - scenario-specific optima,
   - a robust average optimum,
   - a conservative maximin optimum.

Assumptions used here:
- Percentages are integer allocations from 0 to 100.
- Budget used is 50_000 * total_percent / 100 = 500 * total_percent.
- Expected speed multiplier under a scenario distribution p(s) is
  0.9 - 0.8 * P(opponent_speed > our_speed).
  This matches the prompt's rank rule and treats ties as sharing rank.

Usage:
    python3 src/round2/manual2.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List


TOTAL_BUDGET = 50_000
COST_PER_PERCENT = TOTAL_BUDGET / 100


def research(x: int) -> float:
    return 200_000 * math.log(1 + x) / math.log(101)


def scale(x: int) -> float:
    return 7 * x / 100


def budget_used(total_percent: int) -> float:
    return COST_PER_PERCENT * total_percent


def pnl(research_pct: int, scale_pct: int, speed_pct: int, speed_multiplier: float) -> float:
    gross = research(research_pct) * scale(scale_pct) * speed_multiplier
    return gross - budget_used(research_pct + scale_pct + speed_pct)


def normalize(weights: List[float]) -> List[float]:
    total = sum(weights)
    if total <= 0:
        raise ValueError("Scenario weights must sum to a positive value")
    return [w / total for w in weights]


def uniform_pmf() -> List[float]:
    return [1 / 101] * 101


def beta_like_pmf(alpha: float, beta: float) -> List[float]:
    weights = []
    for x in range(101):
        z = (x + 0.5) / 101
        weight = (z ** (alpha - 1)) * ((1 - z) ** (beta - 1))
        weights.append(weight)
    return normalize(weights)


def focal_points_pmf() -> List[float]:
    # Round-number clustering is common in simple manual challenges.
    pmf = [0.0] * 101
    focal = {
        0: 0.12,
        5: 0.03,
        10: 0.09,
        15: 0.02,
        20: 0.09,
        25: 0.04,
        30: 0.09,
        33: 0.02,
        40: 0.07,
        50: 0.14,
        60: 0.07,
        70: 0.08,
        80: 0.06,
        90: 0.05,
        100: 0.03,
    }
    for speed, weight in focal.items():
        pmf[speed] += weight
    remainder = 1 - sum(pmf)
    for i in range(101):
        pmf[i] += remainder / 101
    return pmf


def barbell_pmf() -> List[float]:
    low = beta_like_pmf(1.5, 4.0)
    high = beta_like_pmf(4.0, 1.6)
    return [0.60 * l + 0.40 * h for l, h in zip(low, high)]


SCENARIOS: Dict[str, List[float]] = {
    "uniform": uniform_pmf(),
    "low_speed": beta_like_pmf(1.6, 4.4),
    "high_speed": beta_like_pmf(4.2, 1.7),
    "focal_points": focal_points_pmf(),
    "barbell": barbell_pmf(),
}


def expected_speed_multiplier(speed_pct: int, opponent_speed_pmf: List[float]) -> float:
    prob_strictly_higher = sum(opponent_speed_pmf[s] for s in range(speed_pct + 1, 101))
    return 0.9 - 0.8 * prob_strictly_higher


@dataclass(frozen=True)
class Candidate:
    research_pct: int
    scale_pct: int
    speed_pct: int
    score: float


def brute_force_objective(score_fn: Callable[[int, int, int], float]) -> Candidate:
    best: Candidate | None = None
    for speed_pct in range(101):
        remaining = 100 - speed_pct
        for research_pct in range(remaining + 1):
            for scale_pct in range(remaining - research_pct + 1):
                score = score_fn(research_pct, scale_pct, speed_pct)
                candidate = Candidate(research_pct, scale_pct, speed_pct, score)
                if best is None or candidate.score > best.score:
                    best = candidate
    if best is None:
        raise RuntimeError("No feasible allocation found")
    return best


def scenario_best(opponent_speed_pmf: List[float]) -> Candidate:
    return brute_force_objective(
        lambda r, c, s: pnl(r, c, s, expected_speed_multiplier(s, opponent_speed_pmf))
    )


def robust_average_best(scenarios: Dict[str, List[float]]) -> Candidate:
    def score_fn(r: int, c: int, s: int) -> float:
        values = [pnl(r, c, s, expected_speed_multiplier(s, pmf)) for pmf in scenarios.values()]
        return sum(values) / len(values)

    return brute_force_objective(score_fn)


def robust_maximin_best(scenarios: Dict[str, List[float]]) -> Candidate:
    def score_fn(r: int, c: int, s: int) -> float:
        values = [pnl(r, c, s, expected_speed_multiplier(s, pmf)) for pmf in scenarios.values()]
        return min(values)

    return brute_force_objective(score_fn)


def describe_candidate(candidate: Candidate, scenarios: Dict[str, List[float]]) -> None:
    print(
        f"Research={candidate.research_pct}%  "
        f"Scale={candidate.scale_pct}%  "
        f"Speed={candidate.speed_pct}%"
    )
    print(f"Total budget used: {candidate.research_pct + candidate.scale_pct + candidate.speed_pct}%")
    print(f"Budget used (XIRECs): {budget_used(candidate.research_pct + candidate.scale_pct + candidate.speed_pct):,.0f}")
    print(f"Research outcome: {research(candidate.research_pct):,.2f}")
    print(f"Scale outcome: {scale(candidate.scale_pct):.4f}")
    for name, pmf in scenarios.items():
        multiplier = expected_speed_multiplier(candidate.speed_pct, pmf)
        score = pnl(candidate.research_pct, candidate.scale_pct, candidate.speed_pct, multiplier)
        print(f"  {name:12s} speed_mult={multiplier:0.4f}  pnl={score:,.2f}")


def main() -> None:
    print("Round 2 manual optimizer")
    print("Assumption: integer percentages, explicit opponent-speed scenarios, exact brute force over allocations.\n")

    print("Scenario-specific best responses")
    print("-" * 72)
    for name, pmf in SCENARIOS.items():
        best = scenario_best(pmf)
        print(f"{name:12s}: R={best.research_pct:2d}  S={best.scale_pct:2d}  V={best.speed_pct:2d}  pnl={best.score:,.2f}")

    print("\nRobust average recommendation")
    print("-" * 72)
    avg_best = robust_average_best(SCENARIOS)
    describe_candidate(avg_best, SCENARIOS)

    print("\nConservative maximin recommendation")
    print("-" * 72)
    maximin_best = robust_maximin_best(SCENARIOS)
    describe_candidate(maximin_best, SCENARIOS)


if __name__ == "__main__":
    main()
