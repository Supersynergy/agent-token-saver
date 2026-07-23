"""ABBA counter-bias ordering for provider A/B tests.

Given results from provider A and B, return ABBA-ordered trial sequence
(A, B, B, A) so order-bias (warmup, fatigue, drift) cancels symmetrically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List, Tuple

Trial = Tuple[str, float]  # (provider, metric)


@dataclass
class ABBAPlan:
    trials: List[Trial]
    order: str  # "ABBA" or "BAAB"

    def pairs(self) -> List[Tuple[Trial, Trial]]:
        """Return consecutive (A, B) or (B, A) pairs for analysis."""
        t = self.trials
        return [(t[i], t[i + 1]) for i in range(0, len(t) - 1, 2)]


def abba_order(
    run_a: Callable[[], float],
    run_b: Callable[[], float],
    n_rounds: int = 1,
) -> ABBAPlan:
    """Execute runs in ABBA order: A, B, B, A per round."""
    if n_rounds < 1:
        raise ValueError("n_rounds must be >= 1")
    trials: List[Trial] = []
    for _ in range(n_rounds):
        trials.append(("A", run_a()))
        trials.append(("B", run_b()))
        trials.append(("B", run_b()))
        trials.append(("A", run_a()))
    return ABBAPlan(trials=trials, order="ABBA")


def abba_mean_diff(plan: ABBAPlan) -> float:
    """Mean(A) - Mean(B) over the ABBA plan, symmetric weight."""
    a_vals = [m for p, m in plan.trials if p == "A"]
    b_vals = [m for p, m in plan.trials if p == "B"]
    if not a_vals or not b_vals:
        return 0.0
    return sum(a_vals) / len(a_vals) - sum(b_vals) / len(b_vals)
