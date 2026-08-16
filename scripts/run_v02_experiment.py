"""Run the frozen V0.2 mini active exploration and equal-budget baselines."""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.baselines import FixedExplorer, NoInterventionExplorer, RandomExplorer, balanced_no_intervention_plan
from src.hamiltonian import generate_ising_hamiltonian
from src.logging import JsonlTrace
from src.logging.jsonl_logger import utc_now
from src.research import (
    ActiveExperimentExecutor,
    ExperimentBudget,
    FrozenConfig,
    Observation,
    ResearchMemory,
    RuleBasedResearchAgent,
    create_run_identity,
    judge_current_comparison,
    revise_hypothesis,
)


TRACE_ROOT = ROOT / "traces" / "v02"
RESULT_ROOT = ROOT / "results" / "v02"
PROMPT_PATH = ROOT / "prompts" / "research_agent_v01.txt"


def prepare_space(config: dict) -> tuple[dict, list[dict], dict[str, dict]]:
    ecfg = config["experiment_space"]
    hamiltonians = {}
    features = {}
    sets = {}
    for item in ecfg["hamiltonians"]:
        ham = generate_ising_hamiltonian(
            item["num_qubits"], item["topology"], item["seed"], ecfg["coefficient_low"],
            ecfg["coefficient_high"], ecfg["random_edge_probability"],
        )
        hamiltonians[ham.hamiltonian_id] = ham
        sets[ham.hamiltonian_id] = item["set"]
        possible_edges = ham.num_qubits * (ham.num_qubits - 1) / 2
        features[ham.hamiltonian_id] = {
            "num_qubits": ham.num_qubits,
            "topology": ham.topology,
            "num_interactions": len(ham.J),
            "interaction_density": len(ham.J) / possible_edges if possible_edges else 0.0,
            "set": item["set"],
            "seed": ham.seed,
        }
    regions = [
        {"hamiltonian_id": identifier, "depth": int(depth), "entanglement": entanglement, "set": sets[identifier]}
        for identifier in sorted(hamiltonians)
        for depth in ecfg["depths"]
        for entanglement in ecfg["entanglements"]
    ]
    return hamiltonians, regions, features


def next_id(trace: JsonlTrace, field: str, prefix: str) -> str:
    maximum = 0
    pattern = re.compile(rf"^{re.escape(prefix)}(\d{{6}})$")
    for record in trace.read_all():
        match = pattern.fullmatch(str(record.get(field, "")))
        if match:
            maximum = max(maximum, int(match.group(1)))
    return f"{prefix}{maximum + 1:06d}"


def seed_v01(memory: ResearchMemory) -> None:
    summary = json.loads((ROOT / "results" / "smoke_test_summary.json").read_text(encoding="utf-8"))
    hypothesis = summary["hypothesis"]
    memory.append("hypotheses", {"round": 0, "event": "SEEDED_FROM_V01", "source_version": "0.1", **hypothesis})
    v01_evidence = JsonlTrace(ROOT / "traces" / "evidence.jsonl").read_all()[-1]
    memory.append("evidence", {"round": 0, "event": "SEEDED_FROM_V01", "source_version": "0.1", **v01_evidence})
    for record in JsonlTrace(ROOT / "traces" / "experiments.jsonl").read_all():
        compact = {
            key: record.get(key)
            for key in (
                "experiment_id", "hamiltonian_id", "depth", "entanglement", "initialization_seed",
                "energy_error", "converged", "status",
            )
        }
        memory.append("experiments", {"round": 0, "event": "SEEDED_FROM_V01", "source_version": "0.1", **compact})


def inject_seed_group(state, seeds: list[int]):
    def enriched(items):
        return tuple(dict(item) | {"seed_group": list(seeds)} for item in items)
    return replace(state, untested_regions=enriched(state.untested_regions), tested_regions=enriched(state.tested_regions))


