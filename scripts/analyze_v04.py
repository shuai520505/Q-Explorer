"""Deterministically analyze frozen N0/N1/N2/N3 Boundary runs."""

from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean, median
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.v03 import TaskSuite
from src.v03d import EvidenceGraph
from src.v04 import (
    BoundaryEstimator, BoundarySignature, V04Protocol, audit_boundary_run,
    classify_noise_level, wilson_interval,
)

RESULT = ROOT / "results" / "v04"
FIGURE = RESULT / "figures"


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def csv_value(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (list, dict, tuple)) else value


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    columns = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows({key: csv_value(row.get(key)) for key in columns} for row in rows)


def reference_signature(payload: dict) -> BoundarySignature:
    row = dict(payload)
    row["candidate_boundary_region"] = tuple(row["candidate_boundary_region"]) if row.get("candidate_boundary_region") else None
    row["contrast_by_depth"] = tuple(row.get("contrast_by_depth", []))
    row["supporting_experiment_ids"] = tuple(row.get("supporting_experiment_ids", []))
    row["counterexample_ids"] = tuple(row.get("counterexample_ids", []))
    return BoundarySignature(**row)


def exact_noisy_runs(graph: EvidenceGraph, protocol: V04Protocol, level: str, strategy: str = "llm") -> list[dict]:
    rows = [
        row for row in graph.records["runs"]
        if row.get("event") in {"END", "FAILED"} and row.get("task_id") == protocol.data["target_task_id"]
        and row.get("noise_level_id") == level and row.get("strategy") == strategy
        and row.get("v04_protocol_hash") == protocol.sha256
    ]
    unique = {row["run_id"]: row for row in rows}
    if strategy == "llm":
        expected_seeds = set(protocol.data["run_seeds"][level])
        actual_seeds = {int(row["run_seed"]) for row in unique.values()}
        if len(unique) != protocol.data["runs_per_noise_level"] or actual_seeds != expected_seeds:
            raise RuntimeError(f"{level} frozen-run mismatch: count={len(unique)}, seeds={sorted(actual_seeds)}")
    return sorted(unique.values(), key=lambda row: (row.get("run_seed") is None, row.get("run_seed") or 0, row["run_id"]))


def aggregate_level(level: str, rows: list[dict], reference: BoundarySignature, thresholds: dict) -> tuple[dict, dict]:
    total = len(rows)
    validated = sum(row["validated_original"] for row in rows)
    scientific = sum(row["scientifically_validated"] for row in rows)
    process_valid = sum(row["scientific_process_valid"] for row in rows)
    retained = sum(row["boundary_retained"] for row in rows)
    resolved_rows = [row for row in rows if row["signature_resolved"]]
    no_shift = sum(row["shift_category"] == "NO_SHIFT" for row in resolved_rows)
    magnitudes = [float(row["effect_magnitude"]) for row in resolved_rows if row["effect_magnitude"] is not None]
    uncertainties = [float(row["uncertainty"]) for row in rows if row["uncertainty"] is not None]
    counterexamples = sum(row["new_counterexample"] for row in rows)
    revisions = sum(int(row["revision_count"]) for row in rows)
    attributed = sum(int(row["evidence_attributed_revision_count"]) for row in rows)
    valid_ci = wilson_interval(validated, total)
    scientific_ci = wilson_interval(scientific, total)
    magnitude_ratio = None
    if magnitudes and reference.effect_magnitude:
        magnitude_ratio = median(magnitudes) / float(reference.effect_magnitude)
    metrics = {
        "scientifically_validated_rate": scientific / total,
        "boundary_retention_rate": retained / total,
        "resolved_signature_rate": len(resolved_rows) / total,
        "no_shift_rate_among_resolved": no_shift / len(resolved_rows) if resolved_rows else 0.0,
        "median_effect_magnitude_ratio": magnitude_ratio,
        "counterexample_emergence_rate": counterexamples / total,
    }
    signal = {"primary": "PRESERVED", "secondary": []} if level == "N0" else classify_noise_level(metrics, thresholds)
    aggregate = {
        "noise_level": level, "total_runs": total, "validated_count": validated,
        "validated_rate": validated / total, "validated_ci_low": valid_ci[0], "validated_ci_high": valid_ci[1],
        "scientifically_validated_count": scientific, "scientifically_validated_rate": scientific / total,
        "scientifically_validated_ci_low": scientific_ci[0], "scientifically_validated_ci_high": scientific_ci[1],
        "scientific_process_valid_count": process_valid, "scientific_process_valid_rate": process_valid / total,
        "boundary_retained_count": retained, "boundary_retention_rate": metrics["boundary_retention_rate"],
        "resolved_signature_count": len(resolved_rows), "resolved_signature_rate": metrics["resolved_signature_rate"],
        "no_shift_count": no_shift, "no_shift_rate_among_resolved": metrics["no_shift_rate_among_resolved"],
        "median_effect_magnitude": median(magnitudes) if magnitudes else None,
        "mean_effect_magnitude": mean(magnitudes) if magnitudes else None,
        "median_effect_magnitude_ratio": magnitude_ratio,
        "mean_uncertainty": mean(uncertainties) if uncertainties else None,
        "new_counterexample_count": counterexamples, "counterexample_emergence_rate": metrics["counterexample_emergence_rate"],
        "hypothesis_revision_count": revisions, "evidence_attributed_revision_count": attributed,
        "feedback_changed_action_count": sum(row["feedback_changed_action"] for row in rows),
        "invalid_run_count": sum("INVALID_ACTION" in row["failure_modes"] for row in rows),
        "vqe_runs_consumed": sum(int(row["budget_spent"]) for row in rows),
        "shift_counts": dict(sorted(Counter(row["shift_category"] for row in rows).items())),
        "effect_direction_counts": dict(sorted(Counter(row["effect_direction"] for row in rows).items())),
        "held_out_direction_counts": dict(sorted(Counter(row["held_out_result"] for row in rows).items())),
        "primary_status": signal["primary"], "secondary_signals": signal["secondary"],
    }
    return aggregate, signal


