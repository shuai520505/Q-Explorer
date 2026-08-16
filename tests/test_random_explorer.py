from src.baselines import RandomExplorer
from src.research import Observation
from tests.test_agent_feedback_sensitivity import state_with


def test_random_explorer_is_seed_reproducible():
    observation = Observation.from_state(state_with("SUPPORT"))
    first = RandomExplorer(17).select_action(observation, "ACT_000001")
    second = RandomExplorer(17).select_action(observation, "ACT_000001")
    assert first.to_dict() == second.to_dict()
    assert "baseline seed 17" in first.reason

