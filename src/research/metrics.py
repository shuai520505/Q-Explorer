"""Four transparent V0.2 comparison metrics and agent failure-mode checks."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean


STABLE_DECISIONS = {"COUNTEREXAMPLE"}


def compute_run_metrics(
    run: dict,
    actions: list[dict],
    experiments: list[dict],
    evidence: list[dict],
    adequate_replication: int,
) -> dict:
    """Compute only the four frozen V0.2 metrics from one completed run."""

    run_id = run["run_id"]
    run_actions = sorted(
        (item for item in actions if item.get("run_id") == run_id and item.get("validation_status") == "VALID"),
        key=lambda item: int(item["round"]),
    )
    run_experiments = [
        item for item in experiments
        if item.get("run_id") == run_id and item.get("source_version") != "0.1"
    ]
    run_evidence = sorted(
        (item for item in evidence if item.get("run_id") == run_id and int(item.get("round", 0)) > 0),
        key=lambda item: int(item["round"]),
    )

    stable = next((item for item in run_evidence if item.get("decision") in STABLE_DECISIONS), None)
    experiments_to_stable = None
    if stable is not None:
        experiments_to_stable = sum(
            int(item.get("budget_cost", 0)) for item in run_actions if int(item["round"]) <= int(stable["round"])
        )

    counterexamples = [item for item in run_evidence if item.get("decision") == "COUNTEREXAMPLE"]
    redundant = _redundant_actions(run_actions, adequate_replication)
    held_out = [item for item in run_evidence if item.get("held_out")]
    held_out_paired = [item for item in held_out if "INSUFFICIENT_REPLICATION" not in item.get("reason_codes", [])]
    held_out_result = held_out_paired[-1]["decision"] if held_out_paired else "NOT_COMPLETED"

    unique_conditions = {
        (
            item.get("experiment", {}).get("hamiltonian_id"),
            item.get("experiment", {}).get("depth"),
            item.get("experiment", {}).get("entanglement"),
        )
        for item in run_actions
        if item.get("experiment")
    }
    action_types = {item.get("action_type") for item in run_actions}
    feedback_responses = defaultdict(set)
    for item in run_actions:
        label = item.get("responding_to_evidence_label")
        if label:
            target = item.get("experiment") or {}
            feedback_responses[label].add((item.get("action_type"), target.get("hamiltonian_id"), target.get("depth"), target.get("entanglement")))
    response_targets = {target for targets in feedback_responses.values() for target in targets}
    random_search_degeneration = bool(
        run.get("strategy_category") == "active_agent"
        and (len(action_types) < 2 or len(unique_conditions) < 2 or (len(feedback_responses) >= 2 and len(response_targets) < 2))
    )

    return {
        "run_id": run_id,
        "strategy": run["strategy"],
        "strategy_category": run["strategy_category"],
        "budget": int(run["budget"]),
        "budget_spent": int(run["budget_spent"]),
        "rounds_completed": int(run["rounds_completed"]),
        "experiments_to_stable_judgment": experiments_to_stable,
        "counterexample_discovery": bool(counterexamples),
        "counterexamples_found": len(counterexamples),
        "redundant_experiment_ratio": float(sum(item["budget_cost"] for item in redundant) / max(int(run["budget_spent"]), 1)),
        "redundant_action_ids": [item["action_id"] for item in redundant],
        "held_out_replication": held_out_result,
        "held_out_reason_codes": held_out_paired[-1].get("reason_codes", []) if held_out_paired else [],
        "unique_conditions": len(unique_conditions),
        "action_type_diversity": len(action_types),
        "optimization_drift": bool(run.get("optimization_drift")),
        "random_search_degeneration": random_search_degeneration,
        "invalid_actions": int(run.get("invalid_actions", 0)),
        "successful_vqe_runs": sum(item.get("status") == "SUCCESS" for item in run_experiments),
        "failed_vqe_runs": sum(item.get("status") == "FAILED" for item in run_experiments),
    }


def _redundant_actions(actions: list[dict], adequate_replication: int) -> list[dict]:
    prior_runs: dict[tuple, int] = defaultdict(int)
    redundant = []
    for action in actions:
        experiment = action.get("experiment")
        if not experiment:
            continue
        key = (experiment["hamiltonian_id"], int(experiment["depth"]), experiment["entanglement"])
        cost = int(action.get("budget_cost", len(experiment.get("seed_group", []))))
        justified_replicate = action.get("action_type") == "REPLICATE" and prior_runs[key] < adequate_replication
        if prior_runs[key] >= adequate_replication and not justified_replicate:
            redundant.append(action)
        prior_runs[key] += cost
    return redundant


def aggregate_random_metrics(rows: list[dict]) -> dict:
    random_rows = [row for row in rows if row["strategy_category"] == "random"]
    stable_values = [row["experiments_to_stable_judgment"] for row in random_rows if row["experiments_to_stable_judgment"] is not None]
    held_out_values = [row["held_out_replication"] for row in random_rows]
    return {
        "strategy": "random_mean",
        "strategy_category": "random_aggregate",
        "replicate_runs": len(random_rows),
        "budget": random_rows[0]["budget"] if random_rows else None,
        "budget_spent": mean(row["budget_spent"] for row in random_rows) if random_rows else None,
        "experiments_to_stable_judgment": mean(stable_values) if stable_values else None,
        "counterexample_discovery": any(row["counterexample_discovery"] for row in random_rows),
        "redundant_experiment_ratio": mean(row["redundant_experiment_ratio"] for row in random_rows) if random_rows else None,
        "held_out_replication": "CONSISTENT_" + held_out_values[0] if held_out_values and len(set(held_out_values)) == 1 else "MIXED",
    }

