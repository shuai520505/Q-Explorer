from src.v03c import merge_replication_runs


def test_existing_and_new_runs_are_tagged_and_merged():
    old = [{"run_id": "OLD", "task_id": "TASK_F01", "config_hash": "C"}]
    new = [{"run_id": "NEW", "task_id": "TASK_F01", "config_hash": "C"}]
    rows = merge_replication_runs(old, new, {"TASK_F01"})
    assert {row["source_run"] for row in rows} == {"v03b", "v03c"}
    assert len(rows) == 2
