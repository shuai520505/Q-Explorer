from tests.test_v03d_competing_design_validity import valid_case
from src.v03d import audit_competing_run


def test_v03d_scientifically_validated_requires_outcome_and_design():
    graph, run, task = valid_case()
    assert audit_competing_run(graph, run, task)["audit_status"] == "SCIENTIFICALLY_VALIDATED"
    graph.records["actions"][1]["action_type"] = "CHANGE_INSTANCE"
    invalid = audit_competing_run(graph, run, task)
    assert invalid["audit_status"] == "OUTCOME_VALIDATED_BUT_DESIGN_INVALID"
    assert "OUTCOME_RIGHT_FOR_WRONG_EXPERIMENTAL_REASON" in invalid["failure_reason"]
