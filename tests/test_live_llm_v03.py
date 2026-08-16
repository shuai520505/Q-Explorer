import json

from src.hamiltonian import generate_ising_hamiltonian
from src.research import FixtureProvider, FrozenConfig, LLMResearchAgent, OpenAICompatibleProvider
from src.v03 import LiveTaskRunner, TaskSuite


class _Headers:
    def get(self, _name):
        return "req-test"


class _Response:
    headers = _Headers()
    def __enter__(self): return self
    def __exit__(self, *_args): return None
    def read(self):
        return json.dumps({
            "id": "x", "model": "deepseek-test", "choices": [{"message": {"content": '{"status":"OK"}', "reasoning_content": "private"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        }).encode()


def test_provider_sends_thinking_without_exposing_secret(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test")
    monkeypatch.setenv("LLM_API_KEY", "unit-test-secret")
    monkeypatch.setenv("LLM_MODEL", "deepseek-test")
    captured = {}
    def fake_open(req, timeout):
        captured.update(json.loads(req.data))
        assert req.headers["Authorization"] == "Bearer unit-test-secret"
        return _Response()
    monkeypatch.setattr("src.research.provider.request.urlopen", fake_open)
    response = OpenAICompatibleProvider(thinking_mode=True, reasoning_effort="high").generate("system", {"x": 1}, 0.0)
    assert captured["thinking"] == {"type": "enabled"}
    assert captured["reasoning_effort"] == "high"
    assert "response_format" not in captured
    assert response.reasoning_content_present is True
    assert response.reasoning_content_hash
    assert "private" not in response.text


def test_provider_can_explicitly_disable_thinking(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test")
    monkeypatch.setenv("LLM_API_KEY", "unit-test-secret")
    monkeypatch.setenv("LLM_MODEL", "deepseek-test")
    captured = {}
    monkeypatch.setattr("src.research.provider.request.urlopen", lambda req, timeout: captured.update(json.loads(req.data)) or _Response())
    OpenAICompatibleProvider(thinking_mode=False).generate("system", {"x": 1}, 0.0)
    assert captured["thinking"] == {"type": "disabled"}
    assert captured["response_format"] == {"type": "json_object"}


def test_fixture_live_runner_keeps_oracle_hidden_and_executes_aer(tmp_path):
    task = next(item for item in TaskSuite("configs/frozen_v03_tasks.yaml").tasks if item.task_type == "COMPETING_EXPLANATIONS")
    condition = next(item for item in task.experiment_pool if item["condition_id"] in task.exploration_set)
    ham = generate_ising_hamiltonian(condition["num_qubits"], condition["topology"], condition["ham_seed"])
    payload = {
        "action_id": "ACT_000001", "round": 1, "hypothesis_id": task.initial_hypothesis["hypothesis_id"],
        "action_type": "CONTROL_DEPTH", "reason": "Hold topology fixed and test depth.",
        "experiment": {"hamiltonian_id": ham.hamiltonian_id, "depth": condition["depth"], "entanglement": condition["entanglement"], "seed_group": [2001, 2011]},
        "controlled_variables": ["topology", "entanglement"], "changed_variables": ["depth"],
        "expected_outcome": "Depth separates the explanations.", "falsification_condition": "The effect does not change.",
        "information_goal": "Discriminate the competing explanations.", "revision_proposal": None,
        "confidence": 0.6, "hypothesis_proposal": None,
    }
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("prompt version: research_agent_v03", encoding="utf-8")
    agent = LLMResearchAgent(FixtureProvider([json.dumps(payload)]), prompt, "research_agent_v03", require_v03_fields=True)
    frozen = FrozenConfig("configs/frozen_v03.yaml")
    suite = TaskSuite("configs/frozen_v03_tasks.yaml")
    summary = LiveTaskRunner(frozen.data, frozen.sha256, suite.sha256, tmp_path / "traces", tmp_path / "checkpoints", agent).run_task(task, 999, "abcdef0", "ph", max_rounds=1)
    assert summary["successful_vqe_runs"] == 2
    response_text = (tmp_path / "traces" / "live_llm_responses.jsonl").read_text(encoding="utf-8").lower()
    assert "oracle" not in response_text
    assert "evaluation_metadata" not in response_text
