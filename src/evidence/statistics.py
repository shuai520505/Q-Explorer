"""Seed-aware aggregation used by both result summaries and EvidenceJudge."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

import numpy as np


GROUP_FIELDS = ("hamiltonian_id", "depth", "entanglement")


def aggregate_experiments(records: Iterable[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for record in records:
        groups[tuple(record[field] for field in GROUP_FIELDS)].append(record)

    aggregates = []
    for key in sorted(groups):
        runs = groups[key]
        successful = [run for run in runs if run.get("status") == "SUCCESS" and run.get("energy_error") is not None]
        errors = np.asarray([run["energy_error"] for run in successful], dtype=float)
        attempted = len(runs)
        converged = sum(bool(run.get("converged")) for run in runs)
        aggregate = dict(zip(GROUP_FIELDS, key, strict=True))
        aggregate.update(
            {
                "attempted_seeds": attempted,
                "number_of_seeds": len(successful),
                "failed_executions": attempted - len(successful),
                "mean_energy_error": float(np.mean(errors)) if len(errors) else None,
                "std_energy_error": float(np.std(errors, ddof=1)) if len(errors) > 1 else (0.0 if len(errors) == 1 else None),
                "variance_energy_error": float(np.var(errors, ddof=1)) if len(errors) > 1 else (0.0 if len(errors) == 1 else None),
                "median_energy_error": float(np.median(errors)) if len(errors) else None,
                "convergence_rate": float(converged / attempted) if attempted else 0.0,
                "failure_rate": float(1.0 - converged / attempted) if attempted else 1.0,
            }
        )
        aggregates.append(aggregate)
    return aggregates

