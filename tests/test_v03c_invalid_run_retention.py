from src.v03c import merge_replication_runs


def test_invalid_run_remains_in_merged_denominator():
    invalid = {"run_id": "BAD", "task_id": "TASK_D01", "config_hash": "C", "final_judgment": "INVALID_ACTION"}
    valid = {"run_id": "GOOD", "task_id": "TASK_D01", "config_hash": "C", "final_judgment": "SUPPORT"}
    merged = merge_replication_runs([invalid], [valid], {"TASK_D01"})
    assert len(merged) == 2
    assert any(row["final_judgment"] == "INVALID_ACTION" for row in merged)
