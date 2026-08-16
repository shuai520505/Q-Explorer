import pytest

from src.v03 import ResearchTask, TaskSuite, TaskValidationError


def test_frozen_suite_has_eight_distinct_task_types():
    suite = TaskSuite("configs/frozen_v03_tasks.yaml")
    assert len(suite.tasks) == 8
    assert len({task.task_type for task in suite.tasks}) == 8


def test_heldout_overlap_is_rejected():
    task = TaskSuite("configs/frozen_v03_tasks.yaml").tasks[0]
    payload = task.to_dict()
    payload["held_out_set"] = list(payload["held_out_set"]) + [payload["exploration_set"][0]]
    with pytest.raises(TaskValidationError, match="disjoint"):
        ResearchTask.from_dict(payload)

