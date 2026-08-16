import pytest

from src.v03 import TaskSuite


def test_task_suite_hash_detects_mutation(tmp_path):
    path = tmp_path / "tasks.yaml"
    path.write_bytes(open("configs/frozen_v03_tasks.yaml", "rb").read())
    suite = TaskSuite(path)
    assert suite.frozen and len(suite.sha256) == 64
    path.write_text(path.read_text(encoding="utf-8") + "\n# changed", encoding="utf-8")
    with pytest.raises(RuntimeError, match="changed"):
        suite.verify_unchanged()

