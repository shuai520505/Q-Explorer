from src.v03c import V03CProtocol


def test_v03c_task_suite_hash_is_unchanged():
    protocol = V03CProtocol.load("configs/frozen_v03c.yaml")
    checks = protocol.verify_workspace(".")
    assert checks["task_suite"] and checks["task_ids"] and checks["budgets"]
