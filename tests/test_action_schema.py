import pytest

from src.research import ActionValidationError, ResearchAction


def valid_payload():
    return {
        "action_id": "ACT_000001", "round": 1, "hypothesis_id": "H001",
        "action_type": "SEARCH_COUNTEREXAMPLE", "reason": "Distinguish topology dependence.",
        "experiment": {"hamiltonian_id": "HAM_ABC123", "depth": 2, "entanglement": "ring", "seed_group": [1, 2]},
        "controlled_variables": ["hamiltonian", "depth", "optimizer"],
        "changed_variables": ["entanglement"], "expected_outcome": "Error difference becomes measurable.",
        "falsification_condition": "Ring is not better than linear.", "information_goal": "Test the narrowed scope.",
        "revision_proposal": None,
    }


def test_action_round_trip_and_cost():
    action = ResearchAction.from_dict(valid_payload())
    assert action.to_dict() == valid_payload()
    assert action.budget_cost == 2


def test_unknown_action_type_is_rejected():
    payload = valid_payload() | {"action_type": "OPTIMIZE_ENERGY"}
    with pytest.raises(ActionValidationError):
        ResearchAction.from_dict(payload)
