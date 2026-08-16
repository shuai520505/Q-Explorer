"""Research memory rebuilt from append-only V0.1 seed and V0.2 event traces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.evidence import aggregate_experiments
from src.logging import JsonlTrace
from src.research.models import ACTION_TYPES, ResearchState


class ResearchMemory:
    """Read/write facade whose replay methods enforce round cutoffs."""

    TRACE_NAMES = ("runs", "actions", "experiments", "hypotheses", "evidence", "revisions")

    def __init__(self, root: str | Path, run_id: str, v01_root: str | Path | None = None) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self.v01_root = Path(v01_root) if v01_root is not None else None
        self.traces = {name: JsonlTrace(self.root / f"{name}.jsonl") for name in self.TRACE_NAMES}

    def append(self, trace_name: str, record: dict[str, Any]) -> None:
        if trace_name not in self.traces:
            raise KeyError(f"Unknown trace {trace_name!r}")
        payload = dict(record)
        payload.setdefault("run_id", self.run_id)
        self.traces[trace_name].append(payload)

    def _v02_records(self, trace_name: str, through_round: int | None = None) -> list[dict]:
        records = [record for record in self.traces[trace_name].read_all() if record.get("run_id") == self.run_id]
        if through_round is not None:
            records = [record for record in records if int(record.get("round", 0)) <= through_round]
        return records

    def _v01_records(self, trace_name: str) -> list[dict]:
        if self.v01_root is None or trace_name not in {"experiments", "hypotheses", "evidence"}:
            return []
        path = self.v01_root / "traces" / f"{trace_name}.jsonl"
        if not path.exists():
            return []
        records = []
        for record in JsonlTrace(path).read_all():
            seeded = dict(record)
            seeded.setdefault("round", 0)
            seeded["source_version"] = "0.1"
            records.append(seeded)
        return records

    def records(self, trace_name: str, through_round: int | None = None, include_v01: bool = True) -> list[dict]:
        seeded = self._v01_records(trace_name) if include_v01 else []
        return seeded + self._v02_records(trace_name, through_round)

    def get_active_hypotheses(self, through_round: int | None = None) -> list[dict]:
        latest: dict[str, dict] = {}
        for record in self.records("hypotheses", through_round):
            identifier = record.get("hypothesis_id")
            if identifier:
                latest[identifier] = record
        return [latest[key] for key in sorted(latest)]

    def get_hypothesis_history(self, hypothesis_id: str, through_round: int | None = None) -> list[dict]:
        return [
            record for record in self.records("hypotheses", through_round)
            if record.get("hypothesis_id") == hypothesis_id
        ]

    def get_support(self, hypothesis_id: str, through_round: int | None = None) -> list[str]:
        values: list[str] = []
        for record in self.get_hypothesis_history(hypothesis_id, through_round):
            for experiment_id in record.get("supporting_experiments", []):
                if experiment_id not in values:
                    values.append(experiment_id)
        return values

    def get_counterexamples(self, hypothesis_id: str, through_round: int | None = None) -> list[str]:
        values: list[str] = []
        for record in self.get_hypothesis_history(hypothesis_id, through_round):
            for experiment_id in record.get("counterexamples", []):
                if experiment_id not in values:
                    values.append(experiment_id)
        return values

    def get_previous_actions(self, through_round: int | None = None) -> list[dict]:
        return self.records("actions", through_round, include_v01=False)

    def get_experiment(self, experiment_id: str, through_round: int | None = None) -> dict | None:
        return next(
            (record for record in self.records("experiments", through_round) if record.get("experiment_id") == experiment_id),
            None,
        )

    def get_reason_for_revision(self, hypothesis_id: str, through_round: int | None = None) -> dict | None:
        return next(
            (
                record for record in self.records("revisions", through_round, include_v01=False)
                if record.get("new_hypothesis_id") == hypothesis_id
            ),
            None,
        )

    def rebuild_state_at_round(
        self,
        round_id: int,
        total_budget: int,
        experiment_space: list[dict],
        hamiltonian_features: dict[str, dict],
    ) -> ResearchState:
        """Rebuild exactly what was knowable at a round; later records are excluded."""

        if round_id < 0:
            raise ValueError("round_id cannot be negative")
        hypotheses = self.get_active_hypotheses(round_id)
        actions = self.get_previous_actions(round_id)
        experiments = self.records("experiments", round_id)
        evidence = self.records("evidence", round_id)
        spent = sum(int(action.get("budget_cost", 0)) for action in actions if action.get("validation_status") == "VALID")
        remaining = total_budget - spent
        if remaining < 0:
            raise ValueError("Trace spends more than the frozen budget")

        tested_keys = {
            (record.get("hamiltonian_id"), int(record.get("depth", 0)), record.get("entanglement"))
            for record in experiments
            if record.get("status") == "SUCCESS"
        }
        tested_regions = tuple(
            {
                "hamiltonian_id": ham_id,
                "depth": depth,
                "entanglement": entanglement,
                "set": _space_set(experiment_space, ham_id),
            }
            for ham_id, depth, entanglement in sorted(tested_keys)
        )
        # Held-out identities/conditions may be known, but outcomes are absent until explicitly executed.
        untested_regions = tuple(
            dict(region) for region in experiment_space
            if (region["hamiltonian_id"], region["depth"], region["entanglement"]) not in tested_keys
        )
        status = {item["hypothesis_id"]: item.get("status", "PENDING") for item in hypotheses}
        support = {identifier: tuple(self.get_support(identifier, round_id)) for identifier in status}
        counterexamples = {identifier: tuple(self.get_counterexamples(identifier, round_id)) for identifier in status}
        recent_experiments = tuple(_compact_experiment(record) for record in experiments[-12:])
        recent_evidence = tuple(_compact_evidence(record) for record in evidence[-6:])
        aggregates = tuple(aggregate_experiments(experiments)) if experiments else ()
        held_out_ids = tuple(sorted({item["hamiltonian_id"] for item in experiment_space if item.get("set") == "held_out"}))
        return ResearchState(
            round=round_id,
            current_hypotheses=tuple(_compact_hypothesis(item) for item in hypotheses),
            hypothesis_status=status,
            supporting_experiments=support,
            counterexamples=counterexamples,
            recent_experiments=recent_experiments,
            tested_regions=tested_regions,
            untested_regions=untested_regions,
            remaining_budget=remaining,
            available_actions=tuple(sorted(ACTION_TYPES)),
            hamiltonian_features={key: dict(value) for key, value in hamiltonian_features.items()},
            aggregate_statistics=aggregates,
            previous_agent_actions=tuple(_compact_action(item) for item in actions),
            recent_evidence=recent_evidence,
            held_out_ids=held_out_ids,
        )


def _space_set(experiment_space: list[dict], hamiltonian_id: str) -> str:
    return next((item.get("set", "exploration") for item in experiment_space if item["hamiltonian_id"] == hamiltonian_id), "legacy")


def _compact_hypothesis(record: dict) -> dict:
    return {
        key: record.get(key)
        for key in ("hypothesis_id", "parent_hypothesis_id", "claim", "status", "supporting_experiments", "counterexamples")
        if key in record
    }


def _compact_experiment(record: dict) -> dict:
    return {
        key: record.get(key)
        for key in (
            "experiment_id", "round", "hamiltonian_id", "depth", "entanglement",
            "initialization_seed", "energy_error", "converged", "status", "held_out",
        )
        if key in record
    }


def _compact_evidence(record: dict) -> dict:
    return {
        key: record.get(key)
        for key in (
            "evidence_id", "round", "hypothesis_id", "decision", "rule", "reason_codes",
            "experiment_ids", "comparison", "held_out",
        )
        if key in record
    }


def _compact_action(record: dict) -> dict:
    return {
        key: record.get(key)
        for key in (
            "action_id", "round", "hypothesis_id", "action_type", "reason", "experiment",
            "information_goal", "validation_status", "budget_cost", "budget_after",
        )
        if key in record
    }
