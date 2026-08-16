from src.v03d import classify_scope_run


def test_v03d_scope_run_classification_separates_outcome_from_attribution():
    run = {"final_judgment": "SUPPORT", "validated_judgment": {"validated": True}}
    assert classify_scope_run(run, [{"audit_status": "STRICTLY_SUPPORTED"}]) == "VALIDATED_WITH_STRICT_REVISION"
    assert classify_scope_run(run, [{"audit_status": "DETERMINISTICALLY_RECONSTRUCTABLE"}]) == "VALIDATED_WITH_RECONSTRUCTED_REVISION"
    assert classify_scope_run(run, [{"audit_status": "INDIRECTLY_SUPPORTED"}]) == "VALIDATED_WITH_INDIRECT_REVISION"
    assert classify_scope_run(run, []) == "VALIDATED_WITH_UNATTRIBUTED_REVISION"
