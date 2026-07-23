"""Tests for ABBA counter-bias ordering.

Oracle: ABBA plan has symmetric A/B counts + abba_mean_diff cancels constant offset.
"""

from scripts.abba import ABBAPlan, abba_mean_diff, abba_order


def test_abba_order_produces_symmetric_sequence():
    plan = abba_order(lambda: 1.0, lambda: 2.0, n_rounds=1)
    assert plan.order == "ABBA"
    assert plan.trials == [("A", 1.0), ("B", 2.0), ("B", 2.0), ("A", 1.0)]
    assert len(plan.pairs()) == 2


def test_abba_cancels_constant_offset():
    # A always 10, B always 12 -> diff = -2 regardless of order bias
    plan = abba_order(lambda: 10.0, lambda: 12.0, n_rounds=2)
    diff = abba_mean_diff(plan)
    assert abs(diff - (-2.0)) < 1e-9


def test_abba_rejects_zero_rounds():
    try:
        abba_order(lambda: 1.0, lambda: 2.0, n_rounds=0)
        assert False, "should raise"
    except ValueError:
        pass


def test_abba_n_rounds_doubles_trials():
    plan1 = abba_order(lambda: 1.0, lambda: 2.0, n_rounds=1)
    plan3 = abba_order(lambda: 1.0, lambda: 2.0, n_rounds=3)
    assert len(plan1.trials) == 4
    assert len(plan3.trials) == 12
    # symmetric: half A, half B
    a_count = sum(1 for p, _ in plan3.trials if p == "A")
    b_count = sum(1 for p, _ in plan3.trials if p == "B")
    assert a_count == b_count == 6
