"""Hard guards for the V0.3-D no-new-experiment audit mode."""

from __future__ import annotations

from dataclasses import dataclass


class AuditExecutionForbidden(RuntimeError):
    """Raised when an audit attempts a prohibited external/scientific execution."""


@dataclass(frozen=True)
class AuditModeGuard:
    audit_mode: bool = True
    new_live_llm_calls: int = 0
    new_aer_vqe_runs: int = 0
    new_research_runs: int = 0

    def forbid_live_llm_call(self) -> None:
        raise AuditExecutionForbidden("LIVE_LLM_CALL_FORBIDDEN")

    def forbid_vqe_execution(self) -> None:
        raise AuditExecutionForbidden("VQE_EXECUTION_FORBIDDEN")

    def forbid_research_run(self) -> None:
        raise AuditExecutionForbidden("NEW_RESEARCH_RUN_FORBIDDEN")

    def assert_clean(self) -> None:
        if not self.audit_mode:
            raise AuditExecutionForbidden("AUDIT_MODE_REQUIRED")
        if self.new_live_llm_calls or self.new_aer_vqe_runs or self.new_research_runs:
            raise AuditExecutionForbidden("AUDIT_EXECUTION_COUNTER_NONZERO")