def verify_history(before: dict) -> dict[str, bool]:
    checks = {}
    for group, details in before["groups"].items():
        current = {}
        for relative in details["files"]:
            path = ROOT / relative
            current[relative] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "MISSING"
        checks[group] = current == details["files"]
    return checks


def choose_hardware_candidates(audits: list[dict], graph: EvidenceGraph, task, maximum: int) -> list[dict]:
    selected: list[tuple[str, dict]] = []
    shifted = [row for row in audits if row["shift_magnitude"] is not None and row["shift_magnitude"] > 0]
    if shifted:
        selected.append(("largest_resolved_boundary_shift", sorted(shifted, key=lambda row: (-row["shift_magnitude"], row["noise_level"], row["run_id"]))[0]))
    retained = [row for row in audits if row["boundary_retained"]]
    if retained:
        selected.append(("scientifically_preserved_at_highest_noise", sorted(retained, key=lambda row: (-int(row["noise_level"][1:]), row["run_id"]))[0]))
    counterexamples = [row for row in audits if row["new_counterexample"]]
    if counterexamples:
        selected.append(("first_noise_induced_counterexample", sorted(counterexamples, key=lambda row: (row["noise_level"], row["run_id"]))[0]))

    candidates = []
    seen = set()
    conditions = {row["condition_id"]: row for row in task.experiment_pool}
    for rule, row in selected:
        if row["run_id"] in seen or len(candidates) >= maximum:
            continue
        seen.add(row["run_id"])
        region = set(row["candidate_boundary_region"] or [])
        experiments = [
            item for item in graph.records["experiments"]
            if item.get("run_id") == row["run_id"] and item.get("condition_id") in conditions
            and (not region or int(conditions[item["condition_id"]]["depth"]) in region)
        ]
        candidates.append({
            "selection_rule": rule, "run_id": row["run_id"], "noise_level": row["noise_level"],
            "hamiltonian_id": sorted({item["hamiltonian_id"] for item in experiments}),
            "ansatz_configs": sorted({(int(item["depth"]), item["entanglement"]) for item in experiments}),
            "n0_behavior": {"region": [2, 3], "direction": "RING_WORSE", "held_out": "RING_BETTER"},
            "noisy_behavior": {"region": row["candidate_boundary_region"], "direction": row["effect_direction"], "held_out": row["held_out_result"]},
            "why_scientifically_informative": "Tests whether the synthetic-noise boundary location and direction transfer to hardware under an explicitly paired HEA comparison.",
            "expected_hardware_observation": "A paired linear/ring contrast resolves with the selected run's boundary direction and region.",
            "falsification_condition": "The paired hardware contrast is unresolved or has a different direction/transition region.",
        })
    return candidates


