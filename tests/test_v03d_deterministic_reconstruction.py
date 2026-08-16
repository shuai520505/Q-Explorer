import json

from src.v03d import EvidenceGraph, audit_scope_revision


def test_v03d_unique_prior_counterexample_is_deterministically_reconstructed():
    graph = EvidenceGraph({
        "experiments": [{"experiment_id": "EXP_1", "run_id": "RUN"}],
        "evidence": [{"evidence_id": "E1", "run_id": "RUN", "task_id": "TASK_G01", "hypothesis_id": "HG01", "round": 2, "decision": "COUNTEREXAMPLE", "experiment_ids": ["EXP_1"]}],
    })
    revision = {"run_id": "RUN", "task_id": "TASK_G01", "round": 3, "parent_hypothesis_id": "HG01", "new_hypothesis_id": "HG01.R1", "old_claim": "broad", "new_claim": "conditional within depth 1", "scope_change": "broad -> conditional", "triggering_evidence_ids": []}
    result = audit_scope_revision(graph, revision)
    assert result["audit_status"] == "DETERMINISTICALLY_RECONSTRUCTABLE"
    assert json.loads(result["reconstructed_evidence_ids"]) == ["E1"]
