from src.research import ExperimentBudget


def test_equal_frozen_budgets_have_equal_total_capacity():
    budgets = {name: ExperimentBudget(20) for name in ("active_agent", "random", "no_intervention", "fixed")}
    for budget in budgets.values():
        for round_id in range(1, 11):
            budget.consume(f"ACT_{round_id:06d}", 2, round_id)
    assert {budget.spent for budget in budgets.values()} == {20}
    assert {budget.remaining for budget in budgets.values()} == {0}

