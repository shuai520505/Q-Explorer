from src.v03 import TaskSuite, diagnose_scientific_failure_modes


def test_supported_claim_before_fact_criteria_is_flagged():
    task = TaskSuite("configs/frozen_v03_tasks.yaml").tasks[0]
    assert "PREMATURE_CONCLUSION" in diagnose_scientific_failure_modes({"claimed_status": "SUPPORTED"}, [], task, [])

