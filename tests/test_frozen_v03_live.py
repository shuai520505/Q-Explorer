import hashlib
from pathlib import Path

import yaml


def test_live_config_has_no_secret_and_matches_prompt():
    path = Path("configs/frozen_v03_live.yaml")
    raw = path.read_text(encoding="utf-8")
    config = yaml.safe_load(raw)
    assert "api_key" not in raw.lower()
    assert "sk-" not in raw.lower()
    prompt = Path(config["prompt_path"])
    assert hashlib.sha256(prompt.read_bytes()).hexdigest() == config["prompt_hash"]
    assert config["independent_run_seeds"] == [301, 302, 303]
    assert config["thinking_healthcheck_verified"] is True
