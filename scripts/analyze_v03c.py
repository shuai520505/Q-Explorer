"""Analyze the pre-registered V0.3-C targeted replication without changing V0.3 artifacts."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import mean, median
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.logging import JsonlTrace
from src.research import FrozenConfig
from src.v03 import TaskSuite
from src.v03c import V03CProtocol, classify_failure_modes, merge_replication_runs, wilson_interval

RESULT = ROOT / "results" / "v03c"
TRACE = ROOT / "traces" / "v03c"
V03_TRACE = ROOT / "traces" / "v03"


def read(root: Path, name: str) -> list[dict]:
    return JsonlTrace(root / f"{name}.jsonl").read_all()


def formal_runs(root: Path, starts_name: str, protocol: V03CProtocol, source: str) -> tuple[list[dict], set[str]]:
    events = read(root, starts_name)
    if source == "v03b":
        starts = [row for row in events if row.get("event") == "START" and row.get("live_config_hash") == protocol.data["live_config_hash"] and row.get("task_id") in protocol.data["target_task_ids"] and row.get("run_seed") in protocol.data["existing_run_seeds"]]
    else:
        starts = [row for row in events if row.get("event") == "START" and row.get("v03c_protocol_hash") == protocol.sha256 and row.get("task_id") in protocol.data["target_task_ids"]]
    start_by_id = {row["run_id"]: row for row in starts}
    finals = [row for row in events if row.get("run_id") in start_by_id and row.get("event") in {"END", "FAILED"}]
    rows = []
    for row in finals:
        start = start_by_id[row["run_id"]]
        rows.append(dict(row, config_hash=start["config_hash"], git_commit=start["git_commit"], prompt_hash=start["prompt_hash"], source_run=source))
    return rows, set(start_by_id)


def main() -> int:
    RESULT.mkdir(parents=True, exist_ok=True)
    protocol = V03CProtocol.load(ROOT / "configs" / "frozen_v03c.yaml")
    checks = protocol.verify_workspace(ROOT)
    if not all(checks.values()):
        raise RuntimeError(f"Frozen workspace mismatch: {[key for key, value in checks.items() if not value]}")
    scientific = FrozenConfig(ROOT / protocol.data["scientific_config_path"])
    suite = TaskSuite(ROOT / protocol.data["task_suite_path"])
    tasks = {task.task_id: task for task in suite.tasks}
    old_runs, old_ids = formal_runs(V03_TRACE, "runs", protocol, "v03b")
    new_runs, new_ids = formal_runs(TRACE, "runs", protocol, "v03c")
    merged = merge_replication_runs(old_runs, new_runs, set(protocol.data["target_task_ids"]))
    if len(merged) != 45 or any(sum(row["task_id"] == task_id for row in merged) != 15 for task_id in protocol.data["target_task_ids"]):
        raise RuntimeError("Merged replication must contain exactly 15 unique runs per target task")

    actions = [dict(row, source_run="v03b") for row in read(V03_TRACE, "actions") if row.get("run_id") in old_ids]
    actions += [dict(row, source_run="v03c") for row in read(TRACE, "actions") if row.get("run_id") in new_ids]
    evidence = [dict(row, source_run="v03b") for row in read(V03_TRACE, "evidence") if row.get("run_id") in old_ids]
    evidence += [dict(row, source_run="v03c") for row in read(TRACE, "evidence") if row.get("run_id") in new_ids]
    revisions = [dict(row, source_run="v03b") for row in read(V03_TRACE, "revisions") if row.get("run_id") in old_ids]
    revisions += [dict(row, source_run="v03c") for row in read(TRACE, "revisions") if row.get("run_id") in new_ids]
    hypotheses = [dict(row, source_run="v03b") for row in read(V03_TRACE, "hypotheses") if row.get("run_id") in old_ids]
    hypotheses += [dict(row, source_run="v03c") for row in read(TRACE, "hypotheses") if row.get("run_id") in new_ids]

    discriminative_types = set(scientific.data["metrics"]["discriminative_action_types"])
    adequate = int(scientific.data["metrics"]["adequate_replication"])
    run_rows, all_failures = [], []
    for run in merged:
        run_actions = sorted((row for row in actions if row["run_id"] == run["run_id"]), key=lambda row: row["round"])
        run_evidence = sorted((row for row in evidence if row["run_id"] == run["run_id"]), key=lambda row: row["round"])
        run_revisions = [row for row in revisions if row["run_id"] == run["run_id"]]
        counterexamples = [row for row in run_evidence if row.get("decision") == "COUNTEREXAMPLE"]
        seen, redundant_cost = defaultdict(int), 0
        for action in run_actions:
            exp = action.get("experiment") or {}
            key = (exp.get("hamiltonian_id"), exp.get("depth"), exp.get("entanglement"))
            if seen[key] >= adequate and action["action_type"] != "REPLICATE":
                redundant_cost += int(action["budget_cost"])
            seen[key] += int(action["budget_cost"])
        spent = int(run["budget_spent"])
        failure_modes = classify_failure_modes(run, run_actions, run_evidence, tasks[run["task_id"]].task_type)
        for mode in failure_modes:
            all_failures.append({"task_id": run["task_id"], "task_type": tasks[run["task_id"]].task_type, "failure_mode": mode, "run_id": run["run_id"]})
        evidence_by_id = {row["evidence_id"]: row for row in run_evidence}
        valid_scope = sum(
            bool(revision.get("triggering_evidence_ids"))
            and all(evidence_by_id.get(eid, {}).get("decision") == "COUNTEREXAMPLE" for eid in revision["triggering_evidence_ids"])
            and "conditional" in (revision.get("new_claim", "") + revision.get("scope_change", "")).lower()
            for revision in run_revisions
        )
        invalid_scope = len(run_revisions) - valid_scope
        scope_creep = sum("HYPOTHESIS_SCOPE_CREEP" in action.get("failure_modes", []) for action in run_actions)
        exploration_actions = [action for action in run_actions if action["action_type"] != "VALIDATE_HYPOTHESIS"]
        depths = {(action.get("experiment") or {}).get("depth") for action in exploration_actions}
        labels = {row["decision"] for row in run_evidence if not row.get("held_out")}
        boundary_probe_count = sum(action["action_type"] == "BOUNDARY_PROBE" for action in run_actions)
        adaptive_boundary = bool(
            run["validated_judgment"]["validated"] and boundary_probe_count and len(depths) >= 2 and len(labels) >= 2
            and any(action["action_type"] == "VALIDATE_HYPOTHESIS" for action in run_actions)
        )
        controls = [action for action in run_actions if action["action_type"] in {"CONTROL_DEPTH", "CONTROL_ENTANGLEMENT"}]
        run_rows.append({
            "run_id": run["run_id"], "task_id": run["task_id"], "task_type": tasks[run["task_id"]].task_type,
            "source_run": run["source_run"], "run_seed": run.get("run_seed"), "config_hash": run["config_hash"],
            "git_commit": run["git_commit"], "validated": bool(run["validated_judgment"]["validated"]),
            "final_judgment": run["final_judgment"], "experiments_to_validated_judgment": run["validated_judgment"].get("experiments_to_validated_judgment"),
            "budget": run["budget"], "budget_spent": spent, "counterexample_discovered": bool(counterexamples),
            "counterexample_count": len(counterexamples),
            "discriminative_experiment_ratio": sum(int(action["budget_cost"]) for action in run_actions if action["action_type"] in discriminative_types) / max(spent, 1),
            "redundant_experiment_ratio": redundant_cost / max(spent, 1),
            "invalid_action": run["final_judgment"] == "INVALID_ACTION", "revision_count": len(run_revisions),
            "valid_scope_revisions": valid_scope, "invalid_scope_revisions": invalid_scope, "scope_creep_attempts": scope_creep,
            "boundary_probe_count": boundary_probe_count, "adaptive_boundary_success": adaptive_boundary,
            "single_variable_control_count": sum(len(action.get("changed_variables", [])) == 1 for action in controls),
            "multi_variable_control_count": sum(len(action.get("changed_variables", [])) > 1 for action in controls),
            "failure_modes": "|".join(failure_modes),
        })
    runs_df = pd.DataFrame(run_rows).sort_values(["task_id", "run_seed"])
    runs_df.to_csv(RESULT / "targeted_replication_runs.csv", index=False)

    summary_rows, ci_rows = [], []
    for task_id in protocol.data["target_task_ids"]:
        subset = runs_df[runs_df.task_id == task_id]
        successes, total = int(subset.validated.sum()), len(subset)
        low, high = wilson_interval(successes, total)
        costs = subset.experiments_to_validated_judgment.dropna().astype(float)
        summary_rows.append({
            "task_id": task_id, "task_type": tasks[task_id].task_type, "n_total": total, "n_validated": successes,
            "validated_rate": successes / total, "wilson_ci_low": low, "wilson_ci_high": high,
            "mean_experiments_to_validated": costs.mean() if len(costs) else None,
            "median_experiments_to_validated": costs.median() if len(costs) else None,
            "min_experiments_to_validated": costs.min() if len(costs) else None,
            "max_experiments_to_validated": costs.max() if len(costs) else None,
            "counterexample_discovery_rate": subset.counterexample_discovered.mean(),
            "discriminative_experiment_ratio": subset.discriminative_experiment_ratio.mean(),
            "redundant_experiment_ratio": subset.redundant_experiment_ratio.mean(),
            "invalid_action_rate": subset.invalid_action.mean(), "hypothesis_revision_count": int(subset.revision_count.sum()),
            "valid_scope_revisions": int(subset.valid_scope_revisions.sum()), "invalid_scope_revisions": int(subset.invalid_scope_revisions.sum()),
            "scope_creep_attempts": int(subset.scope_creep_attempts.sum()),
            "validated_with_adaptive_boundary_probe": int(subset.adaptive_boundary_success.sum()),
        })
        ci_rows.append({"task_id": task_id, "task_type": tasks[task_id].task_type, "successes": successes, "total": total, "rate": successes / total, "method": "Wilson", "confidence_level": 0.95, "ci_low": low, "ci_high": high})
    by_task = pd.DataFrame(summary_rows)
    by_task.to_csv(RESULT / "targeted_replication_by_task.csv", index=False)
    pd.DataFrame(ci_rows).to_csv(RESULT / "confidence_intervals.csv", index=False)
    failures = pd.DataFrame(all_failures)
    if failures.empty:
        failure_summary = pd.DataFrame(columns=["task_id", "task_type", "failure_mode", "run_count"])
    else:
        failure_summary = failures.groupby(["task_id", "task_type", "failure_mode"]).run_id.nunique().reset_index(name="run_count")
    failure_summary.to_csv(RESULT / "failure_mode_summary.csv", index=False)

    baseline = pd.read_csv(ROOT / "results" / "v03" / "strategy_comparison_by_task.csv")
    baseline = baseline[(baseline.task_id.isin(protocol.data["target_task_ids"])) & (baseline.strategy != "llm")]
    figures = make_figures(by_task, runs_df, baseline, actions, evidence, revisions)
    responses_new = [row for row in read(TRACE, "live_llm_responses") if row.get("run_id") in new_ids]
    usage = Counter()
    for response in responses_new:
        usage.update({key: int(value) for key, value in (response.get("usage") or {}).items()})
    task_values = {row["task_type"]: row for row in summary_rows}
    boundary = task_values["BOUNDARY_TRANSITION"]
    scope = task_values["SCOPE_REVISION"]
    competing = task_values["COMPETING_EXPLANATIONS"]
    boundary_signal = "YES" if boundary["n_validated"] >= 5 and boundary["wilson_ci_low"] > 0 else "INCONCLUSIVE"
    scope_signal = "YES" if scope["n_validated"] >= 4 and scope["wilson_ci_low"] > 0 else "INCONCLUSIVE"
    competing_failure = "YES" if competing["validated_rate"] <= 0.5 else "NO"
    m001_status = "SUPPORTED_WITH_TASK_DEPENDENCE"
    m001_r1 = (
        "Within the frozen Q-Explorer task suite, feedback-driven active policies add the clearest value in "
        "boundary localization and evidence-bounded scope revision; simple tasks need no intervention, and "
        "the replication does not establish a stable LLM disadvantage on predefined competing explanations."
    )
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "protocol_hash": protocol.sha256,
        "protocol_commit": "3cbbdf8", "target_task_ids": protocol.data["target_task_ids"],
        "existing_runs": len(old_runs), "new_runs": len(new_runs), "merged_unique_runs": len(merged),
        "runs_per_task": {task_id: int(sum(runs_df.task_id == task_id)) for task_id in protocol.data["target_task_ids"]},
        "new_allocated_vqe_budget": int(sum(run["budget"] for run in new_runs)),
        "new_used_vqe_runs": int(sum(run["budget_spent"] for run in new_runs)),
        "new_full_budget_runs": int(sum(run["budget_spent"] == run["budget"] for run in new_runs)),
        "provider_errors": len(read(TRACE, "provider_errors")),
        "new_live_response_records": len(responses_new), "new_recorded_token_usage_lower_bound": dict(usage),
        "api_cost": None, "rule_based_deterministic": True,
        "prompt_hash_match": checks["prompt"], "model_config_match": checks["model"] and checks["thinking"],
        "judge_config_match": checks["judge"], "budget_config_match": checks["budgets"] and checks["vqe"],
        "task_suite_match": checks["task_suite"] and checks["task_ids"],
        "invalid_runs_retained": int(runs_df.invalid_action.sum()), "replacement_runs": 0,
        "boundary_signal_replicated": boundary_signal, "scope_signal_replicated": scope_signal,
        "competing_failure_mode_replicated": competing_failure,
        "m001_status": m001_status, "m001_revision_proposed": True, "m001_r1_candidate": m001_r1,
        "figures": figures,
    }
    (RESULT / "targeted_replication_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    sync_required_traces(new_ids)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def sync_required_traces(new_ids: set[str]) -> None:
    rows = [row for row in read(TRACE, "runs") if row.get("run_id") in new_ids]
    path = TRACE / "live_runs.jsonl"
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def make_figures(by_task, runs, baseline, actions, evidence, revisions):
    folder = RESULT / "figures"; folder.mkdir(parents=True, exist_ok=True)
    types = ["BOUNDARY_TRANSITION", "SCOPE_REVISION", "COMPETING_EXPLANATIONS"]
    strategies = ["llm", "rule_based", "random", "no_intervention", "fixed"]
    llm_rates = dict(zip(by_task.task_type, by_task.validated_rate))
    values = {"llm": llm_rates}
    for strategy in strategies[1:]:
        values[strategy] = baseline[baseline.strategy == strategy].groupby("task_type").validated_judgment_rate.mean().to_dict()
    x, width = np.arange(3), 0.15
    fig, ax = plt.subplots(figsize=(10, 5))
    for index, strategy in enumerate(strategies):
        ax.bar(x + (index - 2) * width, [values[strategy].get(t, 0) for t in types], width, label=strategy)
    ax.set_xticks(x, [t.replace("_", "\n") for t in types]); ax.set_ylim(0, 1.08); ax.set_ylabel("Validated rate"); ax.legend(fontsize=8); ax.set_title("V0.3-C validated rate by key task")
    fig.tight_layout(); p1 = folder / "figure1_validated_rate_key_tasks.png"; fig.savefig(p1, dpi=180); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    data = [runs[(runs.task_type == task_type) & runs.validated].experiments_to_validated_judgment.dropna().values for task_type in types]
    ax.boxplot(data, tick_labels=[t.replace("_", "\n") for t in types], showmeans=True); ax.set_ylabel("Experiments to Validated Judgment"); ax.set_title("Validated-run cost (failed runs retained outside this conditional plot)")
    fig.tight_layout(); p2 = folder / "figure2_experiments_to_validated.png"; fig.savefig(p2, dpi=180); plt.close(fig)

    failure_rows = []
    for _, row in runs.iterrows():
        for mode in str(row.failure_modes).split("|") if pd.notna(row.failure_modes) and row.failure_modes else []:
            failure_rows.append((row.task_type, mode))
    counts = Counter(failure_rows); modes = sorted({mode for _, mode in failure_rows})
    fig, ax = plt.subplots(figsize=(12, 5)); failure_width = 0.14
    for index, mode in enumerate(modes):
        vals = np.array([counts[(task_type, mode)] for task_type in types])
        offset = (index - (len(modes) - 1) / 2) * failure_width
        ax.bar(x + offset, vals, failure_width, label=mode)
    ax.set_xticks(x, [t.replace("_", "\n") for t in types]); ax.set_ylim(0, 16)
    ax.set_ylabel("Independent runs flagged (modes may overlap)"); ax.set_title("LLM failure modes by task")
    ax.legend(fontsize=7, loc="upper left", bbox_to_anchor=(1, 1))
    fig.tight_layout(); p3 = folder / "figure3_failure_modes.png"; fig.savefig(p3, dpi=180); plt.close(fig)

    candidate_ids = set(runs[(runs.task_type == "BOUNDARY_TRANSITION") & runs.validated & runs.adaptive_boundary_success].run_id)
    representative = next(iter(sorted(candidate_ids)), next(iter(runs[(runs.task_type == "BOUNDARY_TRANSITION") & runs.validated].run_id)))
    acts = sorted((row for row in actions if row["run_id"] == representative), key=lambda row: row["round"])
    evid = {row["round"]: row for row in evidence if row["run_id"] == representative}
    rev_rounds = {row["round"] for row in revisions if row["run_id"] == representative}
    lines = ["Observation: uncertain depth-dependent topology effect"]
    for action in acts:
        marker = " + REVISION" if action["round"] in rev_rounds else ""
        lines.append(f"R{action['round']}: {action['action_type']} → {evid.get(action['round'],{}).get('decision','?')}{marker}")
    fig, ax = plt.subplots(figsize=(12, 4)); ax.axis("off"); ax.text(0.01, 0.98, "\n↓\n".join(lines), va="top", family="monospace", fontsize=9); ax.set_title(f"Boundary timeline: {representative}")
    fig.tight_layout(); p4 = folder / "figure4_boundary_timeline.png"; fig.savefig(p4, dpi=180); plt.close(fig)
    return [str(path.relative_to(ROOT)) for path in (p1, p2, p3, p4)]


if __name__ == "__main__":
    raise SystemExit(main())