def validate_frozen_action(action, regions: list[dict], features: dict[str, dict], remaining: int) -> tuple[bool, str | None, bool]:
    if action.experiment is None:
        return True, None, False
    spec = action.experiment
    key = (spec.hamiltonian_id, spec.depth, spec.entanglement)
    allowed = {(item["hamiltonian_id"], item["depth"], item["entanglement"]): item for item in regions}
    if key not in allowed:
        return False, "OUTSIDE_FROZEN_EXPERIMENT_SPACE", False
    held_out = allowed[key]["set"] == "held_out"
    if held_out and action.action_type != "VALIDATE_HYPOTHESIS":
        return False, "HELD_OUT_ACCESS_REQUIRES_VALIDATION_ACTION", held_out
    if not held_out and action.action_type == "VALIDATE_HYPOTHESIS":
        return False, "VALIDATION_ACTION_REQUIRES_HELD_OUT_INSTANCE", held_out
    if action.budget_cost > remaining:
        return False, "BUDGET_EXCEEDED", held_out
    return True, None, held_out


def update_from_evidence(parent: dict, evidence: dict, all_evidence: list[dict], supported_minimum_instances: int, supported_requires_held_out: bool) -> dict:
    updated = {key: (list(value) if isinstance(value, list) else value) for key, value in parent.items()}
    updated["round"] = evidence["round"]
    updated["event"] = "EVIDENCE_UPDATE"
    decision = evidence["decision"]
    ids = list(evidence.get("experiment_ids", []))
    support = list(updated.get("supporting_experiments", []))
    counters = list(updated.get("counterexamples", []))
    if decision == "SUPPORT":
        support.extend(identifier for identifier in ids if identifier not in support)
        supportive_instances = {
            record.get("comparison", {}).get("hamiltonian_id")
            for record in all_evidence + [evidence]
            if record.get("hypothesis_id") == parent["hypothesis_id"] and record.get("decision") == "SUPPORT"
        }
        held_out_support = any(
            record.get("hypothesis_id") == parent["hypothesis_id"] and record.get("decision") == "SUPPORT" and record.get("held_out")
            for record in all_evidence + [evidence]
        )
        meets_held_out = held_out_support or not supported_requires_held_out
        updated["status"] = "SUPPORTED" if len(supportive_instances) >= supported_minimum_instances and meets_held_out else "PRELIMINARY_SUPPORT"
    elif decision == "COUNTEREXAMPLE":
        counters.extend(identifier for identifier in ids if identifier not in counters)
        updated["status"] = "NARROWED"
    elif updated.get("status") not in {"NARROWED", "REJECTED", "SUPPORTED"}:
        updated["status"] = "INCONCLUSIVE"
    updated["supporting_experiments"] = support
    updated["counterexamples"] = counters
    history = list(updated.get("revision_history", []))
    history.append({"evidence_id": evidence["evidence_id"], "decision": decision, "to_status": updated["status"], "timestamp": utc_now()})
    updated["revision_history"] = history
    return updated


def build_strategy(name: str, config: dict, regions: list[dict], action_count: int):
    if name == "active_agent":
        return RuleBasedResearchAgent(), "active_agent", "rule-based"
    if name.startswith("random_seed_"):
        seed = int(name.removeprefix("random_seed_"))
        return RandomExplorer(seed), "random", f"random-seed-{seed}"
    if name == "no_intervention":
        return NoInterventionExplorer(balanced_no_intervention_plan(regions, action_count)), "no_intervention", "pre-registered-plan"
    if name == "fixed":
        frozen = config["strategies"]["fixed"]
        return FixedExplorer(int(frozen["depth"]), frozen["entanglement"]), "fixed", "pre-registered-fixed"
    raise ValueError(name)


