import pytest

from src.research import BudgetExceeded, ExperimentBudget


def test_budget_records_before_cost_after_in_vqe_runs():
    budget = ExperimentBudget(5)
    entry = budget.consume("ACT_000001", 2, 1)
    assert entry == {"action_id": "ACT_000001", "round": 1, "budget_before": 5, "budget_cost": 2, "budget_after": 3}
    with pytest.raises(BudgetExceeded):
        budget.consume("ACT_000002", 4, 2)
    assert budget.remaining == 3


def test_budget_ledger_replay_detects_inconsistency():
    with pytest.raises(ValueError, match="inconsistent"):
        ExperimentBudget.from_ledger(5, [{"action_id": "A", "round": 1, "budget_before": 99, "budget_cost": 2, "budget_after": 3}])

