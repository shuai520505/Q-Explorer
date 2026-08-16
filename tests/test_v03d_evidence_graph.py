from src.v03d import EvidenceGraph


def test_v03d_evidence_graph_resolves_complete_trigger_path():
    graph = EvidenceGraph({
        "experiments": [{"experiment_id": "EXP_1", "run_id": "RUN"}],
        "evidence": [{"evidence_id": "E1", "run_id": "RUN", "decision": "COUNTEREXAMPLE", "experiment_ids": ["EXP_1"]}],
        "revisions": [{"revision_id": "REV_1", "triggering_evidence_ids": ["E1"], "new_hypothesis_id": "H.R1"}],
    })
    assert graph.get_run("missing")["status"] == "MISSING_LINK"
    path = graph.get_trigger_path("REV_1")
    assert path["status"] == "COMPLETE"
    assert path["paths"][0]["experiment_ids"] == ["EXP_1"]
