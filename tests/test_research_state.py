import json

from src.research import Observation, ResearchMemory


def test_research_state_is_serializable_and_observation_explains_counterexample(tmp_path):
    memory = ResearchMemory(tmp_path / "v02", "RUN_TEST")
    memory.append("hypotheses", {"round": 0, "hypothesis_id": "H001", "claim": "ring helps", "status": "NARROWED", "supporting_experiments": [], "counterexamples": ["EXP_A"]})
    memory.append("evidence", {"round": 0, "evidence_id": "E1", "hypothesis_id": "H001", "decision": "COUNTEREXAMPLE", "rule": "relative_worsening_threshold", "experiment_ids": ["EXP_A"]})
    space = [{"hamiltonian_id": "HAM_A", "depth": 1, "entanglement": "ring", "set": "exploration"}]
    state = memory.rebuild_state_at_round(0, 10, space, {"HAM_A": {"topology": "chain"}})
    payload = state.to_dict()
    json.dumps(payload)
    observation = Observation.from_state(state, "H001").to_dict()
    assert observation["recent_evidence"][-1]["decision"] == "COUNTEREXAMPLE"
    assert observation["active_hypothesis"]["status"] == "NARROWED"

