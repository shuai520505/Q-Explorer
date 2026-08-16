"""Frozen V0.4 protocol loader and mutation checks."""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _section_hash(section) -> str:
    return hashlib.sha256(yaml.safe_dump(section, sort_keys=True).encode("utf-8")).hexdigest()


class V04Protocol:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()
        self._bytes = self.path.read_bytes()
        self.sha256 = hashlib.sha256(self._bytes).hexdigest()
        self.data = yaml.safe_load(self._bytes)

    @classmethod
    def load(cls, path: str | Path) -> "V04Protocol":
        protocol = cls(path)
        protocol.validate()
        return protocol

    def validate(self) -> None:
        data = self.data
        if data.get("version") != "0.4" or not data.get("frozen"):
            raise ValueError("V0.4 protocol must be version 0.4 and frozen")
        if data["target_task_id"] != "TASK_F01" or data["target_task_type"] != "BOUNDARY_TRANSITION":
            raise ValueError("V0.4 permits only the frozen Boundary task")
        if data["noise_level_ids"] != ["N1", "N2", "N3"]:
            raise ValueError("Formal V0.4 levels must be exactly N1/N2/N3")
        if int(data["runs_per_noise_level"]) != 15 or int(data["vqe_budget_per_run"]) != 16:
            raise ValueError("V0.4 freezes 15 runs per noise level and 16 VQE runs per research run")
        for level in data["noise_level_ids"]:
            seeds = list(data["run_seeds"][level])
            if len(seeds) != 15 or len(set(seeds)) != 15:
                raise ValueError(f"{level} must contain exactly 15 unique run seeds")
        if set(data["discovery_signals"]["allowed"]) != {"PRESERVED", "SHIFTED", "WEAKENED", "DISAPPEARED", "COUNTEREXAMPLE_EMERGED", "INCONCLUSIVE"}:
            raise ValueError("Discovery signal set changed")

    def verify_workspace(self, root: str | Path) -> dict[str, bool]:
        root = Path(root).resolve()
        scientific = yaml.safe_load((root / self.data["scientific_config_path"]).read_text(encoding="utf-8"))
        noise = yaml.safe_load((root / self.data["noise_config_path"]).read_text(encoding="utf-8"))
        levels = noise["noise_levels"]
        monotonic = all(
            [float(levels[name][key]) for name in ("N0", "N1", "N2", "N3")] == sorted(float(levels[name][key]) for name in ("N0", "N1", "N2", "N3"))
            for key in ("p_1q", "p_2q", "p_readout")
        )
        return {
            "protocol": _sha(self.path) == self.sha256,
            "scientific_config": _sha(root / self.data["scientific_config_path"]) == self.data["scientific_config_hash"],
            "task_suite": _sha(root / self.data["task_suite_path"]) == self.data["task_suite_hash"],
            "judge": _section_hash(scientific["judge"]) == self.data["judge_config_hash"],
            "vqe": _section_hash(scientific["vqe"]) == self.data["vqe_config_hash"],
            "noise_config": _sha(root / self.data["noise_config_path"]) == self.data["noise_config_hash"],
            "noise_monotonic": monotonic,
            "prompt": _sha(root / self.data["agent"]["prompt_path"]) == self.data["agent"]["prompt_hash"],
            "transfer_hypothesis": _sha(root / self.data["transfer_hypothesis_path"]) == self.data["transfer_hypothesis_hash"],
            "smoke_test": _sha(root / self.data["smoke_test_path"]) == self.data["smoke_test_hash"],
            "history_snapshot": _sha(root / self.data["history_snapshot_before_path"]) == self.data["history_snapshot_before_hash"],
            "shots": noise.get("shots") is None and self.data["shots"]["value"] is None,
        }
