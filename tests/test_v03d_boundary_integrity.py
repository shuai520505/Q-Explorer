from src.v03d import EvidenceGraph, audit_boundary_run


def test_v03d_boundary_integrity_requires_probe_experiment_evidence_and_heldout():
    graph = EvidenceGraph({
        "actions": [{"run_id": "R", "action_id": "A", "action_type": "BOUNDARY_PROBE"}],
        "experiments": [
            {"run_id": "R", "action_id": "A", "experiment_id": "EXP", "status": "SUCCESS"},
            {"run_id": "R", "action_id": "H", "experiment_id": "HEX", "status": "SUCCESS"},
        ],
        "evidence": [
            {"run_id": "R", "action_id": "A", "evidence_id": "EV", "experiment_ids": ["EXP"], "held_out": False},
            {"run_id": "R", "action_id": "H", "evidence_id": "HEV", "experiment_ids": ["HEX"], "held_out": True},
        ],
    })
    run = {"run_id": "R", "validated_judgment": {"validated": True}}
    assert audit_boundary_run(graph, run)["audit_status"] == "PASS"
