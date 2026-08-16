"""Run the pre-registered V0.3-D deterministic audit over frozen traces."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.v03 import TaskSuite
from src.v03d import (
    AuditModeGuard,
    EvidenceGraph,
    audit_boundary_run,
    audit_competing_run,
    audit_scope_revision,
    classify_scope_run,
)

RESULT = ROOT / "results" / "v03d"
FIGURES = RESULT / "figures"
TRACE = ROOT / "traces" / "v03d"


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def formal_live_runs(graph: EvidenceGraph, config: dict, task_id: str) -> list[dict]:
    formal = config["formal_runs"]["live_llm"]
    expected = [
        f"V03_{task_id}_llm_{seed}_cc47285bd_g{formal['v03_git_commit']}"
        for seed in formal["v03_task_seeds"]
    ] + [
        f"V03_{task_id}_llm_{seed}_cc47285bd_g{config['historical_sources']['v03c']['protocol_commit']}"
        for seed in formal["v03c_task_seeds"]
    ]
    rows = [graph.get_run(run_id) for run_id in expected]
    missing = [row for row in rows if row.get("status") == "MISSING_LINK"]
    if missing:
        raise RuntimeError(f"Missing formal Live LLM runs for {task_id}: {missing}")
    if len({row["run_id"] for row in rows}) != 15:
        raise RuntimeError(f"Formal run deduplication failed for {task_id}")
    return rows


def formal_rule_run(graph: EvidenceGraph, config: dict, task_id: str) -> list[dict]:
    suffix = f"_g{config['formal_runs']['rule_based']['executable_commit']}"
    rows = [
        row for row in graph.records["runs"]
        if row.get("event") == "END" and row.get("task_id") == task_id
        and row.get("strategy") == "rule_based" and str(row.get("run_id", "")).endswith(suffix)
    ]
    unique = {row["run_id"]: row for row in rows}
    if len(unique) != 1:
        raise RuntimeError(f"Expected one frozen deterministic Rule-Based run, found {sorted(unique)}")
    return list(unique.values())


def scope_audit(graph: EvidenceGraph, runs: list[dict]) -> tuple[list[dict], dict]:
    revision_rows, run_rows = [], []
    for run in runs:
        previous_round = 0
        audits = []
        for revision in graph.revisions_for_run(run["run_id"]):
            row = audit_scope_revision(graph, revision, previous_round)
            revision_rows.append(row)
            audits.append(row)
            previous_round = int(revision.get("round", previous_round))
        classification = classify_scope_run(run, audits)
        run_rows.append({
            "run_id": run["run_id"], "original_validated": bool(run["validated_judgment"]["validated"]),
            "revision_count": len(audits), "run_classification": classification,
            "evidence_attributed_revision": classification in {"VALIDATED_WITH_STRICT_REVISION", "VALIDATED_WITH_RECONSTRUCTED_REVISION"},
        })
    status_counts = Counter(row["audit_status"] for row in revision_rows)
    class_counts = Counter(row["run_classification"] for row in run_rows)
    original = sum(row["original_validated"] for row in run_rows)
    attributed = sum(row["evidence_attributed_revision"] for row in run_rows)
    rate = attributed / len(run_rows)
    if rate >= 0.50:
        capability = "SUPPORTED"
    elif attributed >= 2 and attributed >= original / 2:
        capability = "PARTIAL"
    else:
        capability = "INCONCLUSIVE"
    summary = {
        "total_runs": len(run_rows), "total_revisions": len(revision_rows),
        "revision_status_counts": {status: status_counts.get(status, 0) for status in ("STRICTLY_SUPPORTED", "DETERMINISTICALLY_RECONSTRUCTABLE", "INDIRECTLY_SUPPORTED", "UNSUPPORTED_ATTRIBUTION")},
        "run_classification_counts": dict(sorted(class_counts.items())),
        "original_validated": original, "evidence_attributed_validated": attributed,
        "evidence_attributed_scope_revision_rate": rate, "scope_capability_status": capability,
        "run_rows": run_rows,
    }
    return revision_rows, summary


def competing_summary(rows: list[dict]) -> dict:
    total = len(rows)
    return {
        "total_runs": total,
        "original_validated": sum(row["validated_original"] for row in rows),
        "scientific_design_valid": sum(row["scientific_design_valid"] for row in rows),
        "scientifically_validated": sum(row["scientifically_validated"] for row in rows),
        "outcome_right_wrong_reason": sum(row["audit_status"] == "OUTCOME_VALIDATED_BUT_DESIGN_INVALID" for row in rows),
        "multi_variable_change_runs": sum(row["multi_variable_change_count"] > 0 for row in rows),
        "valid_single_variable_control_runs": sum(row["single_variable_control_executed"] for row in rows),
        "failure_reason_counts": dict(sorted(Counter(reason for row in rows for reason in row["failure_reason"].split("|") if reason).items())),
    }


def make_figures(scope_rows: list[dict], llm_rows: list[dict], rule_rows: list[dict], boundary_rows: list[dict], graph: EvidenceGraph) -> list[str]:
    FIGURES.mkdir(parents=True, exist_ok=True)
    statuses = ("STRICTLY_SUPPORTED", "DETERMINISTICALLY_RECONSTRUCTABLE", "INDIRECTLY_SUPPORTED", "UNSUPPORTED_ATTRIBUTION")
    counts = Counter(row["audit_status"] for row in scope_rows)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(["Explicit", "Reconstructed", "Indirect", "Unsupported"], [counts[s] for s in statuses])
    ax.set_ylabel("Revision records"); ax.set_title("Scope revision evidence attribution")
    fig.tight_layout(); first = FIGURES / "figure1_scope_evidence_attribution.png"; fig.savefig(first, dpi=180); plt.close(fig)

    labels = ("Original validated", "Scientific design valid", "Scientifically validated")
    metrics = ("validated_original", "scientific_design_valid", "scientifically_validated")
    x = range(len(labels)); width = 0.36
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar([value - width / 2 for value in x], [sum(row[key] for row in llm_rows) / len(llm_rows) for key in metrics], width, label="Live LLM")
    ax.bar([value + width / 2 for value in x], [sum(row[key] for row in rule_rows) / len(rule_rows) for key in metrics], width, label="Rule-Based")
    ax.set_xticks(list(x), labels); ax.set_ylim(0, 1.08); ax.set_ylabel("Rate"); ax.legend(); ax.set_title("Competing explanations: outcome vs scientific process")
    fig.tight_layout(); second = FIGURES / "figure2_competing_validity_layers.png"; fig.savefig(second, dpi=180); plt.close(fig)

    representative = next(row for row in boundary_rows if row["validated_original"] and row["evidence_chain_complete"])
    run_id = representative["run_id"]
    actions = sorted((row for row in graph.records["actions"] if row.get("run_id") == run_id), key=lambda row: int(row.get("round", 0)))
    evidence = {row.get("action_id"): row for row in graph.records["evidence"] if row.get("run_id") == run_id}
    lines = ["Observation: uncertain depth-dependent topology effect"]
    for action in actions:
        linked = evidence.get(action.get("action_id"), {})
        marker = "HELD-OUT" if linked.get("held_out") else "EXPLORATION"
        lines.append(f"R{action.get('round')}: {action.get('action_type')} -> {action.get('action_id')}")
        lines.append(f"    EXP: {', '.join(linked.get('experiment_ids', []))} -> {linked.get('evidence_id')} / {linked.get('decision')} [{marker}]")
    if not graph.revisions_for_run(run_id):
        lines.append("Revision: none recorded (not inferred)")
    fig, ax = plt.subplots(figsize=(13, 7)); ax.axis("off")
    ax.text(0.01, 0.98, "\n".join(lines), va="top", family="monospace", fontsize=7.5)
    ax.set_title(f"Complete boundary evidence chain: {run_id}")
    fig.tight_layout(); third = FIGURES / "figure3_boundary_evidence_chain.png"; fig.savefig(third, dpi=180); plt.close(fig)
    return [str(path.relative_to(ROOT)) for path in (first, second, third)]


def main() -> int:
    guard = AuditModeGuard()
    guard.assert_clean()
    config = yaml.safe_load((ROOT / "configs" / "frozen_v03d.yaml").read_text(encoding="utf-8"))
    graph = EvidenceGraph.from_trace_roots((ROOT / "traces" / "v03", ROOT / "traces" / "v03c"))
    suite = TaskSuite(ROOT / "configs" / "frozen_v03_tasks.yaml")
    tasks = {task.task_id: task for task in suite.tasks}
    RESULT.mkdir(parents=True, exist_ok=True)
    write_json(RESULT / "evidence_graph_summary.json", graph.summary())

    scope_runs = formal_live_runs(graph, config, config["target_tasks"]["scope_revision"])
    scope_rows, scope_summary = scope_audit(graph, scope_runs)
    pd.DataFrame(scope_rows).to_csv(RESULT / "scope_revision_audit.csv", index=False)
    write_jsonl(RESULT / "reconstructed_scope_links.jsonl", [
        {
            "source": "POSTHOC_DETERMINISTIC_RECONSTRUCTION",
            "run_id": row["run_id"], "revision_record_locator": row["revision_record_locator"],
            "evidence_ids": json.loads(row["reconstructed_evidence_ids"]),
            "experiment_ids": json.loads(row["reconstructed_experiment_ids"]),
        }
        for row in scope_rows if row["audit_status"] == "DETERMINISTICALLY_RECONSTRUCTABLE"
    ])
    write_json(RESULT / "scope_revision_summary.json", scope_summary)

    competing_task = tasks[config["target_tasks"]["competing_explanations"]]
    llm_competing = [audit_competing_run(graph, run, competing_task) for run in formal_live_runs(graph, config, competing_task.task_id)]
    rule_competing = [audit_competing_run(graph, run, competing_task) for run in formal_rule_run(graph, config, competing_task.task_id)]
    pd.DataFrame(llm_competing).to_csv(RESULT / "competing_explanation_audit.csv", index=False)
    pd.DataFrame(rule_competing).to_csv(RESULT / "competing_rule_based_audit.csv", index=False)
    competing = {"live_llm": competing_summary(llm_competing), "rule_based": competing_summary(rule_competing), "rules_strategy_agnostic": True}
    write_json(RESULT / "competing_validity_summary.json", competing)

    boundary_runs = formal_live_runs(graph, config, config["target_tasks"]["boundary_integrity"])
    boundary_rows = [audit_boundary_run(graph, run) for run in boundary_runs]
    pd.DataFrame(boundary_rows).to_csv(RESULT / "boundary_integrity_audit.csv", index=False)
    boundary_validated = [row for row in boundary_rows if row["validated_original"]]
    boundary_pass = bool(boundary_validated and all(row["evidence_chain_complete"] for row in boundary_validated))
    figures = make_figures(scope_rows, llm_competing, rule_competing, boundary_rows, graph)

    outcome_wrong_reason = competing["live_llm"]["outcome_right_wrong_reason"]
    problem_revision = bool(outcome_wrong_reason or scope_summary["original_validated"] > scope_summary["evidence_attributed_validated"])
    m001 = {
        "performance_level_status": "SUPPORTED_WITH_TASK_DEPENDENCE",
        "scientific_process_status": "PARTIALLY_SUPPORTED" if boundary_pass else "INCONCLUSIVE",
        "m001_r1_recommended": True,
        "candidate_m001_r1": "LLM-based active scientific exploration shows task-dependent incremental value, with the clearest replicated evidence currently appearing in adaptive boundary localization. Performance on hypothesis scope revision and competing-explanation tasks must additionally be evaluated for evidence attribution and experimental-control validity, because successful held-out outcomes do not by themselves guarantee scientifically valid reasoning.",
        "problem_definition_revision": problem_revision,
        "problem_definition_revision_text": "AI scientific-exploration evaluation must jointly measure outcome validity and scientific-process validity." if problem_revision else None,
    }
    write_json(RESULT / "m001_reassessment.json", m001)
    summary = {
        "audit_mode": True, "new_live_llm_calls": 0, "new_aer_vqe_runs": 0, "new_research_runs": 0,
        "scope": scope_summary, "competing": competing,
        "boundary": {
            "total_runs": len(boundary_rows), "original_validated": len(boundary_validated),
            "validated_chains_complete": sum(row["evidence_chain_complete"] for row in boundary_validated),
            "evidence_chain_pass": boundary_pass,
            "probe_present_validated": sum(bool(json.loads(row["adaptive_probe_action_ids"])) for row in boundary_validated),
            "probe_present_not_validated": sum(bool(json.loads(row["adaptive_probe_action_ids"])) for row in boundary_rows if not row["validated_original"]),
            "v04_candidate": boundary_pass,
        },
        "m001": m001, "problem_definition_revision": problem_revision, "figures": figures,
    }
    write_json(RESULT / "scientific_validity_summary.json", summary)
    audit_events = [
        {"event": "AUDIT_START", "audit_mode": True, "new_live_llm_calls": 0, "new_aer_vqe_runs": 0, "new_research_runs": 0},
        *({"event": "SCOPE_REVISION_AUDIT", **row} for row in scope_rows),
        *({"event": "SCOPE_RUN_CLASSIFICATION", **row} for row in scope_summary["run_rows"]),
        *({"event": "COMPETING_RUN_AUDIT", **row} for row in llm_competing),
        *({"event": "COMPETING_RUN_AUDIT", **row} for row in rule_competing),
        *({"event": "BOUNDARY_RUN_AUDIT", **row} for row in boundary_rows),
        {"event": "AUDIT_END", "scope_capability_status": scope_summary["scope_capability_status"],
         "m001_scientific_process_status": m001["scientific_process_status"],
         "problem_definition_revision": problem_revision},
    ]
    write_jsonl(TRACE / "audit_events.jsonl", audit_events)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
