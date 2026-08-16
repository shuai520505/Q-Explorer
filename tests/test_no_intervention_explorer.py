from src.baselines import NoInterventionExplorer
from src.research import Observation
from tests.test_agent_feedback_sensitivity import state_with


def test_no_intervention_ignores_evidence_and_follows_plan():
    plan = [{"hamiltonian_id": "HAM_NEW", "depth": 2, "entanglement": "ring"}]
    support = NoInterventionExplorer(plan).select_action(Observation.from_state(state_with("SUPPORT")), "ACT_000001")
    counter = NoInterventionExplorer(plan).select_action(Observation.from_state(state_with("COUNTEREXAMPLE")), "ACT_000001")
    assert support.experiment == counter.experiment
    assert support.reason == counter.reason


def test_no_intervention_can_execute_preregistered_replicate_from_tested_state():
    state = state_with("SUPPORT")
    from dataclasses import replace
    tested = dict(state.tested_regions[0]) | {"seed_group": [5, 6], "set": "exploration"}
    observation = Observation.from_state(replace(state, tested_regions=(tested,), untested_regions=()))
    plan = [{"hamiltonian_id": tested["hamiltonian_id"], "depth": tested["depth"], "entanglement": tested["entanglement"]}]
    action = NoInterventionExplorer(plan).select_action(observation, "ACT_000001")
    assert action.experiment.seed_group == (5, 6)
