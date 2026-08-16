import pytest

from src.v03d import AuditExecutionForbidden, AuditModeGuard


def test_v03d_audit_guard_forbids_all_new_scientific_execution():
    guard = AuditModeGuard()
    guard.assert_clean()
    with pytest.raises(AuditExecutionForbidden, match="LIVE_LLM_CALL_FORBIDDEN"):
        guard.forbid_live_llm_call()
    with pytest.raises(AuditExecutionForbidden, match="VQE_EXECUTION_FORBIDDEN"):
        guard.forbid_vqe_execution()
    with pytest.raises(AuditExecutionForbidden, match="NEW_RESEARCH_RUN_FORBIDDEN"):
        guard.forbid_research_run()
