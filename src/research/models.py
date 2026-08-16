"""Strict JSON-serializable state, observation, and action schemas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any


ACTION_TYPES = frozenset(
    {
        "REPLICATE",
        "PROPOSE_HYPOTHESIS",
        "CONTROL_DEPTH",
        "CONTROL_ENTANGLEMENT",
        "CHANGE_INSTANCE",
        "SEARCH_COUNTEREXAMPLE",
        "BOUNDARY_PROBE",
        "VALIDATE_HYPOTHESIS",
        "REVISE_HYPOTHESIS",
        "ABANDON_HYPOTHESIS",
        "STOP",
    }
)
ENTANGLEMENTS = frozenset({"linear", "ring"})


class ActionValidationError(ValueError):
    """Raised when an Agent output violates the frozen action contract."""


@dataclass(frozen=True)
class ExperimentSpec:
    hamiltonian_id: str
    depth: int
    entanglement: str
    seed_group: tuple[int, ...]

    def __post_init__(self) -> None:
        if not re.fullmatch(r"HAM_[A-Z0-9]+", self.hamiltonian_id):
            raise ActionValidationError("experiment.hamiltonian_id must be a stable HAM_* identifier")
        if not isinstance(self.depth, int) or self.depth < 1:
            raise ActionValidationError("experiment.depth must be a positive integer")
        if self.entanglement not in ENTANGLEMENTS:
            raise ActionValidationError("experiment.entanglement must be linear or ring")
        if not self.seed_group or any(not isinstance(seed, int) or seed < 0 for seed in self.seed_group):
            raise ActionValidationError("experiment.seed_group must contain non-negative integer seeds")
        if len(set(self.seed_group)) != len(self.seed_group):
            raise ActionValidationError("experiment.seed_group cannot contain duplicates")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["seed_group"] = list(self.seed_group)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExperimentSpec":
        expected = {"hamiltonian_id", "depth", "entanglement", "seed_group"}
        _strict_keys(payload, expected, "experiment")
        seeds = payload["seed_group"]
        if not isinstance(seeds, list):
            raise ActionValidationError("experiment.seed_group must be a JSON array")
        return cls(payload["hamiltonian_id"], payload["depth"], payload["entanglement"], tuple(seeds))


@dataclass(frozen=True)
class ResearchAction:
    action_id: str
    round: int
    hypothesis_id: str
    action_type: str
    reason: str
    experiment: ExperimentSpec | None
    controlled_variables: tuple[str, ...]
    changed_variables: tuple[str, ...]
    expected_outcome: str
    falsification_condition: str
    information_goal: str
    revision_proposal: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if not re.fullmatch(r"ACT_\d{6}", self.action_id):
            raise ActionValidationError("action_id must match ACT_000001")
        if not isinstance(self.round, int) or self.round < 1:
            raise ActionValidationError("round must be a positive integer")
        if not self.hypothesis_id:
            raise ActionValidationError("hypothesis_id is required")
        if self.action_type not in ACTION_TYPES:
            raise ActionValidationError(f"action_type must be one of {sorted(ACTION_TYPES)}")
        if self.action_type == "STOP" and self.experiment is not None:
            raise ActionValidationError("STOP cannot contain an experiment")
        if self.action_type != "STOP" and self.experiment is None:
            raise ActionValidationError("non-STOP actions require an experiment")
        for name, text in {
            "reason": self.reason,
            "expected_outcome": self.expected_outcome,
            "falsification_condition": self.falsification_condition,
            "information_goal": self.information_goal,
        }.items():
            if not isinstance(text, str) or not text.strip():
                raise ActionValidationError(f"{name} must be a non-empty string")
        if not self.controlled_variables or not self.changed_variables:
            raise ActionValidationError("controlled_variables and changed_variables must be non-empty")
        if self.action_type == "REVISE_HYPOTHESIS":
            if not isinstance(self.revision_proposal, dict) or set(self.revision_proposal) != {"new_claim", "scope_change"}:
                raise ActionValidationError("REVISE_HYPOTHESIS requires revision_proposal with new_claim and scope_change")
            if not all(isinstance(value, str) and value.strip() for value in self.revision_proposal.values()):
                raise ActionValidationError("revision_proposal values must be non-empty strings")
        elif self.revision_proposal is not None:
            raise ActionValidationError("revision_proposal is only valid for REVISE_HYPOTHESIS")

    @property
    def budget_cost(self) -> int:
        return 0 if self.experiment is None else len(self.experiment.seed_group)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "round": self.round,
            "hypothesis_id": self.hypothesis_id,
            "action_type": self.action_type,
            "reason": self.reason,
            "experiment": None if self.experiment is None else self.experiment.to_dict(),
            "controlled_variables": list(self.controlled_variables),
            "changed_variables": list(self.changed_variables),
            "expected_outcome": self.expected_outcome,
            "falsification_condition": self.falsification_condition,
            "information_goal": self.information_goal,
            "revision_proposal": self.revision_proposal,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ResearchAction":
        expected = {
            "action_id", "round", "hypothesis_id", "action_type", "reason", "experiment",
            "controlled_variables", "changed_variables", "expected_outcome",
            "falsification_condition", "information_goal",
            "revision_proposal",
        }
        _strict_keys(payload, expected, "action")
        for key in ("controlled_variables", "changed_variables"):
            if not isinstance(payload[key], list) or any(not isinstance(value, str) for value in payload[key]):
                raise ActionValidationError(f"{key} must be a JSON string array")
        experiment = None if payload["experiment"] is None else ExperimentSpec.from_dict(payload["experiment"])
        return cls(
            action_id=payload["action_id"],
            round=payload["round"],
            hypothesis_id=payload["hypothesis_id"],
            action_type=payload["action_type"],
            reason=payload["reason"],
            experiment=experiment,
            controlled_variables=tuple(payload["controlled_variables"]),
            changed_variables=tuple(payload["changed_variables"]),
            expected_outcome=payload["expected_outcome"],
            falsification_condition=payload["falsification_condition"],
            information_goal=payload["information_goal"],
            revision_proposal=payload["revision_proposal"],
        )


def _strict_keys(payload: Any, expected: set[str], location: str) -> None:
    if not isinstance(payload, dict):
        raise ActionValidationError(f"{location} must be a JSON object")
    actual = set(payload)
    if actual != expected:
        missing, extra = sorted(expected - actual), sorted(actual - expected)
        raise ActionValidationError(f"{location} fields mismatch; missing={missing}, extra={extra}")


@dataclass(frozen=True)
class ResearchState:
    round: int
    current_hypotheses: tuple[dict, ...]
    hypothesis_status: dict[str, str]
    supporting_experiments: dict[str, tuple[str, ...]]
    counterexamples: dict[str, tuple[str, ...]]
    recent_experiments: tuple[dict, ...]
    tested_regions: tuple[dict, ...]
    untested_regions: tuple[dict, ...]
    remaining_budget: int
    available_actions: tuple[str, ...]
    hamiltonian_features: dict[str, dict]
    aggregate_statistics: tuple[dict, ...]
    previous_agent_actions: tuple[dict, ...]
    recent_evidence: tuple[dict, ...]
    held_out_ids: tuple[str, ...] = field(default_factory=tuple)
    environment_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _json_value(asdict(self))


@dataclass(frozen=True)
class Observation:
    round: int
    remaining_budget: int
    active_hypothesis: dict
    recent_evidence: tuple[dict, ...]
    known_support: tuple[str, ...]
    known_counterexamples: tuple[str, ...]
    tested_conditions: tuple[dict, ...]
    available_actions: tuple[str, ...]
    untested_conditions: tuple[dict, ...]
    hamiltonian_features: dict[str, dict]
    previous_agent_actions: tuple[dict, ...]
    recent_experiments: tuple[dict, ...]
    environment_metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_state(cls, state: ResearchState, hypothesis_id: str | None = None) -> "Observation":
        hypotheses = list(state.current_hypotheses)
        if not hypotheses:
            raise ValueError("ResearchState has no hypotheses")
        active = next((item for item in hypotheses if item["hypothesis_id"] == hypothesis_id), hypotheses[-1])
        identifier = active["hypothesis_id"]
        return cls(
            round=state.round,
            remaining_budget=state.remaining_budget,
            active_hypothesis=active,
            recent_evidence=state.recent_evidence,
            known_support=state.supporting_experiments.get(identifier, ()),
            known_counterexamples=state.counterexamples.get(identifier, ()),
            tested_conditions=state.tested_regions,
            available_actions=state.available_actions,
            untested_conditions=state.untested_regions,
            hamiltonian_features=state.hamiltonian_features,
            previous_agent_actions=state.previous_agent_actions,
            recent_experiments=state.recent_experiments,
            environment_metadata=state.environment_metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return _json_value(asdict(self))


def _json_value(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value
