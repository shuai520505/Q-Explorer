from src.v03 import TaskSuite, diagnose_scientific_failure_modes


def test_competing_task_requires_discriminative_control_after_two_actions():
    task = next(task for task in TaskSuite("configs/frozen_v03_tasks.yaml").tasks if task.competing_hypotheses)
    action = {"action_type": "CHANGE_INSTANCE", "reason": "more data", "information_goal": "coverage"}
    assert "FAILED_TO_DISCRIMINATE" in diagnose_scientific_failure_modes(action, [], task, [{}, {}])

