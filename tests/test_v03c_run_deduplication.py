import pytest

from src.v03c import deduplicate_runs


def test_duplicate_run_key_is_rejected():
    row = {"run_id": "R", "task_id": "T", "config_hash": "C"}
    with pytest.raises(ValueError, match="Duplicate"):
        deduplicate_runs([row, dict(row)])
