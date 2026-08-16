"""Hard stop for every real-hardware submission during Gate 0."""

from __future__ import annotations

from dataclasses import dataclass


class HardwareExecutionForbidden(RuntimeError):
    """Raised before any provider submission method can be reached."""


@dataclass(frozen=True)
class HardwareExecutionGuard:
    mode: str = "AUDIT"
    formal_hardware_research_jobs: int = 0
    formal_hardware_vqe_runs: int = 0

    def assert_audit_mode(self) -> None:
        if self.mode != "AUDIT":
            raise HardwareExecutionForbidden("HARDWARE_EXECUTION_MODE_MUST_BE_AUDIT")
        if self.formal_hardware_research_jobs or self.formal_hardware_vqe_runs:
            raise HardwareExecutionForbidden("GATE0_EXECUTION_COUNTER_NONZERO")

    def forbid_submission(self) -> None:
        raise HardwareExecutionForbidden("REAL_HARDWARE_EXECUTION_BLOCKED_BY_GATE0")
