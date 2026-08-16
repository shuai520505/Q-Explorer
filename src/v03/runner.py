"""Checkpointable multi-task runner sharing the V0.2 Aer fact layer."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import random
from statistics import mean, variance

from src.evidence import EvidenceJudge
from src.hamiltonian import generate_ising_hamiltonian
from src.logging import JsonlTrace
from src.research import ActiveExperimentExecutor, ExperimentSpec, ResearchAction
from src.v03.checkpoint import TaskCheckpoint
from src.v03.diagnostics import diagnose_scientific_failure_modes
from src.v03.validation import evaluate_validated_judgment


@dataclass(frozen=True)
class PlannedCondition:
    condition: dict
    action_type: str
    information_goal: str


def plan_conditions(task, strategy: str, policy_seed: int | None = None) -> list[PlannedCondition]:
    exploration = [dict(item) for item in task.experiment_pool if item["condition_id"] in task.exploration_set]
    held_out = [dict(item) for item in task.experiment_pool if item["condition_id"] in task.held_out_set]
    rounds = task.budget // 2
    validation_rounds = min(2, len(held_out), rounds)
    exploration_rounds = rounds - validation_rounds
    if strategy == "random":
        rng = random.Random(policy_seed)
        rng.shuffle(exploration)
    elif strategy == "fixed":
        preferred = [item for item in exploration if item["depth"] == 2 and item["entanglement"] == "linear"]
        exploration = preferred + [item for item in exploration if item not in preferred]
    elif strategy == "rule_based":
        question = task.scientific_question.lower()
        if "stable across" in question:
            exploration = [item for item in exploration for _ in range(2)]
        elif "depth" in question:
            exploration.sort(key=lambda item: (abs(int(item["depth"]) - 2), item["ham_seed"], item["entanglement"]))
        else:
            exploration.sort(key=lambda item: (item["ham_seed"], item["depth"], item["entanglement"]))
    else:
        exploration.sort(key=lambda item: (item["depth"], item["entanglement"], item["ham_seed"]))
    if not exploration:
        raise ValueError(f"Task {task.task_id} has no exploration conditions")
    chosen = [exploration[index % len(exploration)] for index in range(exploration_rounds)]
    chosen.extend(held_out[:validation_rounds])
    planned = []
    for index, condition in enumerate(chosen):
        held = condition["condition_id"] in task.held_out_set
        if held:
            action_type, goal = "VALIDATE_HYPOTHESIS", "Test the current judgment on an isolated independent condition."
        elif strategy == "rule_based" and task.competing_hypotheses:
            action_type, goal = "CONTROL_DEPTH", "Discriminate the two stated explanations with a single-variable control."
        elif strategy == "rule_based" and "depth" in task.scientific_question.lower():
            action_type, goal = "BOUNDARY_PROBE", "Reduce uncertainty about the depth transition region."
        elif strategy == "rule_based" and index > 0 and condition == chosen[index - 1]:
            action_type, goal = "REPLICATE", "Increase replication because the current evidence is seed-sensitive."
        elif strategy == "rule_based":
            action_type, goal = "SEARCH_COUNTEREXAMPLE", "Test whether the current claim survives a discriminative condition."
        else:
            action_type, goal = "CHANGE_INSTANCE", "Execute the frozen selection-policy condition."
        planned.append(PlannedCondition(condition, action_type, goal))
    return planned


class V03TaskRunner:
    def __init__(self, config: dict, config_hash: str, suite_hash: str, trace_root: Path, checkpoint_root: Path, executor_factory=None, run_id_factory=None, trace_metadata: dict | None = None, initial_hypothesis: dict | None = None) -> None:
        self.config = config
        self.config_hash = config_hash
        self.suite_hash = suite_hash
        self.trace_root = trace_root
        self.checkpoint_root = checkpoint_root
        self.executor_factory = executor_factory or (lambda hamiltonians, vqe_config: ActiveExperimentExecutor(hamiltonians, vqe_config))
        self.run_id_factory = run_id_factory
        self.trace_metadata = dict(trace_metadata or {})
        self.initial_hypothesis = dict(initial_hypothesis) if initial_hypothesis else None
        self.traces = {name: JsonlTrace(trace_root / f"{name}.jsonl") for name in ("runs", "actions", "experiments", "hypotheses", "evidence", "revisions", "llm_responses")}

    def run_task(self, task, strategy: str, policy_seed: int | None, git_commit: str, prompt_hash: str) -> dict:
        suffix = "det" if policy_seed is None else str(policy_seed)
        run_id = self.run_id_factory(task, strategy, suffix, self.config_hash, git_commit) if self.run_id_factory else f"V03_{task.task_id}_{strategy}_{suffix}_c{self.config_hash[:8]}_g{git_commit[:7]}"
        checkpoint = TaskCheckpoint(self.checkpoint_root / f"{run_id}.json")
        state = checkpoint.load()
        if state and state.get("complete"):
            return state["summary"] | {"resumed": True}
        completed = set((state or {}).get("completed_experiment_ids", []))
        spent = int((state or {}).get("spent", len(completed)))
        existing_experiments = [item for item in self.traces["experiments"].read_all() if item.get("run_id") == run_id]
        existing_actions = {int(item["round"]): item for item in self.traces["actions"].read_all() if item.get("run_id") == run_id}
        existing_evidence = {int(item["round"]): item for item in self.traces["evidence"].read_all() if item.get("run_id") == run_id}
        self.traces["runs"].append({
            "event": "START" if not state else "RESUME", "run_id": run_id, "task_id": task.task_id,
            "strategy": strategy, "policy_seed": policy_seed, "git_commit": git_commit,
            "config_hash": self.config_hash, "task_suite_hash": self.suite_hash,
            "prompt_hash": prompt_hash, "model": "not-live", "experiment_budget": task.budget,
        } | self.trace_metadata)
        hypothesis = dict(self.initial_hypothesis or task.initial_hypothesis or {"hypothesis_id": f"{task.task_id}.H1", "claim": "A scoped relation is proposed from initial observations.", "status": "PENDING"})
        self.traces["hypotheses"].append({"run_id": run_id, "task_id": task.task_id, "round": 0, "event": "INITIAL", **hypothesis} | self.trace_metadata)
        planned = plan_conditions(task, strategy, policy_seed)
        hamiltonians = {}
        condition_ham = {}
        for item in task.experiment_pool:
            ham = generate_ising_hamiltonian(item["num_qubits"], item["topology"], item["ham_seed"])
            hamiltonians[ham.hamiltonian_id] = ham
            condition_ham[item["condition_id"]] = ham.hamiltonian_id
        executor = self.executor_factory(hamiltonians, self.config["vqe"])
        seed_values = self.config["vqe"]["seeds"]
        action_rows, evidence_rows = [], []
        all_experiments = []
        for round_index, planned_item in enumerate(planned, start=1):
            if strategy == "rule_based":
                planned_item = select_rule_based_condition(task, round_index, evidence_rows, action_rows)
            seeds = tuple(seed_values[(round_index - 1) * 2: round_index * 2])
            condition = planned_item.condition
            action_id = f"{run_id}_ACT_{round_index:02d}"
            spec = ExperimentSpec(condition_ham[condition["condition_id"]], condition["depth"], condition["entanglement"], seeds)
            action = ResearchAction(
                action_id=f"ACT_{int(hashlib.sha256(action_id.encode()).hexdigest()[:6], 16) % 1000000:06d}",
                round=round_index, hypothesis_id=hypothesis["hypothesis_id"], action_type=planned_item.action_type,
                reason=planned_item.information_goal, experiment=spec,
                controlled_variables=tuple(task.controlled_variables), changed_variables=tuple(task.allowed_variables[:1]),
                expected_outcome="The condition changes or clarifies the current evidence label.",
                falsification_condition=task.falsification_conditions[0], information_goal=planned_item.information_goal,
            )
            action_record = action.to_dict() | {
                "run_id": run_id, "task_id": task.task_id, "condition_id": condition["condition_id"],
                "budget_before": task.budget - spent, "budget_cost": len(seeds), "budget_after": task.budget - spent - len(seeds),
                "failure_modes": diagnose_scientific_failure_modes(action.to_dict(), evidence_rows[-1:], task, action_rows),
            } | self.trace_metadata
            if round_index not in existing_actions:
                self.traces["actions"].append(action_record)
            else:
                action_record = existing_actions[round_index]
            action_rows.append(action_record)
            held_out = condition["condition_id"] in task.held_out_set
            expected_ids = {f"V02_{run_id}_R{round_index:02d}_S{seed}" for seed in seeds}
            records = [item for item in existing_experiments if item["experiment_id"] in expected_ids]
            missing_seeds = tuple(seed for seed in seeds if f"V02_{run_id}_R{round_index:02d}_S{seed}" not in completed)
            if missing_seeds:
                execution_action = ResearchAction.from_dict(action.to_dict() | {"experiment": action.experiment.to_dict() | {"seed_group": list(missing_seeds)}})
                records.extend(executor.execute(run_id, execution_action, held_out))
            for record in records:
                record["task_id"] = task.task_id
                record["condition_id"] = condition["condition_id"]
                if record["experiment_id"] not in completed:
                    self.traces["experiments"].append(record)
                    completed.add(record["experiment_id"])
                all_experiments.append(record)
                checkpoint.save({"complete": False, "spent": len(completed), "completed_experiment_ids": sorted(completed)})
            spent = len(completed)
            evidence = existing_evidence.get(round_index) or (self._judge(task, run_id, round_index, action, condition, all_experiments, held_out) | self.trace_metadata)
            if round_index not in existing_evidence:
                self.traces["evidence"].append(evidence)
            evidence_rows.append(evidence)
            if evidence["decision"] == "COUNTEREXAMPLE":
                hypothesis["status"] = "NARROWED"
            elif evidence["decision"] == "SUPPORT":
                hypothesis["status"] = "PRELIMINARY_SUPPORT"
            elif hypothesis.get("status") == "PENDING":
                hypothesis["status"] = "INCONCLUSIVE"
            self.traces["hypotheses"].append({"run_id": run_id, "task_id": task.task_id, "round": round_index, "event": "EVIDENCE_UPDATE", **hypothesis} | self.trace_metadata)
            if task.task_type in {"SCOPE_REVISION", "PROBLEM_REVISION"} and evidence["decision"] == "COUNTEREXAMPLE":
                revision = {
                    "run_id": run_id, "task_id": task.task_id, "round": round_index,
                    "parent_hypothesis_id": hypothesis["hypothesis_id"], "new_hypothesis_id": hypothesis["hypothesis_id"] + ".R1",
                    "old_claim": hypothesis["claim"], "new_claim": "The relation is conditional within the tested depth and Hamiltonian scope.",
                    "revision_reason": "COUNTEREXAMPLE under a frozen discriminative condition", "scope_change": "broad -> conditional",
                    "triggering_evidence_ids": [evidence["evidence_id"]],
                }
                self.traces["revisions"].append(revision | self.trace_metadata)
            checkpoint.save({"complete": False, "spent": spent, "completed_experiment_ids": sorted(completed)})
        validated = evaluate_validated_judgment(task, evidence_rows, action_rows, all_experiments)
        summary = {
            "run_id": run_id, "task_id": task.task_id, "task_type": task.task_type, "strategy": strategy,
            "policy_seed": policy_seed, "budget": task.budget, "budget_spent": spent,
            "successful_vqe_runs": sum(item["status"] == "SUCCESS" for item in all_experiments),
            "failed_vqe_runs": sum(item["status"] == "FAILED" for item in all_experiments),
            "final_judgment": validated.final_decision, "validated_judgment": validated.to_dict(),
            "held_out_result": next((item["decision"] for item in reversed(evidence_rows) if item["held_out"]), "NOT_COMPLETED"),
            "failure_modes": sorted({mode for item in action_rows for mode in item["failure_modes"]}),
        } | self.trace_metadata
        self.traces["runs"].append({"event": "END", **summary})
        checkpoint.save({"complete": True, "spent": spent, "completed_experiment_ids": sorted(completed), "summary": summary})
        return summary

    def _judge(self, task, run_id, round_index, action, condition, experiments, held_out) -> dict:
        current = [item for item in experiments if item.get("condition_id") == condition["condition_id"] and item["status"] == "SUCCESS"]
        controls = [item for item in experiments if item.get("condition_id") != condition["condition_id"] and item["status"] == "SUCCESS"]
        candidate = _stats(current)
        control = _stats(controls[-2:]) if controls else None
        if candidate["number_of_seeds"] < 2 or control is None or control["number_of_seeds"] < 2:
            judgment = {"decision": "INCONCLUSIVE", "rule": "insufficient_control_or_replication", "candidate": candidate, "control": control, "diagnostics": None, "thresholds": self.config["judge"]}
            codes = ["INSUFFICIENT_REPLICATION"]
        else:
            judgment = EvidenceJudge(self.config["judge"]).judge(candidate, control)
            codes = ["REPLICATED_ACROSS_SEEDS"]
            if judgment["decision"] == "COUNTEREXAMPLE": codes.append("COUNTEREXAMPLE_FOUND")
            if task.competing_hypotheses and action.action_type in {"CONTROL_DEPTH", "CONTROL_ENTANGLEMENT"}: codes.append("CONTROL_SUPPORTS_H_A" if judgment["decision"] == "SUPPORT" else "CONTROL_SUPPORTS_H_B")
            if action.action_type == "BOUNDARY_PROBE" and judgment["decision"] != "INCONCLUSIVE": codes.append("BOUNDARY_LOCALIZED")
            if held_out and judgment["decision"] != "SUPPORT": codes.append("FAILED_ON_HELD_OUT")
        return {
            "run_id": run_id, "task_id": task.task_id, "round": round_index,
            "evidence_id": f"{run_id}_EVID_{round_index:02d}", "hypothesis_id": action.hypothesis_id,
            "action_id": action.action_id, "condition_id": condition["condition_id"], "held_out": held_out,
            "experiment_ids": [item["experiment_id"] for item in current],
            "comparison": {"hamiltonian_id": action.experiment.hamiltonian_id, "condition_id": condition["condition_id"]},
            "reason_codes": codes, **judgment,
        }


def _stats(records: list[dict]) -> dict:
    errors = [float(item["energy_error"]) for item in records]
    converged = sum(bool(item.get("converged")) for item in records)
    return {
        "number_of_seeds": len(errors), "mean_energy_error": mean(errors),
        "variance_energy_error": variance(errors) if len(errors) > 1 else 0.0,
        "failure_rate": 1.0 - converged / len(errors),
    }


def select_rule_based_condition(task, round_index: int, evidence: list[dict], actions: list[dict]) -> PlannedCondition:
    """Evidence-responsive selection; held-out remains isolated until the final two rounds."""
    total_rounds = task.budget // 2
    exploration = [dict(item) for item in task.experiment_pool if item["condition_id"] in task.exploration_set]
    held_out = [dict(item) for item in task.experiment_pool if item["condition_id"] in task.held_out_set]
    if round_index > total_rounds - 2:
        condition = held_out[round_index - (total_rounds - 1)]
        return PlannedCondition(condition, "VALIDATE_HYPOTHESIS", "Validate the current judgment on an isolated condition not used for formation.")
    used_ids = [item.get("condition_id") for item in actions]
    last_evidence = evidence[-1]["decision"] if evidence else None
    last_condition = next((item for item in exploration if item["condition_id"] == used_ids[-1]), None) if used_ids else None

    if task.task_type == "REPLICATION_NEEDED" and round_index <= 4:
        condition = last_condition or exploration[0]
        return PlannedCondition(condition, "REPLICATE", "Replicate the same condition because the initial evidence is explicitly under-replicated.")
    if task.competing_hypotheses:
        condition = next((item for item in exploration if item["condition_id"] not in used_ids), exploration[round_index % len(exploration)])
        return PlannedCondition(condition, "CONTROL_DEPTH", "Discriminate the competing connectivity and depth explanations with a single-variable control.")
    if task.task_type == "BOUNDARY_TRANSITION":
        ordered = sorted(exploration, key=lambda item: (abs(int(item["depth"]) - 2), item["entanglement"]))
        condition = next((item for item in ordered if item["condition_id"] not in used_ids), ordered[round_index % len(ordered)])
        return PlannedCondition(condition, "BOUNDARY_PROBE", "Probe an adjacent depth selected from the latest evidence to localize a possible transition.")
    if last_evidence in {"INCONCLUSIVE", "WEAKEN"} and last_condition is not None:
        paired = next((item for item in exploration if item["ham_seed"] == last_condition["ham_seed"] and item["depth"] == last_condition["depth"] and item["entanglement"] != last_condition["entanglement"] and item["condition_id"] not in used_ids), None)
        if paired:
            return PlannedCondition(paired, "CONTROL_ENTANGLEMENT", "Resolve inconclusive evidence with the paired entanglement control at fixed Hamiltonian and depth.")
    if last_evidence == "COUNTEREXAMPLE":
        condition = next((item for item in exploration if item["condition_id"] not in used_ids and (last_condition is None or item["ham_seed"] != last_condition["ham_seed"])), None)
        if condition:
            return PlannedCondition(condition, "SEARCH_COUNTEREXAMPLE", "Test whether the counterexample persists on a different instance before revising scope.")
    condition = next((item for item in exploration if item["condition_id"] not in used_ids), exploration[round_index % len(exploration)])
    action_type = "SEARCH_COUNTEREXAMPLE" if last_evidence == "SUPPORT" else "CHANGE_INSTANCE"
    goal = "Actively seek a contradiction to preliminary support." if last_evidence == "SUPPORT" else "Acquire the next non-redundant observation to reduce uncertainty."
    return PlannedCondition(condition, action_type, goal)
