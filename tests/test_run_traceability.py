from datetime import datetime, timezone

from src.research import FrozenConfig, create_run_identity


def test_run_id_and_frozen_hash_are_traceable(tmp_path):
    config = tmp_path / "frozen.yaml"
    config.write_text("project: {version: '0.2'}\n", encoding="utf-8")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("scientific decision", encoding="utf-8")
    frozen = FrozenConfig(config)
    identity = create_run_identity([], "active_agent", frozen.sha256, prompt, "p1", "fixture", 0.0, 20, datetime(2026, 8, 12, tzinfo=timezone.utc))
    assert identity.run_id == "RUN_20260812_001"
    assert len(identity.config_hash) == 64 and len(identity.prompt_hash) == 64
    frozen.verify_unchanged()

