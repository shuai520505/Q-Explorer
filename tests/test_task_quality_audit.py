from src.v03 import TaskSuite


def test_quality_audit_covers_all_structures_and_is_not_trivially_two_runs():
    rows = TaskSuite("configs/frozen_v03_tasks.yaml").quality_audit()
    assert len(rows) == 8
    assert all(row["minimum_possible_resolution_runs"] > 2 for row in rows)
    assert any(row["requires_control"] for row in rows)
    assert any(row["requires_replication"] for row in rows)
    assert any(row["contains_competing_explanations"] for row in rows)

