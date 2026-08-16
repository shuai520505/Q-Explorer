"""Frozen V0.3-C protocol validation, merging, CIs, and diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from typing import Iterable

import yaml

from src.research import FrozenConfig
from src.v03 import TaskSuite


@dataclass(frozen=True)
class V03CProtocol:
    path: Path
    data: dict
    sha256: str

    @classmethod
    def load(cls, path: str | Path) -> "V03CProtocol":
        path = Path(path).resolve()
        raw = path.read_bytes()
        data = yaml.safe_load(raw)
        protocol = cls(path, data, hashlib.sha256(raw).hexdigest())
        protocol.validate_schema()
        return protocol

    def validate_schema(self) -> None:
        if not self.data.get("frozen") or self.data.get("version") != "0.3-C":
            raise ValueError("V0.3-C protocol must be explicitly frozen")
        if self.data["target_total_runs_per_task"] != 15:
            raise ValueError("V0.3-C target must remain 15 runs per task")
        if self.data["existing_run_seeds"] != [301, 302, 303]:
            raise ValueError("Existing V0.3-B seeds changed")
        if self.data["additional_run_seeds"] != list(range(304, 316)):
            raise ValueError("V0.3-C additional seeds changed")
        if set(self.data["target_task_ids"]) != {"TASK_D01", "TASK_F01", "TASK_G01"}:
            raise ValueError("Target task set changed")
        if self.data["model"] != "deepseek-v4-flash" or self.data["thinking_mode"] is not False:
            raise ValueError("Frozen live model settings changed")

    def verify_workspace(self, root: str | Path) -> dict[str, bool]:
        root = Path(root)
        scientific = FrozenConfig(root / self.data["scientific_config_path"])
        live = FrozenConfig(root / self.data["live_config_path"])
        suite = TaskSuite(root / self.data["task_suite_path"])
        prompt_hash = hashlib.sha256((root / self.data["prompt_path"]).read_bytes()).hexdigest()
        checks = {
            "scientific_config": scientific.sha256 == self.data["scientific_config_hash"],
            "live_config": live.sha256 == self.data["live_config_hash"],
            "task_suite": suite.sha256 == self.data["task_suite_hash"],
            "prompt": prompt_hash == self.data["prompt_hash"] == live.data["prompt_hash"],
            "model": live.data["model"] == self.data["model"],
            "thinking": live.data["thinking_mode"] is self.data["thinking_mode"],
            "judge": _section_hash(scientific.data["judge"]) == self.data["judge_config_hash"],
            "vqe": _section_hash(scientific.data["vqe"]) == self.data["vqe_config_hash"],
        }
        tasks = {task.task_id: task for task in suite.tasks}
        checks["task_ids"] = set(self.data["target_task_ids"]) <= set(tasks)
        checks["budgets"] = all(tasks[task_id].budget == self.data["budget_by_task"][task_id] for task_id in self.data["target_task_ids"])
        return checks


def _section_hash(section: dict) -> str:
    return hashlib.sha256(yaml.safe_dump(section, sort_keys=True).encode()).hexdigest()


def run_key(row: dict) -> tuple[str, str, str]:
    return str(row["run_id"]), str(row["task_id"]), str(row["config_hash"])


def deduplicate_runs(rows: Iterable[dict]) -> list[dict]:
    unique = {}
    for row in rows:
        key = run_key(row)
        if key in unique:
            raise ValueError(f"Duplicate run key: {key}")
        unique[key] = dict(row)
    return list(unique.values())


def merge_replication_runs(existing: list[dict], added: list[dict], target_task_ids: set[str]) -> list[dict]:
    tagged = [dict(row, source_run="v03b") for row in existing if row["task_id"] in target_task_ids]
    tagged += [dict(row, source_run="v03c") for row in added if row["task_id"] in target_task_ids]
    return deduplicate_runs(tagged)


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0 or not 0 <= successes <= total:
        raise ValueError("Wilson interval requires 0 <= successes <= total and total > 0")
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, center - radius), min(1.0, center + radius)


COMPETING_FAILURE_MODES = (
    "FAILED_TO_IDENTIFY_COMPETING_EXPLANATIONS", "FAILED_TO_CONTROL_CONFOUND",
    "NON_DISCRIMINATIVE_EXPERIMENT", "MULTI_VARIABLE_CHANGE", "PREMATURE_CONCLUSION",
    "COUNTEREXAMPLE_IGNORED", "EXCESSIVE_REPLICATION", "INVALID_ACTION", "BUDGET_EXHAUSTED",
)


def classify_failure_modes(run: dict, actions: list[dict], evidence: list[dict], task_type: str) -> list[str]:
    modes = set(run.get("failure_modes", [])) & set(COMPETING_FAILURE_MODES)
    validated = bool(run.get("validated_judgment", {}).get("validated"))
    if run.get("final_judgment") == "INVALID_ACTION" or run.get("invalid_responses", 0):
        modes.add("INVALID_ACTION")
    if not validated and int(run.get("budget_spent", 0)) >= int(run.get("budget", 0)):
        modes.add("BUDGET_EXHAUSTED")
    if any("PREMATURE_CONCLUSION" in action.get("failure_modes", []) for action in actions):
        modes.add("PREMATURE_CONCLUSION")
    if any("COUNTEREXAMPLE_IGNORED" in action.get("failure_modes", []) for action in actions):
        modes.add("COUNTEREXAMPLE_IGNORED")
    if any("EXCESSIVE_REPLICATION" in action.get("failure_modes", []) for action in actions):
        modes.add("EXCESSIVE_REPLICATION")
    if task_type == "COMPETING_EXPLANATIONS":
        text = " ".join(str(action.get(key, "")) for action in actions for key in ("reason", "information_goal")).lower()
        if not any(term in text for term in ("competing", "discriminate", "explanation")):
            modes.add("FAILED_TO_IDENTIFY_COMPETING_EXPLANATIONS")
        controls = [action for action in actions if action.get("action_type") in {"CONTROL_DEPTH", "CONTROL_ENTANGLEMENT"}]
        if not controls:
            modes.add("FAILED_TO_CONTROL_CONFOUND")
            modes.add("NON_DISCRIMINATIVE_EXPERIMENT")
        if any(len(action.get("changed_variables", [])) > 1 for action in controls):
            modes.add("MULTI_VARIABLE_CHANGE")
    return [mode for mode in COMPETING_FAILURE_MODES if mode in modes]
