"""Deterministic outcome/process audit for frozen V0.4 Boundary runs."""

from __future__ import annotations

import math

from src.v04.boundary import BoundaryEstimator, BoundarySignature, shift_category


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Return a two-sided Wilson binomial interval (95% for the default z)."""

    if total <= 0 or not 0 <= successes <= total:
        raise ValueError("Wilson interval requires 0 <= successes <= total and total > 0")
    rate = successes / total
    denominator = 1.0 + z * z / total
    centre = (rate + z * z / (2.0 * total)) / denominator
    margin = z * math.sqrt(rate * (1.0 - rate) / total + z * z / (4.0 * total * total)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _complete_evidence_link(graph, action: dict, evidence_rows: list[dict]) -> bool:
    linked = [row for row in evidence_rows if row.get("action_id") == action.get("action_id")]
    if len(linked) != 1 or not linked[0].get("experiment_ids"):
        return False
    for experiment_id in linked[0]["experiment_ids"]:
        experiment = graph.get_experiment(experiment_id)
        if experiment.get("status") == "MISSING_LINK" or experiment.get("run_id") != action.get("run_id"):
            return False
    return True


def audit_boundary_run(
    graph,
    run: dict,
    task,
    estimator: BoundaryEstimator,
    reference: BoundarySignature,
    small_shift_max: float,
) -> dict:
    """Apply the same frozen process checks to N0 and noisy runs."""

    run_id = run["run_id"]
    actions = sorted(
        (row for row in graph.records["actions"] if row.get("run_id") == run_id),
        key=lambda row: int(row.get("round", 0)),
    )
    evidence = sorted(
        (row for row in graph.records["evidence"] if row.get("run_id") == run_id),
        key=lambda row: int(row.get("round", 0)),
    )
    experiments = [row for row in graph.records["experiments"] if row.get("run_id") == run_id]
    condition_by_id = {row["condition_id"]: row for row in task.experiment_pool}
    probe_actions = [row for row in actions if row.get("action_type") == "BOUNDARY_PROBE"]
    complete_probe_ids = [row["action_id"] for row in probe_actions if _complete_evidence_link(graph, row, evidence)]
    probe_depths = sorted({
        int(condition_by_id[row["condition_id"]]["depth"])
        for row in probe_actions
        if row.get("condition_id") in task.exploration_set and row.get("condition_id") in condition_by_id
    })
    held_out_complete_ids = []
    minimum_seeds = int(task.success_criteria["minimum_seeds_per_condition"])
    for condition_id in task.held_out_set:
        rows = [row for row in evidence if row.get("held_out") and row.get("condition_id") == condition_id]
        if len(rows) == 1 and len(rows[0].get("experiment_ids", [])) >= minimum_seeds:
            action = next((item for item in actions if item.get("action_id") == rows[0].get("action_id")), None)
            if action and _complete_evidence_link(graph, action, evidence):
                held_out_complete_ids.append(rows[0]["evidence_id"])

    validated = bool(run.get("validated_judgment", {}).get("validated"))
    hypothesis_id = run.get("transfer_hypothesis_id") or "H_BOUNDARY_N0"
    noise_level = run.get("noise_level_id") or "N0"
    signature = estimator.estimate(run_id, noise_level, experiments, task, validated, hypothesis_id)
    complete_probe_chain = bool(probe_actions) and len(complete_probe_ids) == len(probe_actions)
    probe_depth_coverage = len(probe_depths) >= 2
    signature_resolved = signature.candidate_boundary_region is not None and signature.effect_direction not in {"UNRESOLVED", "NO_CLEAR_EFFECT"}
    held_out_complete = bool(held_out_complete_ids) and len(held_out_complete_ids) == len(task.held_out_set)
    process_valid = bool(complete_probe_chain and probe_depth_coverage and signature_resolved and held_out_complete)
    scientifically_validated = bool(validated and process_valid)
    shift, shift_magnitude = shift_category(reference, signature, small_shift_max)
    direction_retained = signature.effect_direction == reference.effect_direction
    held_out_retained = signature.held_out_result == reference.held_out_result
    location_retained = shift == "NO_SHIFT"
    boundary_retained = bool(scientifically_validated and direction_retained and held_out_retained and location_retained)

    new_counterexample_evidence_ids: list[str] = []
    reference_rows = {int(row["depth"]): row for row in reference.contrast_by_depth}
    noisy_rows = {int(row["depth"]): row for row in signature.contrast_by_depth}
    reference_depth = max(reference_rows) if reference_rows else None
    comparable_reference = reference_rows.get(reference_depth) if reference_depth is not None else None
    comparable_noisy = noisy_rows.get(reference_depth) if reference_depth is not None else None
    exploration_direction_changed = bool(
        comparable_reference and comparable_noisy
        and comparable_noisy["direction"] not in {"UNRESOLVED", "NO_CLEAR_EFFECT"}
        and comparable_noisy["direction"] != comparable_reference["direction"]
    )
    if exploration_direction_changed:
        new_counterexample_evidence_ids.extend(
            row["evidence_id"] for row in evidence
            if not row.get("held_out") and row.get("evidence_id")
            and row.get("condition_id") in condition_by_id
            and int(condition_by_id[row["condition_id"]]["depth"]) == reference_depth
        )
    if signature.held_out_result not in {"NOT_RESOLVED", "NO_CLEAR_EFFECT"} and not held_out_retained:
        new_counterexample_evidence_ids.extend(
            row["evidence_id"] for row in evidence if row.get("held_out") and row.get("evidence_id")
        )
    new_counterexample_evidence_ids = sorted(set(new_counterexample_evidence_ids))
    new_counterexample_experiment_ids = sorted({
        experiment_id
        for row in evidence
        if row.get("evidence_id") in new_counterexample_evidence_ids
        for experiment_id in row.get("experiment_ids", [])
    })

    revisions = graph.revisions_for_run(run_id)
    attributed_revisions = []
    for revision in revisions:
        identifiers = list(revision.get("triggering_evidence_ids") or [])
        linked = [graph.get_evidence(identifier) for identifier in identifiers]
        if identifiers and all(
            row.get("status") != "MISSING_LINK"
            and row.get("run_id") == run_id
            and int(row.get("round", 0)) < int(revision.get("round", 0))
            for row in linked
        ):
            attributed_revisions.append(revision.get("revision_id") or f"{run_id}:round:{revision.get('round')}")

    return {
        "run_id": run_id, "noise_level": noise_level, "strategy": run.get("strategy"),
        "run_seed": run.get("run_seed"), "budget_spent": int(run.get("budget_spent", 0)),
        "validated_original": validated, "scientific_process_valid": process_valid,
        "scientifically_validated": scientifically_validated,
        "complete_boundary_probe_chain": complete_probe_chain,
        "probe_depth_coverage_met": probe_depth_coverage, "probe_depths": probe_depths,
        "probe_action_ids": [row["action_id"] for row in probe_actions],
        "complete_probe_action_ids": complete_probe_ids,
        "held_out_evidence_complete": held_out_complete,
        "held_out_evidence_ids": held_out_complete_ids,
        "candidate_boundary_region": None if signature.candidate_boundary_region is None else list(signature.candidate_boundary_region),
        "boundary_location": signature.boundary_location, "effect_direction": signature.effect_direction,
        "effect_magnitude": signature.effect_magnitude, "uncertainty": signature.uncertainty,
        "held_out_result": signature.held_out_result, "signature_resolved": signature_resolved,
        "shift_category": shift, "shift_magnitude": shift_magnitude,
        "direction_retained": direction_retained, "held_out_retained": held_out_retained,
        "boundary_retained": boundary_retained,
        "new_counterexample": bool(new_counterexample_evidence_ids),
        "new_counterexample_evidence_ids": new_counterexample_evidence_ids,
        "new_counterexample_experiment_ids": new_counterexample_experiment_ids,
        "revision_count": len(revisions), "evidence_attributed_revision_count": len(attributed_revisions),
        "evidence_attributed_revision_ids": attributed_revisions,
        "feedback_changed_action": bool(run.get("feedback_changed_action")),
        "failure_modes": list(run.get("failure_modes") or []), "signature": signature.to_dict(),
    }
