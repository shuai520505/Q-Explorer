"""Research decision policies, cleanly separated from the VQE fact layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
from typing import Any

from src.research.models import ExperimentSpec, Observation, ResearchAction


class ResearchAgent(ABC):
    name = "research_agent"

    @abstractmethod
    def select_action(self, observation: Observation, action_id: str) -> ResearchAction:
        """Select a structured scientific action without executing an experiment."""


class FixtureResearchAgent(ResearchAgent):
    """Deterministic scripted fixture used only for schema/integration tests."""

    name = "fixture"

    def __init__(self, actions: list[ResearchAction]) -> None:
        self._actions = list(actions)
        self._position = 0

    def select_action(self, observation: Observation, action_id: str) -> ResearchAction:
        if self._position >= len(self._actions):
            raise IndexError("FixtureResearchAgent exhausted")
        template = self._actions[self._position]
        self._position += 1
        payload = template.to_dict() | {"action_id": action_id, "round": observation.round}
        return ResearchAction.from_dict(payload)


class RuleBasedResearchAgent(ResearchAgent):
    """Transparent evidence-responsive policy used when no live LLM is configured."""

    name = "rule_based_v01"

    def select_action(self, observation: Observation, action_id: str) -> ResearchAction:
        recent_label = observation.recent_evidence[-1].get("decision") if observation.recent_evidence else None
        hypothesis_id = observation.active_hypothesis["hypothesis_id"]
        status = observation.active_hypothesis.get("status", "PENDING")
        affordable = observation.remaining_budget
        if affordable <= 0:
            return _stop(action_id, observation.round, hypothesis_id, "The VQE-run budget is exhausted.")

        held_out = [item for item in observation.untested_conditions if item.get("set") == "held_out"]
        if affordable <= 4 and held_out:
            region = sorted(held_out, key=lambda item: (item["hamiltonian_id"], item["depth"], item["entanglement"]))[0]
            return _action(
                action_id, observation.round, hypothesis_id, "VALIDATE_HYPOTHESIS", region, affordable,
                "The frozen exploration budget is nearly exhausted, so use the reserved held-out validation flow without reading held-out outcomes in advance.",
                ["depth", "optimizer", "seed_policy"], ["hamiltonian", "entanglement"],
                "The candidate direction replicates on the held-out instance.",
                "The held-out comparison reverses or is inconclusive under frozen thresholds.",
                "Measure held-out replication after hypothesis formation.",
            )

        if recent_label == "COUNTEREXAMPLE" or status == "NARROWED":
            region = _choose_region(observation, prefer_new_instance=True, prefer_depth=2)
            action_type = "REVISE_HYPOTHESIS" if hypothesis_id == "H001" else "CHANGE_INSTANCE"
            return _action(
                action_id, observation.round, hypothesis_id, action_type, region, affordable,
                "A counterexample narrowed the original claim; changing only the Hamiltonian instance tests whether it was instance-specific.",
                ["depth", "entanglement", "optimizer", "seed_policy"], ["hamiltonian"],
                "The topology comparison changes on an independent exploration instance.",
                "The counterexample pattern persists on the new instance, ruling out an instance-specific explanation.",
                "Separate instance dependence from a broader entanglement failure condition.",
                revision_proposal={
                    "new_claim": "Ring entanglement may lower VQE error only for a restricted subset of Hamiltonian structures and circuit depths.",
                    "scope_change": "universal fixed-condition claim -> conditional topology-and-depth scope",
                } if action_type == "REVISE_HYPOTHESIS" else None,
            )
        if recent_label == "SUPPORT":
            region = _choose_region(observation, prefer_new_instance=False, prefer_depth=3)
            return _action(
                action_id, observation.round, hypothesis_id, "BOUNDARY_PROBE", region, affordable,
                "Support motivates a one-variable depth boundary probe before broader validation.",
                ["hamiltonian", "entanglement", "optimizer", "seed_policy"], ["depth"],
                "The supported direction remains at the adjacent depth.",
                "The direction reverses or falls below the frozen support threshold at the adjacent depth.",
                "Locate a depth boundary rather than optimize energy.",
            )
        if recent_label in {"INCONCLUSIVE", "WEAKEN"}:
            region = _paired_control_region(observation) or _choose_region(observation, prefer_new_instance=False, prefer_depth=None)
            return _action(
                action_id, observation.round, hypothesis_id, "CONTROL_ENTANGLEMENT", region, affordable,
                "Inconclusive evidence requires the paired entanglement control on the same Hamiltonian and depth.",
                ["hamiltonian", "depth", "optimizer", "seed_policy"], ["entanglement"],
                "The paired control resolves the effect direction.",
                "The effect remains below variance or changes direction across seeds.",
                "Distinguish topology association from initialization variability.",
            )
        region = _choose_region(observation, prefer_new_instance=True, prefer_depth=1)
        return _action(
            action_id, observation.round, hypothesis_id, "SEARCH_COUNTEREXAMPLE", region, affordable,
            "No current decisive evidence exists, so test a new instance with an explicit falsification target.",
            ["depth", "optimizer", "seed_policy"], ["hamiltonian", "entanglement"],
            "The candidate direction appears on the new instance.",
            "The direction reverses on the new instance.",
            "Seek a scientifically informative counterexample.",
        )


def _choose_region(observation: Observation, prefer_new_instance: bool, prefer_depth: int | None) -> dict:
    regions = [item for item in observation.untested_conditions if item.get("set") != "held_out"]
    if not regions:
        # A declared replicate is preferable to inventing an experiment outside the frozen space.
        if observation.tested_conditions:
            return dict(observation.tested_conditions[0])
        raise RuntimeError("No frozen experiment condition is available")
    tested_ids = {item["hamiltonian_id"] for item in observation.tested_conditions}
    def score(region: dict) -> tuple:
        new_instance = int(region["hamiltonian_id"] not in tested_ids) if prefer_new_instance else 0
        depth_match = int(prefer_depth is not None and region["depth"] == prefer_depth)
        ring = int(region["entanglement"] == "ring")
        return (-new_instance, -depth_match, -ring, region["hamiltonian_id"], region["depth"])
    return sorted(regions, key=score)[0]


def _paired_control_region(observation: Observation) -> dict | None:
    if not observation.recent_experiments:
        return None
    last = observation.recent_experiments[-1]
    complement = "linear" if last["entanglement"] == "ring" else "ring"
    return next(
        (
            item for item in observation.untested_conditions
            if item.get("set") != "held_out"
            and item["hamiltonian_id"] == last["hamiltonian_id"]
            and int(item["depth"]) == int(last["depth"])
            and item["entanglement"] == complement
        ),
        None,
    )


def _action(
    action_id: str, round_id: int, hypothesis_id: str, action_type: str, region: dict, budget: int,
    reason: str, controlled: list[str], changed: list[str], expected: str, falsification: str, goal: str,
    revision_proposal: dict[str, str] | None = None,
) -> ResearchAction:
    seeds = tuple(region.get("seed_group", ()))
    if not seeds:
        raise RuntimeError("Frozen experiment region lacks a seed_group")
    seeds = seeds[:budget]
    return ResearchAction(
        action_id, round_id, hypothesis_id, action_type,
        reason,
        ExperimentSpec(region["hamiltonian_id"], int(region["depth"]), region["entanglement"], seeds),
        tuple(controlled), tuple(changed), expected, falsification, goal, revision_proposal,
    )


def _stop(action_id: str, round_id: int, hypothesis_id: str, reason: str) -> ResearchAction:
    return ResearchAction(action_id, round_id, hypothesis_id, "STOP", reason, None, ("frozen_space",), ("execution",), "No experiment runs.", "New budget becomes available.", "Prevent budget violation.", None)


@dataclass(frozen=True)
class AgentResponse:
    action: ResearchAction | None
    validation_status: str
    raw_response_hash: str
    request_id: str | None
    repair_attempted: bool
    error: str | None
    raw_response: str | None = None
    model: str | None = None
    usage: dict[str, int] | None = None
    latency_seconds: float | None = None
    reasoning_content_present: bool = False
    reasoning_content_hash: str | None = None
    confidence: float | None = None
    hypothesis_proposal: dict | None = None
