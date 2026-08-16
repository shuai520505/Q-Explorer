import json

from src.research import Observation, ResearchState, RuleBasedResearchAgent


def state_with(decision):
    regions = (
        {"hamiltonian_id": "HAM_NEW", "depth": 2, "entanglement": "ring", "set": "exploration", "seed_group": [1, 2]},
        {"hamiltonian_id": "HAM_OLD", "depth": 3, "entanglement": "ring", "set": "exploration", "seed_group": [3, 4]},
    )
    return ResearchState(
        round=1, current_hypotheses=({"hypothesis_id": "H001", "claim": "ring helps", "status": "PENDING"},),
        hypothesis_status={"H001": "PENDING"}, supporting_experiments={"H001": ()}, counterexamples={"H001": ()},
        recent_experiments=(), tested_regions=({"hamiltonian_id": "HAM_OLD", "depth": 1, "entanglement": "linear"},),
        untested_regions=regions, remaining_budget=10, available_actions=(), hamiltonian_features={}, aggregate_statistics=(),
        previous_agent_actions=(), recent_evidence=({"evidence_id": "E1", "decision": decision, "rule": "synthetic"},), held_out_ids=(),
    )


def test_support_and_counterexample_change_agent_action_and_reason():
    agent = RuleBasedResearchAgent()
    support = agent.select_action(Observation.from_state(state_with("SUPPORT")), "ACT_000001")
    counter = agent.select_action(Observation.from_state(state_with("COUNTEREXAMPLE")), "ACT_000002")
    assert support.action_type == "BOUNDARY_PROBE"
    assert counter.action_type == "REVISE_HYPOTHESIS"
    assert support.experiment.to_dict() != counter.experiment.to_dict()
    assert support.reason != counter.reason
