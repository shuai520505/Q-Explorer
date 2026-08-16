from src.research import ResearchMemory


def test_memory_api_and_round_replay(tmp_path):
    memory = ResearchMemory(tmp_path, "RUN_TEST")
    memory.append("hypotheses", {"round": 0, "hypothesis_id": "H001", "claim": "c", "status": "PENDING", "supporting_experiments": [], "counterexamples": []})
    memory.append("actions", {"round": 1, "action_id": "ACT_000001", "validation_status": "VALID", "budget_cost": 2})
    memory.append("experiments", {"round": 1, "experiment_id": "V02_EXP_1", "hamiltonian_id": "HAM_A", "depth": 1, "entanglement": "linear", "initialization_seed": 1, "energy_error": 0.1, "converged": False, "status": "SUCCESS"})
    memory.append("evidence", {"round": 2, "evidence_id": "E2", "hypothesis_id": "H001", "decision": "SUPPORT"})
    space = [{"hamiltonian_id": "HAM_A", "depth": 1, "entanglement": "linear", "set": "exploration"}]
    state1 = memory.rebuild_state_at_round(1, 10, space, {"HAM_A": {}})
    state2 = memory.rebuild_state_at_round(2, 10, space, {"HAM_A": {}})
    assert state1.remaining_budget == 8
    assert state1.recent_evidence == ()
    assert state2.recent_evidence[-1]["decision"] == "SUPPORT"
    assert memory.get_experiment("V02_EXP_1", 1)["round"] == 1

