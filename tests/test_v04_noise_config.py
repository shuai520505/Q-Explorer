from pathlib import Path

import yaml

from src.backend import NoiseConfig


def test_v04_frozen_noise_config_has_exact_levels_and_no_shots():
    payload = yaml.safe_load(Path("configs/frozen_v04_noise.yaml").read_text(encoding="utf-8"))
    assert list(payload["noise_levels"]) == ["N0", "N1", "N2", "N3"]
    assert payload["shots"] is None
    for level, values in payload["noise_levels"].items():
        NoiseConfig(level, shots=payload["shots"], **values)
