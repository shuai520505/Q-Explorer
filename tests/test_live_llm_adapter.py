import pytest

from src.research import OpenAICompatibleProvider


def test_live_provider_requires_environment_credentials(monkeypatch):
    for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="required"):
        OpenAICompatibleProvider(max_tokens=10, timeout=1, retry=0)

