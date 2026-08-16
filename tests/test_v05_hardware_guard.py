import pytest

from src.v05_gate0 import HardwareExecutionForbidden, HardwareExecutionGuard


def test_v05_hardware_guard_blocks_every_submission():
    guard = HardwareExecutionGuard()
    guard.assert_audit_mode()
    with pytest.raises(HardwareExecutionForbidden, match="REAL_HARDWARE_EXECUTION_BLOCKED_BY_GATE0"):
        guard.forbid_submission()
