from src.v03d import EvidenceGraph
from src.v03 import TaskSuite
from src.v04 import BoundaryEstimator, BoundarySignature, audit_boundary_run


def _reference():
    return BoundarySignature("REF", "N0", True, (2, 3), 2.5, "RING_WORSE", 1.0, 0.1, (), (), (), "RING_BETTER", "H")


def test_process_validity_requires_outcome_and_complete_chain():
    boundary_task = next(task for task in TaskSuite("configs/frozen_v03_tasks.yaml").tasks if task.task_id == "TASK_F01")
    run = {"run_id": "R", "strategy": "llm", "noise_level_id": "N1", "budget_spent": 16,
           "validated_judgment": {"validated": True}, "transfer_hypothesis_id": "H"}
    records = {
        "runs": [run],
        "actions": [{"run_id": "R", "round": 1, "action_id": "A", "action_type": "BOUNDARY_PROBE", "condition_id": "F1L"}],
        "experiments": [], "evidence": [], "hypotheses": [], "revisions": [],
    }
    row = audit_boundary_run(EvidenceGraph(records), run, boundary_task, BoundaryEstimator(0.05, 0.2), _reference(), 1.0)
    assert row["validated_original"] is True
    assert row["scientifically_validated"] is False
    assert row["complete_boundary_probe_chain"] is False
