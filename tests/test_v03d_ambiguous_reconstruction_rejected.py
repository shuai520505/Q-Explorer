from src.v03d import EvidenceGraph, audit_scope_revision


def test_v03d_multiple_prior_candidates_are_not_hand_selected():
    graph = EvidenceGraph({
        "experiments": [
            {"experiment_id": "EXP_1", "run_id": "RUN"},
            {"experiment_id": "EXP_2", "run_id": "RUN"},
        ],
        "evidence": [
            {"evidence_id": "E1", "run_id": "RUN", "task_id": "TASK_G01", "hypothesis_id": "HG01", "round": 1, "decision": "WEAKEN", "experiment_ids": ["EXP_1"]},
            {"evidence_id": "E2", "run_id": "RUN", "task_id": "TASK_G01", "hypothesis_id": "HG01", "round": 2, "decision": "COUNTEREXAMPLE", "experiment_ids": ["EXP_2"]},
        ],
    })
    revision = {"run_id": "RUN", "task_id": "TASK_G01", "round": 3, "parent_hypothesis_id": "HG01", "new_claim": "conditional", "scope_change": "narrow", "triggering_evidence_ids": []}
    result = audit_scope_revision(graph, revision)
    assert result["eligible_candidate_count"] == 2
    assert result["audit_status"] == "INDIRECTLY_SUPPORTED"
