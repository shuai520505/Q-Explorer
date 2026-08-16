"""Deterministic N0 transfer hypothesis reconstruction from immutable traces."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import math

from src.v03c import wilson_interval

from .boundary import BoundaryEstimator


def build_n0_transfer_hypothesis(task, runs: list[dict], experiments: list[dict], evidence: list[dict], estimator: BoundaryEstimator) -> dict:
    run_ids = {row["run_id"] for row in runs}
    unique_experiments = {}
    for record in experiments:
        if record.get("run_id") in run_ids:
            key = (record.get("condition_id"), record.get("initialization_seed"), record.get("status"))
            unique_experiments.setdefault(key, record)
    validated = sum(bool((row.get("validated_judgment") or {}).get("validated")) for row in runs)
    aggregate = estimator.estimate(
        "N0_AGGREGATE", "N0", list(unique_experiments.values()), task, bool(validated), "H_BOUNDARY_N0",
    )
    low, high = wilson_interval(validated, len(runs))
    decisions = Counter(row.get("decision") for row in evidence if row.get("run_id") in run_ids)
    region = aggregate.candidate_boundary_region
    region_text = "unresolved" if region is None else f"depths {region[0]} and {region[1]}"
    claim = (
        f"Within frozen {task.task_id}, the topology-associated VQE energy-error contrast changes most strongly "
        f"between {region_text}; at the deepest explored depth the direction is {aggregate.effect_direction}."
    )
    return {
        "hypothesis_id": "H_BOUNDARY_N0", "status": "PRELIMINARY_SUPPORT", "claim": claim,
        "scope": {"task_id": task.task_id, "depths": sorted({int(row['depth']) for row in task.experiment_pool}), "ansatz_family": "HEA", "environment": "N0_NOISELESS"},
        "source": "PROGRAMMATIC_RECONSTRUCTION_FROM_FROZEN_V03B_V03C_BOUNDARY_TRACES",
        "source_run_ids": sorted(run_ids), "validated_runs": validated, "total_runs": len(runs),
        "validated_rate": validated / len(runs), "wilson_95_ci": [low, high],
        "boundary_signature": aggregate.to_dict(),
        "supporting_evidence_ids": sorted(row["evidence_id"] for row in evidence if row.get("run_id") in run_ids and row.get("decision") == "SUPPORT"),
        "counterexample_evidence_ids": sorted(row["evidence_id"] for row in evidence if row.get("run_id") in run_ids and row.get("decision") == "COUNTEREXAMPLE"),
        "decision_counts": dict(sorted(decisions.items())),
        "uncertainty": {"validated_rate_wilson_95_ci": [low, high], "signature_standard_error_max": aggregate.uncertainty},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
