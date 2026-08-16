"""Frozen V0.2 selection baselines sharing the ResearchAction contract."""

from __future__ import annotations

import random

from src.research.agents import ResearchAgent
from src.research.models import ExperimentSpec, Observation, ResearchAction


def _eligible(observation: Observation) -> list[dict]:
    validation = observation.remaining_budget <= 4
    regions = [item for item in observation.untested_conditions if (item.get("set") == "held_out") == validation]
    return regions or list(observation.untested_conditions)


def _baseline_action(action_id: str, observation: Observation, region: dict, action_type: str, reason: str) -> ResearchAction:
    seeds = tuple(region["seed_group"][: observation.remaining_budget])
    return ResearchAction(
        action_id=action_id,
        round=observation.round,
        hypothesis_id=observation.active_hypothesis["hypothesis_id"],
        action_type=action_type,
        reason=reason,
        experiment=ExperimentSpec(region["hamiltonian_id"], int(region["depth"]), region["entanglement"], seeds),
        controlled_variables=("optimizer", "seed_policy", "budget"),
        changed_variables=("experiment_condition",),
        expected_outcome="The selected condition adds a comparable observation under the shared fact layer.",
        falsification_condition="The observed topology direction differs from the active claim.",
        information_goal="Provide a policy-neutral comparison point under the frozen experiment space.",
        revision_proposal=None,
    )


class RandomExplorer(ResearchAgent):
    name = "random"

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self._rng = random.Random(seed)

    def select_action(self, observation: Observation, action_id: str) -> ResearchAction:
        regions = _eligible(observation)
        if not regions:
            raise RuntimeError("RandomExplorer has no affordable frozen condition")
        ordered = sorted(regions, key=lambda item: (item["hamiltonian_id"], item["depth"], item["entanglement"]))
        region = ordered[0] if observation.remaining_budget <= 4 else self._rng.choice(ordered)
        action_type = "VALIDATE_HYPOTHESIS" if region.get("set") == "held_out" else "CHANGE_INSTANCE"
        return _baseline_action(action_id, observation, region, action_type, f"Random baseline draw using frozen baseline seed {self.seed}; evidence does not alter selection probabilities.")


class NoInterventionExplorer(ResearchAgent):
    name = "no_intervention"

    def __init__(self, plan: list[dict]) -> None:
        self.plan = [dict(item) for item in plan]
        self.position = 0

    def select_action(self, observation: Observation, action_id: str) -> ResearchAction:
        if self.position >= len(self.plan):
            raise RuntimeError("No-intervention plan exhausted")
        planned = self.plan[self.position]
        self.position += 1
        candidates = [item for item in observation.untested_conditions if _key(item) == _key(planned)]
        if not candidates:
            candidates = [item for item in observation.tested_conditions if _key(item) == _key(planned)]
        if not candidates:
            raise RuntimeError(f"Frozen planned condition unavailable: {_key(planned)}")
        region = candidates[0]
        action_type = "VALIDATE_HYPOTHESIS" if region.get("set") == "held_out" else "CONTROL_ENTANGLEMENT"
        return _baseline_action(action_id, observation, region, action_type, "Execute the next condition from the complete pre-registered sequence; observed evidence cannot alter this plan.")


class FixedExplorer(ResearchAgent):
    name = "fixed"

    def __init__(self, depth: int, entanglement: str) -> None:
        self.depth = depth
        self.entanglement = entanglement

    def select_action(self, observation: Observation, action_id: str) -> ResearchAction:
        regions = _eligible(observation)
        if observation.remaining_budget <= 4:
            region = sorted(regions, key=lambda item: (item["hamiltonian_id"], item["depth"], item["entanglement"]))[0]
            return _baseline_action(action_id, observation, region, "VALIDATE_HYPOTHESIS", "Execute the common pre-registered held-out validation condition after exploration.")
        fixed = [item for item in regions if item["depth"] == self.depth and item["entanglement"] == self.entanglement]
        if not fixed:
            fixed = [item for item in observation.tested_conditions if item["depth"] == self.depth and item["entanglement"] == self.entanglement and item.get("set") != "held_out"]
        region = sorted(fixed or regions, key=lambda item: (item["hamiltonian_id"], item["depth"], item["entanglement"]))[0]
        action_type = "VALIDATE_HYPOTHESIS" if region.get("set") == "held_out" else "CONTROL_DEPTH"
        return _baseline_action(action_id, observation, region, action_type, f"Use the pre-frozen fixed condition depth={self.depth}, entanglement={self.entanglement}; evidence does not change it.")


def balanced_no_intervention_plan(experiment_space: list[dict], action_count: int) -> list[dict]:
    exploration = sorted((item for item in experiment_space if item.get("set") == "exploration"), key=lambda item: (item["depth"], item["entanglement"], item["hamiltonian_id"]))
    held_out = sorted((item for item in experiment_space if item.get("set") == "held_out"), key=lambda item: (item["hamiltonian_id"], item["depth"], item["entanglement"]))
    validation_slots = min(2, action_count)
    return exploration[: action_count - validation_slots] + held_out[:validation_slots]


def _key(region: dict) -> tuple:
    return region["hamiltonian_id"], int(region["depth"]), region["entanglement"]
