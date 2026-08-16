from src.research import ResearchMemory


def test_future_experiments_and_evidence_are_absent_from_prior_state(tmp_path):
    memory = ResearchMemory(tmp_path, "RUN_TEST")
    memory.append("hypotheses", {"round": 0, "hypothesis_id": "H001", "claim": "c", "status": "PENDING"})
    memory.append("experiments", {"round": 4, "experiment_id": "FUTURE", "hamiltonian_id": "HAM_A", "depth": 1, "entanglement": "ring", "initialization_seed": 9, "energy_error": 0.0, "status": "SUCCESS"})
    memory.append("evidence", {"round": 4, "evidence_id": "FUTURE_E", "decision": "SUPPORT"})
    state = memory.rebuild_state_at_round(3, 10, [{"hamiltonian_id": "HAM_A", "depth": 1, "entanglement": "ring", "set": "exploration"}], {"HAM_A": {}})
    assert all(item.get("experiment_id") != "FUTURE" for item in state.recent_experiments)
    assert all(item.get("evidence_id") != "FUTURE_E" for item in state.recent_evidence)

