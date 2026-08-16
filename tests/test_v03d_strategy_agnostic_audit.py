from tests.test_v03d_competing_design_validity import valid_case
from src.v03d import audit_competing_run


def test_v03d_same_evidence_gets_same_validity_for_each_strategy():
    graph, llm_run, task = valid_case("llm")
    rule_run = dict(llm_run, strategy="rule_based")
    llm = audit_competing_run(graph, llm_run, task)
    rule = audit_competing_run(graph, rule_run, task)
    fields = ("scientific_design_valid", "scientifically_validated", "scientific_control_score", "audit_status")
    assert {field: llm[field] for field in fields} == {field: rule[field] for field in fields}
