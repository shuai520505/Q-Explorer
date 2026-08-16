from copy import deepcopy

from src.v03d import EvidenceGraph, audit_scope_revision


def test_v03d_scope_audit_does_not_mutate_input_history():
    records = {"revisions": [{"run_id": "R", "task_id": "T", "round": 1, "parent_hypothesis_id": "H", "new_claim": "x", "triggering_evidence_ids": []}]}
    before = deepcopy(records)
    graph = EvidenceGraph(records)
    audit_scope_revision(graph, graph.records["revisions"][0])
    assert records == before
