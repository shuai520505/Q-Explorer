from src.v03 import TaskSuite


def test_all_strategies_receive_each_tasks_frozen_vqe_budget():
    strategies = ("llm", "rule_based", "random", "no_intervention", "fixed")
    allocation = {(task.task_id, strategy): task.budget for task in TaskSuite("configs/frozen_v03_tasks.yaml").tasks for strategy in strategies}
    for task in TaskSuite("configs/frozen_v03_tasks.yaml").tasks:
        assert {allocation[(task.task_id, strategy)] for strategy in strategies} == {task.budget}

