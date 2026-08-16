import json

from src.research import FixtureProvider, LLMResearchAgent, Observation, ResearchState
from tests.test_action_schema import valid_payload


def observation():
    return Observation.from_state(
        ResearchState(1, ({"hypothesis_id": "H001", "claim": "c", "status": "PENDING"},), {"H001": "PENDING"}, {"H001": ()}, {"H001": ()}, (), (), (), 10, (), {}, (), (), (), ())
    )


def test_invalid_first_response_is_repaired_once(tmp_path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("prompt version: p1", encoding="utf-8")
    provider = FixtureProvider(["not json", json.dumps(valid_payload())])
    agent = LLMResearchAgent(provider, prompt, "p1", max_repair_attempts=1)
    result = agent.request_action(observation(), "ACT_000099")
    assert result.validation_status == "VALID"
    assert result.repair_attempted is True
    assert result.action.action_id == "ACT_000099"
    assert provider.calls == 2


def test_persistently_invalid_output_stays_invalid(tmp_path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("prompt version: p1", encoding="utf-8")
    agent = LLMResearchAgent(FixtureProvider(["bad", "still bad"]), prompt, "p1", max_repair_attempts=1)
    result = agent.request_action(observation(), "ACT_000001")
    assert result.validation_status == "INVALID_ACTION"
    assert result.action is None
    assert result.error

