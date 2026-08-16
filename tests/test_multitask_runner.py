from src.v03 import TaskSuite, plan_conditions, select_rule_based_condition
import yaml


def test_each_strategy_plan_respects_task_budget_and_validation_tail():
    for task in TaskSuite("configs/frozen_v03_tasks.yaml").tasks:
        for strategy in ("rule_based", "random", "no_intervention", "fixed"):
            plan = plan_conditions(task, strategy, 17 if strategy == "random" else None)
            assert len(plan) * 2 == task.budget
            assert all(item.action_type == "VALIDATE_HYPOTHESIS" for item in plan[-2:])
            assert all(item.condition["condition_id"] in task.held_out_set for item in plan[-2:])


def test_seed_policy_can_pay_largest_task_budget():
    config = yaml.safe_load(open("configs/frozen_v03.yaml", encoding="utf-8"))
    largest = max(task.budget for task in TaskSuite("configs/frozen_v03_tasks.yaml").tasks)
    assert len(config["vqe"]["seeds"]) >= largest


def test_rule_based_selection_changes_after_counterexample():
    task = next(task for task in TaskSuite("configs/frozen_v03_tasks.yaml").tasks if task.task_type == "LOCAL_RULE_COUNTEREXAMPLE")
    prior = [{"condition_id": task.exploration_set[0]}]
    selected = select_rule_based_condition(task, 2, [{"decision": "COUNTEREXAMPLE"}], prior)
    assert selected.action_type == "SEARCH_COUNTEREXAMPLE"
    assert selected.condition["condition_id"] != task.exploration_set[0]
