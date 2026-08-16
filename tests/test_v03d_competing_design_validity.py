from types import SimpleNamespace

from src.v03d import EvidenceGraph, audit_competing_run


def valid_case(strategy="llm"):
    task = SimpleNamespace(experiment_pool=(
        {"condition_id": "D1", "ham_seed": 1, "topology": "chain", "num_qubits": 4, "depth": 1, "entanglement": "ring"},
        {"condition_id": "D3", "ham_seed": 1, "topology": "chain", "num_qubits": 4, "depth": 3, "entanglement": "ring"},
    ))
    records = {
        "actions": [
            {"run_id": "R", "round": 1, "action_id": "A1", "action_type": "CHANGE_INSTANCE", "condition_id": "D1", "reason": "compare connectivity and depth", "information_goal": "discriminate HD_A vs HD_B"},
            {"run_id": "R", "round": 2, "action_id": "A2", "action_type": "CONTROL_DEPTH", "condition_id": "D3", "changed_variables": ["depth"]},
        ],
        "experiments": [
            {"run_id": "R", "action_id": "A1", "experiment_id": "E1", "status": "SUCCESS"},
            {"run_id": "R", "action_id": "A2", "experiment_id": "E2", "status": "SUCCESS"},
        ],
        "evidence": [{"run_id": "R", "action_id": "A2", "evidence_id": "EV2", "decision": "COUNTEREXAMPLE", "reason_codes": ["CONTROL_SUPPORTS_H_B"], "experiment_ids": ["E2"], "held_out": False}],
    }
    run = {"run_id": "R", "strategy": strategy, "final_judgment": "COUNTEREXAMPLE", "validated_judgment": {"validated": True}, "budget": 4, "budget_spent": 4}
    return EvidenceGraph(records), run, task


def test_v03d_valid_single_variable_chain_is_scientifically_valid():
    graph, run, task = valid_case()
    result = audit_competing_run(graph, run, task)
    assert result["single_variable_control_executed"]
    assert result["scientific_design_valid"]
    assert result["scientific_control_score"] == 3
