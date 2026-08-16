from src.v03 import TaskSuite, diagnose_scientific_failure_modes


def test_counterexample_requires_scientifically_responsive_action():
    task = TaskSuite("configs/frozen_v03_tasks.yaml").tasks[0]
    modes = diagnose_scientific_failure_modes({"action_type": "CHANGE_INSTANCE"}, [{"decision": "COUNTEREXAMPLE"}], task, [])
    assert "COUNTEREXAMPLE_IGNORED" in modes