def run_strategy(name: str, frozen: FrozenConfig, hamiltonians: dict, regions: list[dict], features: dict[str, dict]) -> dict:
    config = frozen.data
    budget_total = int(config["budget"]["runs_per_strategy"])
    seed_groups = config["vqe"]["seed_groups"]
    action_count = budget_total // len(seed_groups[0])
    agent, category, model = build_strategy(name, config, regions, action_count)
    run_trace = JsonlTrace(TRACE_ROOT / "runs.jsonl")
    existing_ids = [record["run_id"] for record in run_trace.read_all() if "run_id" in record]
    identity = create_run_identity(
        existing_ids, name, frozen.sha256, PROMPT_PATH, config["agent"]["prompt_version"], model,
        config["agent"]["temperature"], budget_total,
    )
    memory = ResearchMemory(TRACE_ROOT, identity.run_id)
    run_trace.append({"event": "START", **identity.to_dict(), "live_llm_used": False})
    seed_v01(memory)
    budget = ExperimentBudget(budget_total)
    executor = ActiveExperimentExecutor(hamiltonians, config["vqe"])
    revision_created = False
    rounds_completed = 0
    invalid_actions = 0
    for round_id in range(1, action_count + 1):
        frozen.verify_unchanged()
        state = memory.rebuild_state_at_round(round_id - 1, budget_total, regions, features)
        state = inject_seed_group(replace(state, round=round_id), seed_groups[round_id - 1])
        observation = Observation.from_state(state)
        action_id = next_id(memory.traces["actions"], "action_id", "ACT_")
        try:
            action = agent.select_action(observation, action_id)
            valid, error, held_out = validate_frozen_action(action, regions, features, budget.remaining)
        except Exception as exc:
            action, valid, error, held_out = None, False, f"{type(exc).__name__}: {exc}", False
        if not valid or action is None:
            invalid_actions += 1
            memory.append("actions", {
                "round": round_id, "action_id": action_id, "strategy": category,
                "validation_status": "INVALID_ACTION", "validation_error": error,
                "budget_before": budget.remaining, "budget_cost": 0, "budget_after": budget.remaining,
                "prompt_version": identity.prompt_version, "model": identity.model,
            })
            break

        ledger = budget.consume(action.action_id, action.budget_cost, round_id)
        response_hash = hashlib.sha256(json.dumps(action.to_dict(), sort_keys=True).encode()).hexdigest()
        action_record = action.to_dict() | ledger | {
            "strategy": category,
            "validation_status": "VALID",
            "validation_error": None,
            "prompt_version": identity.prompt_version,
            "prompt_hash": identity.prompt_hash,
            "model": identity.model,
            "temperature": identity.temperature,
            "request_id": None,
            "response_hash": response_hash,
            "responding_to_evidence_id": observation.recent_evidence[-1].get("evidence_id") if observation.recent_evidence else None,
            "responding_to_evidence_label": observation.recent_evidence[-1].get("decision") if observation.recent_evidence else None,
            "agent_failure_modes": detect_agent_failure_modes(action),
        }
        memory.append("actions", action_record)

        evidence_hypothesis_id = action.hypothesis_id
        if action.action_type == "REVISE_HYPOTHESIS" and action.revision_proposal:
            parent = next(item for item in memory.get_active_hypotheses(round_id - 1) if item["hypothesis_id"] == action.hypothesis_id)
            existing_hypothesis_ids = {item["hypothesis_id"] for item in memory.get_active_hypotheses(round_id - 1)}
            trigger_ids = [item.get("evidence_id") for item in observation.recent_evidence[-1:] if item.get("evidence_id")]
            child, revision = revise_hypothesis(
                parent,
                action.revision_proposal["new_claim"],
                action.reason,
                trigger_ids,
                action.revision_proposal["scope_change"],
                existing_hypothesis_ids,
            )
            memory.append("revisions", {"round": round_id, "action_id": action.action_id, **revision.to_dict()})
            memory.append("hypotheses", {"round": round_id, "event": "REVISION_CREATED", **child})
            evidence_hypothesis_id = child["hypothesis_id"]
            revision_created = True

        experiment_records = executor.execute(identity.run_id, action, held_out)
        for record in experiment_records:
            memory.append("experiments", record)
        evidence_id = next_id(memory.traces["evidence"], "evidence_id", "V02_EVID_")
        current_experiments = memory.records("experiments", round_id, include_v01=False)
        evidence = judge_current_comparison(current_experiments, action, evidence_hypothesis_id, config["evidence_judge"], evidence_id, held_out)
        memory.append("evidence", evidence)
        current_hypothesis = next(item for item in memory.get_active_hypotheses(round_id) if item["hypothesis_id"] == evidence_hypothesis_id)
        prior_evidence = memory.records("evidence", round_id - 1, include_v01=False)
        updated = update_from_evidence(
            current_hypothesis, evidence, prior_evidence,
            int(config["evidence_judge"]["supported_minimum_instances"]),
            bool(config["evidence_judge"]["supported_requires_held_out"]),
        )
        memory.append("hypotheses", updated)
        rounds_completed += 1
        if budget.remaining == 0:
            break

    frozen.verify_unchanged()
    end_time = utc_now()
    experiments = [record for record in memory.records("experiments", include_v01=False) if record.get("source_version") != "0.1"]
    actions = memory.get_previous_actions()
    evidence = memory.records("evidence", include_v01=False)
    completion = {
        "event": "END", "run_id": identity.run_id, "strategy": name, "strategy_category": category,
        "end_time": end_time, "budget": budget_total, "budget_spent": budget.spent,
        "remaining_budget": budget.remaining, "rounds_completed": rounds_completed,
        "experiment_count": len(experiments), "successful_experiments": sum(item.get("status") == "SUCCESS" for item in experiments),
        "failed_experiments": sum(item.get("status") == "FAILED" for item in experiments),
        "invalid_actions": invalid_actions, "hypothesis_revision": revision_created,
        "optimization_drift": any("AGENT_OPTIMIZATION_DRIFT" in item.get("agent_failure_modes", []) for item in actions),
        "config_hash": frozen.sha256, "prompt_version": identity.prompt_version, "prompt_hash": identity.prompt_hash,
        "model": identity.model, "live_llm_used": False,
    }
    run_trace.append(completion)
    return completion


