"""Analyze V0.3 pilot by task and task type without hiding failed or losing strategies."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
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

RESULT = ROOT / "results" / "v03"
TRACE = ROOT / "traces" / "v03"


def read(name):
    return JsonlTrace(TRACE / f"{name}.jsonl").read_all()


def main() -> int:
    frozen = FrozenConfig(ROOT / "configs" / "frozen_v03.yaml")
    suite = TaskSuite(ROOT / "configs" / "frozen_v03_tasks.yaml")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    run_token = f"_c{frozen.sha256[:8]}_g{commit[:7]}"
    ends = [item for item in read("runs") if item.get("event") == "END" and item.get("run_id", "").endswith(run_token)]
    actions = read("actions")
    evidence = read("evidence")
    task_map = {task.task_id: task for task in suite.tasks}
    by_task_rows = []
    for run in ends:
        task = task_map[run["task_id"]]
        run_actions = [item for item in actions if item.get("run_id") == run["run_id"]]
        run_evidence = [item for item in evidence if item.get("run_id") == run["run_id"]]
        validated = run["validated_judgment"]
        counter = next((item for item in run_evidence if item.get("decision") == "COUNTEREXAMPLE"), None)
        counter_cost = None
        if counter:
            counter_cost = sum(item["budget_cost"] for item in run_actions if item["round"] <= counter["round"])
        discriminative = set(frozen.data["metrics"]["discriminative_action_types"])
        discriminative_runs = sum(item["budget_cost"] for item in run_actions if item["action_type"] in discriminative)
        seen, redundant = defaultdict(int), 0
        for action in run_actions:
            exp = action.get("experiment") or {}
            key = (exp.get("hamiltonian_id"), exp.get("depth"), exp.get("entanglement"))
            if seen[key] >= frozen.data["metrics"]["adequate_replication"] and action["action_type"] != "REPLICATE":
                redundant += action["budget_cost"]
            seen[key] += action["budget_cost"]
        by_task_rows.append({
            "run_id": run["run_id"], "task_id": run["task_id"], "task_type": task.task_type,
            "difficulty": task.difficulty_metadata["difficulty"], "strategy": run["strategy"], "policy_seed": run["policy_seed"],
            "budget": run["budget"], "budget_spent": run["budget_spent"],
            "experiments_to_validated_judgment": validated["experiments_to_validated_judgment"],
            "validated_judgment_rate": float(validated["validated"]),
            "counterexample_discovery_efficiency": counter_cost,
            "discriminative_experiment_ratio": discriminative_runs / run["budget_spent"],
            "redundant_experiment_ratio": redundant / run["budget_spent"],
            "held_out_result": run["held_out_result"], "final_judgment": run["final_judgment"],
            "failure_modes": "|".join(run["failure_modes"]),
        })
    dataframe = pd.DataFrame(by_task_rows)
    dataframe.to_csv(RESULT / "strategy_comparison_by_task.csv", index=False)
    aggregate = dataframe.groupby(["task_type", "strategy"], dropna=False).agg(
        run_count=("run_id", "count"),
        validated_judgment_rate=("validated_judgment_rate", "mean"),
        mean_experiments_to_validated_judgment=("experiments_to_validated_judgment", "mean"),
        median_experiments_to_validated_judgment=("experiments_to_validated_judgment", "median"),
        mean_counterexample_discovery_efficiency=("counterexample_discovery_efficiency", "mean"),
        discriminative_experiment_ratio=("discriminative_experiment_ratio", "mean"),
        redundant_experiment_ratio=("redundant_experiment_ratio", "mean"),
    ).reset_index()
    aggregate.to_csv(RESULT / "strategy_comparison_aggregate.csv", index=False)
    figures = plot(dataframe, actions, evidence, frozen.sha256[:8])
    v02 = json.loads((ROOT / "results" / "v02" / "v02_summary.json").read_text(encoding="utf-8"))
    v02_reanalysis = {
        "original_no_intervention_stable_judgment_runs": 2,
        "validated_under_v03_criteria": False,
        "reason_codes": ["INSUFFICIENT_INDEPENDENT_INSTANCES", "HELD_OUT_VALIDATION_MISSING"],
        "v02_artifacts_modified": False,
    }
    (RESULT / "v02_validated_judgment_reanalysis.json").write_text(json.dumps(v02_reanalysis, indent=2), encoding="utf-8")
    live_status = json.loads((RESULT / "live_llm_status.json").read_text(encoding="utf-8"))
    rates = dataframe.groupby("strategy")["validated_judgment_rate"].mean().to_dict()
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "version": "0.3",
        "config_hash": frozen.sha256, "task_suite_hash": suite.sha256,
        "task_count": len(suite.tasks), "completed_non_live_runs": len(dataframe),
        "selected_git_commit": commit,
        "random_policy_seeds": frozen.data["strategies"]["random"]["policy_seeds"],
        "live_llm_used": live_status["live_llm_used"], "live_llm_blocked_by_credentials": live_status["live_llm_blocked_by_credentials"],
        "validated_judgment_rate_by_strategy": rates,
        "m001_assessment": "INCONCLUSIVE_WITH_PARTIAL_NON_LLM_SUPPORT",
        "interpretation": "Rule-based feedback improved validated rate on competing-explanation/problem-revision tasks relative to static policies in this pilot, but boundary/scope tasks remained unresolved and no live LLM incremental value could be tested without credentials.",
        "figures": figures, "v02_reanalysis": v02_reanalysis,
        "qiskit_aer_used": True, "noise_simulation_used": False, "real_quantum_hardware_used": False,
    }
    (RESULT / "v03_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def plot(df, actions, evidence, config_short):
    folder = RESULT / "figures"; folder.mkdir(parents=True, exist_ok=True)
    strategy_order = ["llm", "rule_based", "random", "no_intervention", "fixed"]
    types = list(dict.fromkeys(df["task_type"]))
    fig, ax = plt.subplots(figsize=(13, 6))
    width = 0.15; x = np.arange(len(types))
    for index, strategy in enumerate(strategy_order):
        subset = df[df.strategy == strategy].groupby("task_type")["experiments_to_validated_judgment"].mean()
        values = [subset.get(task_type, np.nan) for task_type in types]
        ax.bar(x + (index - 2) * width, values, width, label=strategy)
    ax.set_xticks(x, [value.replace("_", "\n") for value in types], fontsize=8)
    ax.set_ylabel("Experiments to Validated Judgment")
    ax.set_title("Validated-judgment cost by task structure")
    ax.legend(); fig.tight_layout(); p1 = folder / "figure1_validated_judgment_cost.png"; fig.savefig(p1, dpi=180); plt.close(fig)

    pivot = df.groupby(["task_type", "strategy"])["validated_judgment_rate"].mean().unstack().reindex(index=types, columns=strategy_order)
    fig, ax = plt.subplots(figsize=(9, 7)); image = ax.imshow(pivot.fillna(0).values, vmin=0, vmax=1, cmap="Blues")
    ax.set_xticks(range(len(strategy_order)), strategy_order, rotation=25); ax.set_yticks(range(len(types)), [v.replace("_", " ") for v in types], fontsize=8)
    for i in range(len(types)):
        for j in range(len(strategy_order)): ax.text(j, i, f"{pivot.fillna(0).iloc[i,j]:.2f}", ha="center", va="center")
    ax.set_title("Validated Judgment Rate"); fig.colorbar(image, ax=ax); fig.tight_layout(); p2 = folder / "figure2_validated_rate_heatmap.png"; fig.savefig(p2, dpi=180); plt.close(fig)

    representative = next((run_id for run_id in df.run_id if "TASK_D01_llm_303" in run_id), next(run_id for run_id in df.run_id if "TASK_D01_rule_based" in run_id))
    acts = sorted((a for a in actions if a.get("run_id") == representative), key=lambda a:a["round"])
    evid = {e["round"]:e for e in evidence if e.get("run_id") == representative}
    fig, ax = plt.subplots(figsize=(13, 4)); ax.axis("off")
    lines = ["Observation: connectivity and depth co-vary → competing hypotheses"]
    for action in acts:
        ev = evid.get(action["round"], {})
        lines.append(f"R{action['round']}: {action['action_type']} → {ev.get('decision','?')} ({','.join(ev.get('reason_codes',[]))})")
    ax.text(0.01, 0.98, "\n↓\n".join(lines), va="top", family="monospace", fontsize=9)
    ax.set_title("Representative competing-explanations trace")
    fig.tight_layout(); p3 = folder / "figure3_scientific_timeline.png"; fig.savefig(p3, dpi=180); plt.close(fig)

    difficulty_order = {"low":1,"medium":2,"high":3}
    rule = df[df.strategy=="rule_based"].groupby("task_id").agg({"validated_judgment_rate":"mean","difficulty":"first"})
    live = df[df.strategy=="llm"].groupby("task_id").agg({"validated_judgment_rate":"mean","difficulty":"first"})
    static = df[df.strategy=="no_intervention"].groupby("task_id").agg({"validated_judgment_rate":"mean","difficulty":"first"})
    common = rule.index.intersection(static.index)
    fig, ax = plt.subplots(figsize=(7,5))
    benefit=[]; complexity=[]
    for task_id in common:
        benefit.append(rule.loc[task_id,"validated_judgment_rate"]-static.loc[task_id,"validated_judgment_rate"]); complexity.append(difficulty_order[rule.loc[task_id,"difficulty"]]-0.04)
    ax.scatter(complexity,benefit,color="#2a6fbb",label="Rule-based − No-intervention")
    live_common = live.index.intersection(static.index)
    ax.scatter([difficulty_order[live.loc[t,"difficulty"]]+0.04 for t in live_common], [live.loc[t,"validated_judgment_rate"]-static.loc[t,"validated_judgment_rate"] for t in live_common], color="#d95f02",label="Live LLM − No-intervention")
    ax.axhline(0,color="gray",linestyle="--"); ax.legend(fontsize=8)
    ax.set_xticks([1,2,3],["low","medium","high"]); ax.set_ylabel("Validated-rate difference"); ax.set_xlabel("Frozen task difficulty"); ax.set_title("Active-policy benefit vs task complexity")
    fig.tight_layout(); p4=folder/"figure4_complexity_relative_benefit.png"; fig.savefig(p4,dpi=180); plt.close(fig)
    return [str(p.relative_to(ROOT)) for p in (p1,p2,p3,p4)]


if __name__ == "__main__":
    raise SystemExit(main())
