import pytest

from src.research import FixtureProvider, LLMResearchAgent


def test_prompt_version_marker_must_match(tmp_path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("prompt version: v1", encoding="utf-8")
    with pytest.raises(ValueError, match="version marker"):
        LLMResearchAgent(FixtureProvider([]), prompt, "v2")


def test_prompt_version_match_is_accepted(tmp_path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("prompt version: v1", encoding="utf-8")
    agent = LLMResearchAgent(FixtureProvider([]), prompt, "v1")
    assert agent.prompt_version == "v1"