def detect_agent_failure_modes(action) -> list[str]:
    text = " ".join((action.reason, action.information_goal, action.falsification_condition)).lower()
    flags = []
    optimization_language = any(term in text for term in ("lowest energy", "minimize energy", "best energy"))
    scientific_contract = bool(action.hypothesis_id and action.controlled_variables and action.changed_variables and action.falsification_condition.strip())
    if optimization_language or not scientific_contract:
        flags.append("AGENT_OPTIMIZATION_DRIFT")
    return flags


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "frozen_v02.yaml")
    parser.add_argument("--strategies", nargs="*", default=None)
    args = parser.parse_args()
    frozen = FrozenConfig(args.config)
    if frozen.data["project"]["version"] != "0.2":
        raise ValueError("Expected frozen V0.2 config")
    TRACE_ROOT.mkdir(parents=True, exist_ok=True)
    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    hamiltonians, regions, features = prepare_space(frozen.data)
    (RESULT_ROOT / "experiment_space.json").write_text(
        json.dumps({"config_hash": frozen.sha256, "hamiltonians": [ham.to_dict() | features[identifier] for identifier, ham in hamiltonians.items()], "regions": regions}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    default_strategies = ["active_agent"] + [f"random_seed_{seed}" for seed in frozen.data["strategies"]["random"]["baseline_seeds"]] + ["no_intervention", "fixed"]
    strategies = args.strategies or default_strategies
    summaries = []
    for name in strategies:
        print(f"START_STRATEGY={name}")
        summary = run_strategy(name, frozen, hamiltonians, regions, features)
        summaries.append(summary)
        print(json.dumps(summary, indent=2))
    print(f"COMPLETED_STRATEGY_RUNS={len(summaries)}")
    return 0 if all(item["remaining_budget"] == 0 and item["failed_experiments"] == 0 for item in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
