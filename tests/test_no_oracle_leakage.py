import json

from src.v03 import TaskSuite


def test_public_task_view_excludes_evaluation_fields_and_heldout_conditions():
    for task in TaskSuite("configs/frozen_v03_tasks.yaml").tasks:
        text = json.dumps(task.public_view()).lower()
        assert "task_type" not in text
        assert "evaluation_metadata" not in text
        assert not set(task.held_out_set) & {item["condition_id"] for item in task.public_view()["experiment_pool"]}


def test_prompt_contains_no_evaluation_only_labels():
    prompt = open("prompts/research_agent_v03.txt", encoding="utf-8").read().lower()
    for banned in ("oracle", "hidden relationship", "expected finding", "baseline result", "held-out labels"):
        assert banned not in prompt

