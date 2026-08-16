from src.v03c import classify_failure_modes


def test_competing_failure_taxonomy_detects_missing_control_and_budget_exhaustion():
    run = {"budget": 16, "budget_spent": 16, "validated_judgment": {"validated": False}, "failure_modes": []}
    actions = [{"action_type": "CHANGE_INSTANCE", "reason": "Try another point", "information_goal": "More data", "failure_modes": [], "changed_variables": ["depth", "topology"]}]
    modes = classify_failure_modes(run, actions, [], "COMPETING_EXPLANATIONS")
    assert "FAILED_TO_IDENTIFY_COMPETING_EXPLANATIONS" in modes
    assert "FAILED_TO_CONTROL_CONFOUND" in modes
    assert "NON_DISCRIMINATIVE_EXPERIMENT" in modes
    assert "BUDGET_EXHAUSTED" in modes