def make_figures(aggregates: list[dict], noisy_audits: list[dict]) -> list[str]:
    FIGURE.mkdir(parents=True, exist_ok=True)
    levels = [row["noise_level"] for row in aggregates]
    rates = [row["scientifically_validated_rate"] for row in aggregates]
    lows = [rate - row["scientifically_validated_ci_low"] for rate, row in zip(rates, aggregates)]
    highs = [row["scientifically_validated_ci_high"] - rate for rate, row in zip(rates, aggregates)]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(levels, rates, yerr=[lows, highs], fmt="o-", capsize=5)
    ax.set_ylim(0, 1.02); ax.set_ylabel("Scientifically validated boundary rate")
    ax.set_xlabel("Synthetic noise level"); ax.set_title("Boundary validity under frozen synthetic noise")
    fig.tight_layout(); one = FIGURE / "figure1_scientific_boundary_rate.png"; fig.savefig(one, dpi=180); plt.close(fig)

    categories = ["NO_SHIFT", "SMALL_SHIFT", "LARGE_SHIFT", "UNRESOLVED"]
    fig, ax = plt.subplots(figsize=(8, 5)); bottom = [0, 0, 0, 0]
    for category in categories:
        values = [row["shift_counts"].get(category, 0) / row["total_runs"] for row in aggregates]
        ax.bar(levels, values, bottom=bottom, label=category)
        bottom = [left + right for left, right in zip(bottom, values)]
    ax.set_ylim(0, 1); ax.set_ylabel("Run fraction"); ax.set_title("Programmatic boundary shift categories"); ax.legend()
    fig.tight_layout(); two = FIGURE / "figure2_boundary_shift.png"; fig.savefig(two, dpi=180); plt.close(fig)

    rates = [sum(row["new_counterexample"] for row in noisy_audits if row["noise_level"] == level) / 15 for level in ("N1", "N2", "N3")]
    fig, ax = plt.subplots(figsize=(8, 5)); ax.bar(("N1", "N2", "N3"), rates)
    ax.set_ylim(0, 1); ax.set_ylabel("New counterexample rate"); ax.set_xlabel("Synthetic noise level")
    ax.set_title("Noise-induced counterexamples relative to H_BOUNDARY_N0")
    fig.tight_layout(); three = FIGURE / "figure3_counterexample_rate.png"; fig.savefig(three, dpi=180); plt.close(fig)
    return [str(path.relative_to(ROOT)) for path in (one, two, three)]


