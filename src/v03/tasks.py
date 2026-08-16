"""Frozen research-task suite with a strict public/oracle information boundary."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


TASK_TYPES = frozenset({
    "SIMPLE_FALSIFICATION", "REPLICATION_NEEDED", "LOCAL_RULE_COUNTEREXAMPLE",
    "COMPETING_EXPLANATIONS", "STABLE_NEGATIVE", "BOUNDARY_TRANSITION",
    "SCOPE_REVISION", "PROBLEM_REVISION",
})


class TaskValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ResearchTask:
    task_id: str
    task_type: str
    initial_observation: tuple[dict, ...]
    initial_hypothesis: dict | None
    scientific_question: str
    allowed_variables: tuple[str, ...]
    controlled_variables: tuple[str, ...]
    experiment_pool: tuple[dict, ...]
    exploration_set: tuple[str, ...]
    held_out_set: tuple[str, ...]
    budget: int
    success_criteria: dict
    falsification_conditions: tuple[str, ...]
    ground_truth_access_policy: str
    difficulty_metadata: dict
    competing_hypotheses: tuple[dict, ...] = ()
    evaluation_metadata: dict | None = None

    def __post_init__(self) -> None:
        if self.task_type not in TASK_TYPES:
            raise TaskValidationError(f"Unknown task_type {self.task_type}")
        if not self.task_id.startswith("TASK_") or self.budget < 1:
            raise TaskValidationError("task_id must start TASK_ and budget must be positive")
        pool_ids = [item.get("condition_id") for item in self.experiment_pool]
        if len(pool_ids) != len(set(pool_ids)) or any(not value for value in pool_ids):
            raise TaskValidationError("condition_id values must be present and unique")
        exploration, held_out = set(self.exploration_set), set(self.held_out_set)
        if exploration & held_out:
            raise TaskValidationError("exploration_set and held_out_set must be disjoint")
        if exploration | held_out != set(pool_ids):
            raise TaskValidationError("Every condition must be assigned to exploration or held-out exactly once")
        if self.ground_truth_access_policy != "EVALUATION_ONLY_AFTER_VALIDATION":
            raise TaskValidationError("V0.3 requires evaluation-only ground truth access")
        required = {"minimum_independent_instances", "minimum_seeds_per_condition", "control_required", "held_out_required"}
        if not required <= self.success_criteria.keys():
            raise TaskValidationError(f"success_criteria missing {sorted(required - self.success_criteria.keys())}")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ResearchTask":
        return cls(
            task_id=payload["task_id"], task_type=payload["task_type"],
            initial_observation=tuple(payload.get("initial_observation", [])),
            initial_hypothesis=payload.get("initial_hypothesis"), scientific_question=payload["scientific_question"],
            allowed_variables=tuple(payload["allowed_variables"]), controlled_variables=tuple(payload["controlled_variables"]),
            experiment_pool=tuple(payload["experiment_pool"]), exploration_set=tuple(payload["exploration_set"]),
            held_out_set=tuple(payload["held_out_set"]), budget=int(payload["budget"]),
            success_criteria=dict(payload["success_criteria"]), falsification_conditions=tuple(payload["falsification_conditions"]),
            ground_truth_access_policy=payload["ground_truth_access_policy"], difficulty_metadata=dict(payload["difficulty_metadata"]),
            competing_hypotheses=tuple(payload.get("competing_hypotheses", [])),
            evaluation_metadata=payload.get("evaluation_metadata"),
        )

    def public_view(self) -> dict[str, Any]:
        """State visible to an Agent: deliberately excludes type, oracle, difficulty, success answer, and held-out outcomes."""
        return {
            "task_id": self.task_id,
            "scientific_question": self.scientific_question,
            "initial_observation": list(self.initial_observation),
            "initial_hypothesis": self.initial_hypothesis,
            "competing_hypotheses": list(self.competing_hypotheses),
            "allowed_variables": list(self.allowed_variables),
            "controlled_variables": list(self.controlled_variables),
            "experiment_pool": [
                {key: value for key, value in item.items() if key not in {"oracle_label", "expected_result"}}
                for item in self.experiment_pool if item["condition_id"] in self.exploration_set
            ],
            "remaining_budget": self.budget,
            "available_actions": [
                "PROPOSE_HYPOTHESIS", "REPLICATE", "CONTROL_DEPTH", "CONTROL_ENTANGLEMENT",
                "CHANGE_INSTANCE", "SEARCH_COUNTEREXAMPLE", "BOUNDARY_PROBE", "VALIDATE_HYPOTHESIS",
                "REVISE_HYPOTHESIS", "ABANDON_HYPOTHESIS", "STOP",
            ],
        }

    def to_dict(self) -> dict:
        return asdict(self)


class TaskSuite:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()
        self._bytes = self.path.read_bytes()
        self.sha256 = hashlib.sha256(self._bytes).hexdigest()
        payload = yaml.safe_load(self._bytes)
        self.version = str(payload["version"])
        self.frozen = bool(payload.get("frozen"))
        self.tasks = tuple(ResearchTask.from_dict(item) for item in payload["tasks"])
        identifiers = [task.task_id for task in self.tasks]
        if len(identifiers) != len(set(identifiers)):
            raise TaskValidationError("task_id values must be unique")
        if len(self.tasks) < 6:
            raise TaskValidationError("V0.3 requires at least six structurally distinct tasks")

    def verify_unchanged(self) -> None:
        if hashlib.sha256(self.path.read_bytes()).hexdigest() != self.sha256:
            raise RuntimeError("Frozen task suite changed during execution")

    def quality_audit(self) -> list[dict]:
        rows = []
        for task in self.tasks:
            metadata = task.difficulty_metadata
            rows.append({
                "task_id": task.task_id,
                "task_type": task.task_type,
                "difficulty": metadata["difficulty"],
                "number_of_valid_actions": len(task.exploration_set),
                "minimum_possible_resolution_runs": int(metadata["minimum_possible_resolution_runs"]),
                "requires_replication": bool(metadata["requires_replication"]),
                "requires_control": bool(metadata["requires_control"]),
                "contains_counterexample": bool(metadata["contains_counterexample"]),
                "contains_competing_explanations": bool(metadata["contains_competing_explanations"]),
                "contains_boundary": bool(metadata["contains_boundary"]),
                "held_out_needed": bool(task.success_criteria["held_out_required"]),
            })
        return rows

