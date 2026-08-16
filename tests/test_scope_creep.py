from src.v03 import TaskSuite, diagnose_scientific_failure_modes


def test_scope_outside_task_qubits_is_flagged():
    task = TaskSuite("configs/frozen_v03_tasks.yaml").tasks[0]
    action = {"hypothesis_proposal": {"scope": {"num_qubits": [4, 10]}}}
    assert "HYPOTHESIS_SCOPE_CREEP" in diagnose_scientific_failure_modes(action, [], task, [])