def main() -> int:
    protocol = V04Protocol.load(ROOT / "configs" / "frozen_v04.yaml")
    checks = protocol.verify_workspace(ROOT)
    if not all(checks.values()):
        raise RuntimeError(f"Frozen workspace mismatch: {[key for key, value in checks.items() if not value]}")
    task = next(task for task in TaskSuite(ROOT / protocol.data["task_suite_path"]).tasks if task.task_id == protocol.data["target_task_id"])
    transfer = json.loads((ROOT / protocol.data["transfer_hypothesis_path"]).read_text(encoding="utf-8"))
    reference = reference_signature(transfer["boundary_signature"])
    estimator = BoundaryEstimator(
        protocol.data["boundary_estimator"]["absolute_effect_deadband"],
        protocol.data["boundary_estimator"]["minimum_boundary_change"],
    )
    historical = EvidenceGraph.from_trace_roots((ROOT / "traces" / "v03", ROOT / "traces" / "v03c"))
    noisy = EvidenceGraph.from_trace_roots((ROOT / "traces" / "v04",))
    n0_runs = [historical.get_run(run_id) for run_id in transfer["source_run_ids"]]
    if any(row.get("status") == "MISSING_LINK" for row in n0_runs):
        raise RuntimeError("A frozen N0 Boundary run is missing")
    n0_audits = [audit_boundary_run(historical, run, task, estimator, reference, protocol.data["boundary_estimator"]["small_shift_max"]) for run in n0_runs]
    noisy_runs = [run for level in protocol.data["noise_level_ids"] for run in exact_noisy_runs(noisy, protocol, level)]
    noisy_audits = [audit_boundary_run(noisy, run, task, estimator, reference, protocol.data["boundary_estimator"]["small_shift_max"]) for run in noisy_runs]

    by_level = {"N0": n0_audits}
    by_level.update({level: [row for row in noisy_audits if row["noise_level"] == level] for level in protocol.data["noise_level_ids"]})
    aggregates, signals = [], {}
    for level in ("N0", "N1", "N2", "N3"):
        aggregate, signal = aggregate_level(level, by_level[level], reference, protocol.data["discovery_signals"]["thresholds"])
        aggregates.append(aggregate); signals[level] = signal

    flat_audits = n0_audits + noisy_audits
    write_jsonl(RESULT / "boundary_signatures.jsonl", [row["signature"] for row in flat_audits])
    write_csv(RESULT / "boundary_by_noise_level.csv", aggregates)
    shift_columns = ["run_id", "noise_level", "run_seed", "validated_original", "scientifically_validated", "candidate_boundary_region", "boundary_location", "effect_direction", "effect_magnitude", "uncertainty", "held_out_result", "shift_category", "shift_magnitude", "boundary_retained"]
    write_csv(RESULT / "boundary_shift_analysis.csv", [{key: row[key] for key in shift_columns} for row in flat_audits])
    counter_columns = ["run_id", "noise_level", "new_counterexample", "new_counterexample_evidence_ids", "new_counterexample_experiment_ids", "direction_retained", "held_out_retained"]
    write_csv(RESULT / "counterexample_analysis.csv", [{key: row[key] for key in counter_columns} for row in noisy_audits])
    revision_columns = ["run_id", "noise_level", "revision_count", "evidence_attributed_revision_count", "evidence_attributed_revision_ids", "validated_original", "scientifically_validated"]
    write_csv(RESULT / "hypothesis_revision_analysis.csv", [{key: row[key] for key in revision_columns} for row in noisy_audits])

    rule_runs = exact_noisy_runs(noisy, protocol, "N2", "rule_based")
    rule_audits = [audit_boundary_run(noisy, run, task, estimator, reference, protocol.data["boundary_estimator"]["small_shift_max"]) for run in rule_runs]
    candidates = choose_hardware_candidates(noisy_audits, noisy, task, protocol.data["hardware_candidate_selection"]["maximum_cases"])
    write_json(RESULT / "hardware_validation_candidates.json", {"count": len(candidates), "candidates": candidates})
    figures = make_figures(aggregates, noisy_audits)
    before = json.loads((ROOT / protocol.data["history_snapshot_before_path"]).read_text(encoding="utf-8"))
    history = verify_history(before)
    total_token_usage = Counter()
    for run in noisy_runs:
        total_token_usage.update(run.get("token_usage") or {})
    preregistration_commits = {
        row["git_commit"] for row in noisy.records["runs"]
        if row.get("event") == "START" and row.get("v04_protocol_hash") == protocol.sha256 and row.get("git_commit")
    }
    if len(preregistration_commits) != 1:
        raise RuntimeError(f"Expected one V0.4 preregistration commit, found {sorted(preregistration_commits)}")
    summary = {
        "protocol_hash": protocol.sha256, "preregistration_commit": next(iter(preregistration_commits)),
        "scientific_question": protocol.data["scientific_question"], "target_task_id": task.task_id,
        "transfer_hypothesis_id": transfer["hypothesis_id"], "noise_model": "synthetic_depolarizing_1q_2q_plus_symmetric_readout",
        "shots": None, "levels": {row["noise_level"]: row for row in aggregates}, "discovery_signals": signals,
        "rule_based_n2_process_reference": rule_audits,
        "new_live_llm_runs": len(noisy_runs), "new_aer_vqe_runs": sum(row["budget_spent"] for row in noisy_audits) + sum(row["budget_spent"] for row in rule_audits),
        "live_llm_api_calls": sum(int(run.get("llm_calls", 0)) for run in noisy_runs),
        "token_usage": dict(sorted(total_token_usage.items())), "estimated_api_cost": "NOT_AVAILABLE_FROM_PROVIDER_TRACE",
        "revision_attribution": {
            "total_revisions": sum(row["revision_count"] for row in noisy_audits),
            "evidence_attributed_revisions": sum(row["evidence_attributed_revision_count"] for row in noisy_audits),
        },
        "failure_modes": dict(sorted(Counter(mode for row in noisy_audits for mode in row["failure_modes"]).items())),
        "invalid_runs_retained": sum("INVALID_ACTION" in row["failure_modes"] for row in noisy_audits),
        "history_immutable": history, "hardware_validation_candidates": candidates,
        "v05_recommended": bool(candidates and any(signals[level]["primary"] in {"PRESERVED", "SHIFTED", "COUNTEREXAMPLE_EMERGED"} for level in ("N1", "N2", "N3"))),
        "figures": figures, "figure4_generated": False,
        "figure4_omission_reason": "N0/N1/N2/N3 are independent research runs, not a single longitudinal trajectory; no cross-level trajectory was fabricated.",
        "live_llm_used": True, "model": protocol.data["agent"]["model"], "thinking_mode": protocol.data["agent"]["thinking_mode"],
        "qiskit_aer_used": True, "noise_simulation_used": True, "real_quantum_hardware_used": False,
    }
    write_json(RESULT / "boundary_robustness_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
