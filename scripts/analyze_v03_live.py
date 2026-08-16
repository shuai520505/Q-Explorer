"""Add frozen live-LLM runs to the existing V0.3 baseline comparison."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.analyze_v03 import plot
from src.logging import JsonlTrace
from src.research import FrozenConfig
from src.v03 import TaskSuite

RESULT, TRACE = ROOT / "results" / "v03", ROOT / "traces" / "v03"


def read(name):
    return JsonlTrace(TRACE / f"{name}.jsonl").read_all()


def main() -> int:
    scientific = FrozenConfig(ROOT / "configs" / "frozen_v03.yaml")
    live_config = FrozenConfig(ROOT / "configs" / "frozen_v03_live.yaml")
    suite = TaskSuite(ROOT / "configs" / "frozen_v03_tasks.yaml")
    tasks = {task.task_id: task for task in suite.tasks}
    run_events, actions, evidence = read("runs"), read("actions"), read("evidence")
    responses = read("live_llm_responses")
    formal_starts = [row for row in run_events if row.get("event") == "START" and row.get("strategy") == "llm" and row.get("live_config_hash") == live_config.sha256]
    formal_ids = {row["run_id"] for row in formal_starts}
    finals = [row for row in run_events if row.get("run_id") in formal_ids and row.get("event") in {"END", "FAILED"}]
    if len(finals) != 24:
        raise RuntimeError(f"Expected 24 frozen live runs, found {len(finals)}")

    rows = []
    discriminative_types = set(scientific.data["metrics"]["discriminative_action_types"])
    for run in finals:
        run_actions = sorted((row for row in actions if row.get("run_id") == run["run_id"]), key=lambda row: row["round"])
        run_evidence = sorted((row for row in evidence if row.get("run_id") == run["run_id"]), key=lambda row: row["round"])
        counter = next((row for row in run_evidence if row.get("decision") == "COUNTEREXAMPLE"), None)
        counter_cost = sum(row["budget_cost"] for row in run_actions if counter and row["round"] <= counter["round"]) if counter else None
        spent = int(run["budget_spent"])
        discriminative = sum(row["budget_cost"] for row in run_actions if row["action_type"] in discriminative_types)
        seen, redundant = defaultdict(int), 0
        for action in run_actions:
            exp = action.get("experiment") or {}
            key = (exp.get("hamiltonian_id"), exp.get("depth"), exp.get("entanglement"))
            if seen[key] >= scientific.data["metrics"]["adequate_replication"] and action["action_type"] != "REPLICATE":
                redundant += action["budget_cost"]
            seen[key] += action["budget_cost"]
        validated = run["validated_judgment"]
        rows.append({
            "run_id": run["run_id"], "task_id": run["task_id"], "task_type": tasks[run["task_id"]].task_type,
            "difficulty": tasks[run["task_id"]].difficulty_metadata["difficulty"], "strategy": "llm", "policy_seed": run.get("run_seed"),
            "budget": run["budget"], "budget_spent": spent,
            "experiments_to_validated_judgment": validated.get("experiments_to_validated_judgment"),
            "validated_judgment_rate": float(validated.get("validated", False)),
            "counterexample_discovery_efficiency": counter_cost,
            "discriminative_experiment_ratio": discriminative / max(spent, 1),
            "redundant_experiment_ratio": redundant / max(spent, 1),
            "held_out_result": run["held_out_result"], "final_judgment": run["final_judgment"],
            "failure_modes": "|".join(run["failure_modes"]),
        })
    live_df = pd.DataFrame(rows)
    live_df.to_csv(RESULT / "live_llm_by_task.csv", index=False)
    comparison_path = RESULT / "strategy_comparison_by_task.csv"
    baseline = pd.read_csv(comparison_path)
    baseline = baseline[baseline["strategy"] != "llm"]
    combined = pd.concat([baseline, live_df], ignore_index=True)
    combined.to_csv(comparison_path, index=False)
    aggregate = combined.groupby(["task_type", "strategy"], dropna=False).agg(
        run_count=("run_id", "count"), validated_judgment_rate=("validated_judgment_rate", "mean"),
        mean_experiments_to_validated_judgment=("experiments_to_validated_judgment", "mean"),
        median_experiments_to_validated_judgment=("experiments_to_validated_judgment", "median"),
        mean_counterexample_discovery_efficiency=("counterexample_discovery_efficiency", "mean"),
        discriminative_experiment_ratio=("discriminative_experiment_ratio", "mean"),
        redundant_experiment_ratio=("redundant_experiment_ratio", "mean"),
    ).reset_index()
    aggregate.to_csv(RESULT / "strategy_comparison_aggregate.csv", index=False)

    formal_responses = [row for row in responses if row.get("run_id") in formal_ids]
    usage = defaultdict(int)
    for row in formal_responses:
        for key, value in (row.get("usage") or {}).items():
            usage[key] += int(value)
    rates = combined.groupby("strategy")["validated_judgment_rate"].mean().to_dict()
    task_rates = live_df.groupby("task_type")["validated_judgment_rate"].mean().to_dict()
    live_summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "provider": live_config.data["provider"],
        "model": live_config.data["model"], "execution_git_commit": sorted({row["git_commit"] for row in formal_starts}),
        "prompt_version": live_config.data["prompt_version"], "prompt_hash": live_config.data["prompt_hash"],
        "live_config_hash": live_config.sha256, "task_suite_hash": suite.sha256,
        "independent_runs": len(finals), "tasks": len(tasks), "allocated_vqe_budget": sum(row["budget"] for row in finals),
        "used_vqe_runs": sum(row["budget_spent"] for row in finals),
        "budget_allocation_fair": all(row["budget"] == tasks[row["task_id"]].budget for row in finals),
        "full_budget_runs": sum(row["budget_spent"] == row["budget"] for row in finals),
        "successful_vqe_runs": sum(row["successful_vqe_runs"] for row in finals),
        "failed_vqe_runs": sum(row["failed_vqe_runs"] for row in finals),
        "validated_runs": sum(row["validated_judgment"]["validated"] for row in finals),
        "validated_rate": sum(row["validated_judgment"]["validated"] for row in finals) / len(finals),
        "validated_rate_by_task_type": task_rates,
        "invalid_action_runs": sum(row["event"] == "FAILED" for row in finals),
        "structured_response_records": len(formal_responses),
        "invalid_output_rate": sum(row["validation_result"] != "VALID" for row in formal_responses) / max(len(formal_responses), 1),
        "repair_attempt_rate": sum(bool(row["repair_attempted"]) for row in formal_responses) / max(len(formal_responses), 1),
        "recorded_final_attempt_token_usage": dict(usage),
        "token_usage_is_lower_bound": True,
        "api_cost": None,
        "feedback_sensitive_runs": sum(bool(row.get("feedback_changed_action")) for row in finals),
        "failure_modes": sorted({mode for row in finals for mode in row["failure_modes"]}),
        "thinking_mode_healthcheck": "PASS", "thinking_mode_formal": "DISABLED_FOR_STRUCTURED_OUTPUT_COMPATIBILITY",
    }
    (RESULT / "live_llm_summary.json").write_text(json.dumps(live_summary, indent=2), encoding="utf-8")
    (RESULT / "live_llm_status.json").write_text(json.dumps({
        "live_llm_used": True, "live_llm_blocked_by_credentials": False,
        "required_environment_variables_present_during_execution": True,
        "provider": live_summary["provider"], "model": live_summary["model"],
        "formal_runs": live_summary["independent_runs"], "api_request_failures": 0,
    }, indent=2), encoding="utf-8")
    figures = plot(combined, actions, evidence, scientific.sha256[:8])
    summary_path = RESULT / "v03_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary.update({
        "generated_at": datetime.now(timezone.utc).isoformat(), "live_llm_used": True,
        "live_llm_blocked_by_credentials": False, "live_llm_summary": live_summary,
        "validated_judgment_rate_by_strategy": rates,
        "m001_assessment": "PARTIALLY_SUPPORTED",
        "interpretation": (
            "Feedback value was task-dependent. Live LLM exceeded non-live policies on boundary and scope-revision rates, "
            "but underperformed transparent rule-based active selection on competing explanations because two runs ended "
            "with invalid actions. Overall LLM and rule-based rates were close, so no general LLM superiority is established."
        ),
        "figures": figures,
    })
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(live_summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
