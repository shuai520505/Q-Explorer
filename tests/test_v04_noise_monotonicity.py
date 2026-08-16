from pathlib import Path

import yaml


def test_v04_noise_probabilities_are_componentwise_monotonic():
    levels = yaml.safe_load(Path("configs/frozen_v04_noise.yaml").read_text(encoding="utf-8"))["noise_levels"]
    for key in ("p_1q", "p_2q", "p_readout"):
        values = [float(levels[level][key]) for level in ("N0", "N1", "N2", "N3")]
        assert values == sorted(values)
        assert len(set(values)) == 4
