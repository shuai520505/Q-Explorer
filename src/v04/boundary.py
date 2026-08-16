"""Programmatic boundary signatures and transition estimation for TASK_F01."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from statistics import mean, variance


@dataclass(frozen=True)
class BoundarySignature:
    run_id: str
    noise_level: str
    validated: bool
    candidate_boundary_region: tuple[int, int] | None
    boundary_location: float | None
    effect_direction: str
    effect_magnitude: float | None
    uncertainty: float | None
    contrast_by_depth: tuple[dict, ...]
    supporting_experiment_ids: tuple[str, ...]
    counterexample_ids: tuple[str, ...]
    held_out_result: str
    hypothesis_id: str

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["candidate_boundary_region"] = None if self.candidate_boundary_region is None else list(self.candidate_boundary_region)
        payload["contrast_by_depth"] = list(self.contrast_by_depth)
        payload["supporting_experiment_ids"] = list(self.supporting_experiment_ids)
        payload["counterexample_ids"] = list(self.counterexample_ids)
        return payload


class BoundaryEstimator:
    """Estimate the depth transition from paired ring-minus-linear errors."""

    def __init__(self, absolute_effect_deadband: float, minimum_boundary_change: float) -> None:
        self.absolute_effect_deadband = float(absolute_effect_deadband)
        self.minimum_boundary_change = float(minimum_boundary_change)
        if self.absolute_effect_deadband < 0 or self.minimum_boundary_change <= 0:
            raise ValueError("Boundary thresholds must be non-negative/positive")

    @staticmethod
    def _direction(contrast: float, deadband: float) -> str:
        if contrast > deadband:
            return "RING_WORSE"
        if contrast < -deadband:
            return "RING_BETTER"
        return "NO_CLEAR_EFFECT"

    def estimate(self, run_id: str, noise_level: str, experiments: list[dict], task, validated: bool, hypothesis_id: str) -> BoundarySignature:
        conditions = {row["condition_id"]: row for row in task.experiment_pool}
        exploration = set(task.exploration_set)
        held_out = set(task.held_out_set)
        grouped: dict[tuple[str, int, str], list[dict]] = {}
        for record in experiments:
            condition_id = record.get("condition_id")
            condition = conditions.get(condition_id)
            if condition and record.get("status") == "SUCCESS" and record.get("energy_error") is not None:
                grouped.setdefault((condition_id, int(condition["depth"]), condition["entanglement"]), []).append(record)

        depth_rows = []
        for depth in sorted({int(row["depth"]) for row in task.experiment_pool if row["condition_id"] in exploration}):
            linear = [record for (condition, item_depth, ent), records in grouped.items() if condition in exploration and item_depth == depth and ent == "linear" for record in records]
            ring = [record for (condition, item_depth, ent), records in grouped.items() if condition in exploration and item_depth == depth and ent == "ring" for record in records]
            if not linear or not ring:
                continue
            linear_errors = [float(row["energy_error"]) for row in linear]
            ring_errors = [float(row["energy_error"]) for row in ring]
            contrast = mean(ring_errors) - mean(linear_errors)
            se = math.sqrt(
                (variance(ring_errors) / len(ring_errors) if len(ring_errors) > 1 else 0.0)
                + (variance(linear_errors) / len(linear_errors) if len(linear_errors) > 1 else 0.0)
            )
            depth_rows.append({
                "depth": depth, "ring_minus_linear": contrast, "standard_error": se,
                "direction": self._direction(contrast, self.absolute_effect_deadband),
                "linear_n": len(linear), "ring_n": len(ring),
                "experiment_ids": [row["experiment_id"] for row in linear + ring],
            })

        region = None
        if len(depth_rows) >= 2:
            pairs = [
                (abs(right["ring_minus_linear"] - left["ring_minus_linear"]), left, right)
                for left, right in zip(depth_rows, depth_rows[1:])
            ]
            change, left, right = max(pairs, key=lambda item: (item[0], item[2]["depth"]))
            if change >= self.minimum_boundary_change or left["direction"] != right["direction"]:
                region = (int(left["depth"]), int(right["depth"]))

        deepest = max(depth_rows, key=lambda row: row["depth"]) if depth_rows else None
        held_linear = [record for (condition, _, ent), records in grouped.items() if condition in held_out and ent == "linear" for record in records]
        held_ring = [record for (condition, _, ent), records in grouped.items() if condition in held_out and ent == "ring" for record in records]
        held_direction = "NOT_RESOLVED"
        counterexamples: list[str] = []
        if held_linear and held_ring:
            held_contrast = mean(float(row["energy_error"]) for row in held_ring) - mean(float(row["energy_error"]) for row in held_linear)
            held_direction = self._direction(held_contrast, self.absolute_effect_deadband)
            if deepest and held_direction not in {deepest["direction"], "NO_CLEAR_EFFECT"}:
                counterexamples = [row["experiment_id"] for row in held_linear + held_ring]
        supporting = [identifier for row in depth_rows for identifier in row["experiment_ids"]]
        return BoundarySignature(
            run_id=run_id, noise_level=noise_level, validated=bool(validated),
            candidate_boundary_region=region,
            boundary_location=None if region is None else mean(region),
            effect_direction=deepest["direction"] if deepest else "UNRESOLVED",
            effect_magnitude=None if deepest is None else abs(float(deepest["ring_minus_linear"])),
            uncertainty=None if not depth_rows else max(float(row["standard_error"]) for row in depth_rows),
            contrast_by_depth=tuple(depth_rows), supporting_experiment_ids=tuple(supporting),
            counterexample_ids=tuple(counterexamples), held_out_result=held_direction,
            hypothesis_id=hypothesis_id,
        )


def shift_category(reference: BoundarySignature, noisy: BoundarySignature, small_shift_max: float) -> tuple[str, float | None]:
    if reference.boundary_location is None or noisy.boundary_location is None:
        return "UNRESOLVED", None
    magnitude = abs(noisy.boundary_location - reference.boundary_location)
    if magnitude == 0:
        return "NO_SHIFT", 0.0
    if magnitude <= float(small_shift_max):
        return "SMALL_SHIFT", magnitude
    return "LARGE_SHIFT", magnitude
