from src.v03 import TaskSuite


def test_heldout_conditions_never_appear_in_initial_agent_pool():
    for task in TaskSuite("configs/frozen_v03_tasks.yaml").tasks:
        public_ids = {item["condition_id"] for item in task.public_view()["experiment_pool"]}
        assert public_ids <= set(task.exploration_set)

