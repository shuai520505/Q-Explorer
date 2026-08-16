"""Live-LLM task execution with strict fact/decision separation."""

from __future__ import annotations

import hashlib
from pathlib import Path

from src.hamiltonian import generate_ising_hamiltonian
from src.logging import JsonlTrace
from src.research import (
    ACTION_TYPES,
    ActiveExperimentExecutor,
    ActionValidationError,
    LLMResearchAgent,
    Observation,
    ResearchAction,
    ResearchState,
)
from src.v03.checkpoint import TaskCheckpoint
from src.v03.diagnostics import diagnose_scientific_failure_modes
from src.v03.runner import V03TaskRunner
from src.v03.validation import evaluate_validated_judgment


class LiveTaskRunner:
    """Execute LLM decisions while Q-Explorer owns experiments and evidence."""

    def __init__(self, config, config_hash, suite_hash, trace_root, checkpoint_root, agent: LLMResearchAgent, live_config_hash: str | None = None, trace_metadata: dict | None = None, executor_factory=None, run_id_factory=None, initial_hypothesis: dict | None = None, environment_metadata: dict | None = None) -> None:
        self.config = config
        self.config_hash = config_hash
        self.suite_hash = suite_hash
        self.agent = agent
        self.live_config_hash = live_config_hash
        self.trace_metadata = dict(trace_metadata or {})
        self.executor_factory = executor_factory or (lambda hamiltonians, vqe_config: ActiveExperimentExecutor(hamiltonians, vqe_config))
        self.run_id_factory = run_id_factory
        self.initial_hypothesis = dict(initial_hypothesis) if initial_hypothesis else None
        self.environment_metadata = dict(environment_metadata or {})
        self.fact_runner = V03TaskRunner(config, config_hash, suite_hash, Path(trace_root), Path(checkpoint_root))
        self.canonical = self.fact_runner.traces
        self.live = {
            name: JsonlTrace(Path(trace_root) / f"live_llm_{name}.jsonl")
            for name in ("runs", "actions", "responses")
        }

    def run_task(self, task, run_seed: int, git_commit: str, prompt_hash: str, max_rounds: int | None = None) -> dict:
        run_id = self.run_id_factory(task, run_seed, self.config_hash, git_commit) if self.run_id_factory else f"V03_{task.task_id}_llm_{run_seed}_c{self.config_hash[:8]}_g{git_commit[:7]}"
        checkpoint = TaskCheckpoint(self.fact_runner.checkpoint_root / f"{run_id}.json")
        saved = checkpoint.load()
        if saved and saved.get("complete"):
            return saved["summary"] | {"resumed": True}
        completed = set((saved or {}).get("completed_experiment_ids", []))
        old_experiments = [row for row in self.canonical["experiments"].read_all() if row.get("run_id") == run_id]
        old_actions = {int(row["round"]): row for row in self.canonical["actions"].read_all() if row.get("run_id") == run_id}
        old_evidence = {int(row["round"]): row for row in self.canonical["evidence"].read_all() if row.get("run_id") == run_id}
        model = getattr(self.agent.provider, "model", "unknown")
        self._append("runs", {
            "event": "START" if not saved else "RESUME", "run_id": run_id, "task_id": task.task_id,
            "strategy": "llm", "run_seed": run_seed, "git_commit": git_commit,
            "config_hash": self.config_hash, "task_suite_hash": self.suite_hash,
            "live_config_hash": self.live_config_hash,
            "prompt_hash": prompt_hash, "prompt_version": self.agent.prompt_version,
            "model": model, "experiment_budget": task.budget, "live_llm_used": True,
        } | self.trace_metadata)

        hamiltonians, condition_ham = {}, {}
        for item in task.experiment_pool:
            ham = generate_ising_hamiltonian(item["num_qubits"], item["topology"], item["ham_seed"])
            hamiltonians[ham.hamiltonian_id] = ham
            condition_ham[item["condition_id"]] = ham.hamiltonian_id
        executor = self.executor_factory(hamiltonians, self.config["vqe"])
        hypothesis = dict(self.initial_hypothesis or task.initial_hypothesis or {
            "hypothesis_id": f"{task.task_id}.H1", "claim": "A scoped relation remains to be proposed.", "status": "PENDING",
        })
        hypothesis["scientific_question"] = task.scientific_question
        hypothesis["initial_observation"] = list(task.initial_observation)
        hypothesis["competing_hypotheses"] = list(task.competing_hypotheses)
        if not old_actions:
            self.canonical["hypotheses"].append({"run_id": run_id, "task_id": task.task_id, "round": 0, "event": "INITIAL", **hypothesis} | self.trace_metadata)

        actions, evidence, experiments = [], [], []
        total_usage, total_latency, invalid = {}, 0.0, 0
        total_rounds = task.budget // 2
        rounds = total_rounds if max_rounds is None else min(total_rounds, int(max_rounds))
        for round_index in range(1, rounds + 1):
            validation_phase = max_rounds is None and round_index > total_rounds - 2
            seeds = tuple(self.config["vqe"]["seeds"][(round_index - 1) * 2:round_index * 2])
            if len(seeds) != 2:
                raise RuntimeError("Frozen V0.3 seed policy cannot fund this round")
            action_record = old_actions.get(round_index)
            if action_record is None:
                observation = self._observation(task, hypothesis, round_index, task.budget - len(completed), validation_phase, seeds, condition_ham, actions, evidence, experiments)
                validator = lambda action: self._validate_action(action, task, validation_phase, seeds, observation)
                response = self.agent.request_action(observation, _action_id(run_id, round_index), validator)
                response_record = {
                    "event": "RESPONSE", "run_id": run_id, "task_id": task.task_id, "round": round_index,
                    "request_id": response.request_id, "model": response.model,
                    "raw_response": response.raw_response, "response_hash": response.raw_response_hash,
                    "structured_action": None if response.action is None else response.action.to_dict(),
                    "confidence": response.confidence, "hypothesis_proposal": response.hypothesis_proposal,
                    "validation_result": response.validation_status, "validation_error": response.error,
                    "repair_attempted": response.repair_attempted,
                    "repair_success": bool(response.repair_attempted and response.action is not None),
                    "latency_seconds": response.latency_seconds, "usage": response.usage,
                    "reasoning_content_present": response.reasoning_content_present,
                    "reasoning_content_hash": response.reasoning_content_hash,
                } | self.trace_metadata
                self.live["responses"].append(response_record)
                self.canonical["llm_responses"].append(response_record)
                if response.action is None:
                    invalid += 1
                    return self._failed(task, run_id, run_seed, completed, invalid, checkpoint)
                action = response.action
                for key, value in (response.usage or {}).items():
                    total_usage[key] = total_usage.get(key, 0) + int(value)
                total_latency += float(response.latency_seconds or 0.0)
                condition = self._condition(task, action, condition_ham)
                action_record = action.to_dict() | {
                    "run_id": run_id, "task_id": task.task_id, "condition_id": condition["condition_id"],
                    "budget_before": task.budget - len(completed), "budget_cost": action.budget_cost,
                    "budget_after": task.budget - len(completed) - action.budget_cost,
                    "confidence": response.confidence, "selection_policy": "live_llm",
                    "failure_modes": diagnose_scientific_failure_modes(action.to_dict(), evidence[-1:], task, actions),
                    "visible_evidence_ids": [row["evidence_id"] for row in evidence],
                } | self.trace_metadata
                self._append("actions", action_record)
            else:
                action = ResearchAction.from_dict({key: action_record[key] for key in ResearchAction.__dataclass_fields__})
                condition = self._condition(task, action, condition_ham)
            actions.append(action_record)

            held_out = condition["condition_id"] in task.held_out_set
            expected = {f"V02_{run_id}_R{round_index:02d}_S{seed}" for seed in seeds}
            records = [row for row in old_experiments if row["experiment_id"] in expected]
            missing = tuple(seed for seed in seeds if f"V02_{run_id}_R{round_index:02d}_S{seed}" not in completed)
            if missing:
                execution_action = ResearchAction.from_dict(action.to_dict() | {"experiment": action.experiment.to_dict() | {"seed_group": list(missing)}})
                records.extend(executor.execute(run_id, execution_action, held_out))
            for record in records:
                record["task_id"], record["condition_id"] = task.task_id, condition["condition_id"]
                if record["experiment_id"] not in completed:
                    self.canonical["experiments"].append(record)
                    completed.add(record["experiment_id"])
                experiments.append(record)
                checkpoint.save({"complete": False, "completed_experiment_ids": sorted(completed)})

            evidence_row = old_evidence.get(round_index) or (self.fact_runner._judge(task, run_id, round_index, action, condition, experiments, held_out) | self.trace_metadata)
            if round_index not in old_evidence:
                self.canonical["evidence"].append(evidence_row)
            evidence.append(evidence_row)
            hypothesis = self._update_hypothesis(task, run_id, round_index, hypothesis, action, evidence_row, evidence[:-1])
            self.canonical["hypotheses"].append({"run_id": run_id, "task_id": task.task_id, "round": round_index, "event": "EVIDENCE_UPDATE", **hypothesis} | self.trace_metadata)
            checkpoint.save({"complete": False, "completed_experiment_ids": sorted(completed)})

        full = max_rounds is None
        judgment = evaluate_validated_judgment(task, evidence, actions, experiments) if full else None
        feedback_changed = any(
            evidence[index - 1]["decision"] != "INCONCLUSIVE"
            and (actions[index]["action_type"], actions[index]["condition_id"]) != (actions[index - 1]["action_type"], actions[index - 1]["condition_id"])
            for index in range(1, len(actions))
        )
        summary = {
            "run_id": run_id, "task_id": task.task_id, "task_type": task.task_type, "strategy": "llm", "run_seed": run_seed,
            "budget": task.budget, "budget_spent": len(completed),
            "successful_vqe_runs": sum(row["status"] == "SUCCESS" for row in experiments),
            "failed_vqe_runs": sum(row["status"] == "FAILED" for row in experiments),
            "final_judgment": judgment.final_decision if judgment else "SMOKE_ONLY",
            "validated_judgment": judgment.to_dict() if judgment else {"validated": False, "reason_codes": ["SMOKE_ONLY"]},
            "held_out_result": next((row["decision"] for row in reversed(evidence) if row["held_out"]), "NOT_COMPLETED"),
            "failure_modes": sorted({mode for row in actions for mode in row["failure_modes"]}),
            "llm_calls": len(actions), "invalid_responses": invalid, "token_usage": total_usage,
            "decision_latency_seconds": total_latency, "feedback_changed_action": feedback_changed, "model": model,
        } | self.trace_metadata
        self._append("runs", {"event": "END" if full else "SMOKE_END", **summary})
        checkpoint.save({"complete": full, "completed_experiment_ids": sorted(completed), "summary": summary})
        return summary

    def _observation(self, task, hypothesis, round_index, remaining, validation_phase, seeds, condition_ham, actions, evidence, experiments):
        visible_ids = set(task.held_out_set if validation_phase else task.exploration_set)
        used = {row["condition_id"] for row in actions}
        conditions = []
        for item in task.experiment_pool:
            if item["condition_id"] in visible_ids:
                conditions.append({
                    "condition_id": item["condition_id"], "set": "held_out_validation" if validation_phase else "exploration",
                    "hamiltonian_id": condition_ham[item["condition_id"]], "num_qubits": item["num_qubits"],
                    "topology": item["topology"], "depth": item["depth"], "entanglement": item["entanglement"],
                    "seed_group": list(seeds),
                })
        tested = [row for row in conditions if row["condition_id"] in used]
        untested = [row for row in conditions if row["condition_id"] not in used] or conditions
        active_id = hypothesis["hypothesis_id"]
        support = tuple(exp for row in evidence if row["decision"] == "SUPPORT" for exp in row["experiment_ids"])
        counters = tuple(exp for row in evidence if row["decision"] == "COUNTEREXAMPLE" for exp in row["experiment_ids"])
        state = ResearchState(
            round=round_index, current_hypotheses=(hypothesis,), hypothesis_status={active_id: hypothesis["status"]},
            supporting_experiments={active_id: support}, counterexamples={active_id: counters},
            recent_experiments=tuple(_experiment_summary(row) for row in experiments[-6:]),
            tested_regions=tuple(tested), untested_regions=tuple(untested), remaining_budget=remaining,
            available_actions=("VALIDATE_HYPOTHESIS",) if validation_phase else tuple(sorted(ACTION_TYPES - {"STOP", "VALIDATE_HYPOTHESIS"})),
            hamiltonian_features={row["hamiltonian_id"]: {"topology": row["topology"], "num_qubits": row["num_qubits"]} for row in conditions},
            aggregate_statistics=(), previous_agent_actions=tuple(_action_summary(row) for row in actions[-6:]),
            recent_evidence=tuple(_evidence_summary(row) for row in evidence[-4:]), held_out_ids=(),
            environment_metadata=self.environment_metadata,
        )
        return Observation.from_state(state, active_id)

    def _validate_action(self, action, task, validation_phase, seeds, observation):
        if action.experiment is None:
            raise ActionValidationError("STOP is not allowed before the frozen budget is consumed")
        if action.experiment.seed_group != seeds:
            raise ActionValidationError(f"seed_group must equal offered frozen seeds {list(seeds)}")
        if validation_phase != (action.action_type == "VALIDATE_HYPOTHESIS"):
            raise ActionValidationError("VALIDATE_HYPOTHESIS is allowed only in the reserved held-out phase")
        allowed = list(observation.untested_conditions)
        if action.action_type == "REPLICATE":
            allowed += list(observation.tested_conditions)
        if not any(row["hamiltonian_id"] == action.experiment.hamiltonian_id and int(row["depth"]) == action.experiment.depth and row["entanglement"] == action.experiment.entanglement for row in allowed):
            raise ActionValidationError("experiment must match one currently visible frozen condition")
        visible_hypotheses = {task.initial_hypothesis["hypothesis_id"]} if task.initial_hypothesis else {f"{task.task_id}.H1"}
        if self.initial_hypothesis:
            visible_hypotheses.add(self.initial_hypothesis["hypothesis_id"])
        visible_hypotheses |= {item["hypothesis_id"] for item in task.competing_hypotheses}
        if action.hypothesis_id not in visible_hypotheses and not action.hypothesis_id.endswith(".R1"):
            raise ActionValidationError("hypothesis_id is not in the visible research state")

    @staticmethod
    def _condition(task, action, condition_ham):
        matches = [item for item in task.experiment_pool if condition_ham[item["condition_id"]] == action.experiment.hamiltonian_id and int(item["depth"]) == action.experiment.depth and item["entanglement"] == action.experiment.entanglement]
        if len(matches) != 1:
            raise ActionValidationError("action does not identify exactly one frozen condition")
        return matches[0]

    def _update_hypothesis(self, task, run_id, round_index, hypothesis, action, evidence, prior_evidence=None):
        updated = dict(hypothesis)
        if evidence["decision"] == "COUNTEREXAMPLE":
            updated["status"] = "NARROWED"
        elif evidence["decision"] == "SUPPORT":
            updated["status"] = "PRELIMINARY_SUPPORT"
        elif updated.get("status") == "PENDING":
            updated["status"] = "INCONCLUSIVE"
        if action.action_type == "REVISE_HYPOTHESIS" and action.revision_proposal:
            new_id = action.hypothesis_id + ".R1"
            self.canonical["revisions"].append({
                "run_id": run_id, "task_id": task.task_id, "round": round_index,
                "parent_hypothesis_id": action.hypothesis_id, "new_hypothesis_id": new_id,
                "old_claim": hypothesis["claim"], "new_claim": action.revision_proposal["new_claim"],
                "revision_reason": action.reason, "scope_change": action.revision_proposal["scope_change"],
                "triggering_evidence_ids": [row["evidence_id"] for row in (prior_evidence or [])],
                "produced_evidence_id": evidence["evidence_id"],
            } | self.trace_metadata)
            updated["hypothesis_id"], updated["claim"] = new_id, action.revision_proposal["new_claim"]
        return updated

    def _append(self, name, record):
        self.live[name].append(record)
        self.canonical[name].append(record)

    def _failed(self, task, run_id, run_seed, completed, invalid, checkpoint):
        summary = {
            "run_id": run_id, "task_id": task.task_id, "task_type": task.task_type, "strategy": "llm", "run_seed": run_seed,
            "budget": task.budget, "budget_spent": len(completed), "successful_vqe_runs": len(completed), "failed_vqe_runs": 0,
            "final_judgment": "INVALID_ACTION", "validated_judgment": {"validated": False, "reason_codes": ["INVALID_ACTION"]},
            "held_out_result": "NOT_COMPLETED", "failure_modes": ["INVALID_ACTION"], "llm_calls": 1,
            "invalid_responses": invalid, "feedback_changed_action": False,
        } | self.trace_metadata
        self._append("runs", {"event": "FAILED", **summary})
        checkpoint.save({"complete": True, "completed_experiment_ids": sorted(completed), "summary": summary})
        return summary


def _action_id(run_id, round_index):
    return f"ACT_{int(hashlib.sha256(f'{run_id}:{round_index}'.encode()).hexdigest()[:8], 16) % 1000000:06d}"


def _experiment_summary(row):
    return {key: row.get(key) for key in ("experiment_id", "condition_id", "hamiltonian_id", "depth", "entanglement", "initialization_seed", "energy_error", "converged", "status", "held_out")}


def _action_summary(row):
    return {key: row.get(key) for key in ("action_id", "round", "action_type", "condition_id", "information_goal")}


def _evidence_summary(row):
    return {key: row.get(key) for key in ("evidence_id", "round", "decision", "condition_id", "reason_codes", "experiment_ids")}
