from src.v03 import TaskSuite
from src.v03c import V03CProtocol


def test_v03c_targets_exactly_three_frozen_tasks():
    protocol = V03CProtocol.load("configs/frozen_v03c.yaml")
    suite = TaskSuite("configs/frozen_v03_tasks.yaml")
    targets = {task.task_id: task.task_type for task in suite.tasks if task.task_id in protocol.data["target_task_ids"]}
    assert targets == {
        "TASK_D01": "COMPETING_EXPLANATIONS",
        "TASK_F01": "BOUNDARY_TRANSITION",
        "TASK_G01": "SCOPE_REVISION",
    }
