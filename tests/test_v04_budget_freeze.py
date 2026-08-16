from pathlib import Path

import yaml


def test_v04_protocol_freezes_15_runs_and_16_vqe_budget():
    path = Path("configs/frozen_v04.yaml")
    if not path.exists():
        return
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert payload["runs_per_noise_level"] == 15
    assert payload["vqe_budget_per_run"] == 16
    assert payload["noise_level_ids"] == ["N1", "N2", "N3"]
