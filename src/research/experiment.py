"""Shared Aer experiment executor and transparent V0.2 evidence extension."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from src.ansatz import build_hea
from src.backend import AerBackend
from src.evidence import EvidenceJudge, aggregate_experiments
from src.exact_solver import solve_exact
from src.hamiltonian import IsingHamiltonian
from src.research.models import ResearchAction
from src.vqe import VQEConfig, VQERunner


@dataclass
class ActiveExperimentExecutor:
    hamiltonians: dict[str, IsingHamiltonian]
    vqe_config: dict
    backend: object | None = None

    def __post_init__(self) -> None:
        self.backend = self.backend or AerBackend()
        self.runner = VQERunner(
            self.backend,
            VQEConfig(
                optimizer=self.vqe_config["optimizer"],
                max_iterations=int(self.vqe_config["max_iterations"]),
                optimizer_tolerance=float(self.vqe_config["optimizer_tolerance"]),
                convergence_energy_error=float(self.vqe_config["convergence_energy_error"]),
            ),
        )
        self.exact = {identifier: solve_exact(hamiltonian).exact_ground_energy for identifier, hamiltonian in self.hamiltonians.items()}

    def execute(self, run_id: str, action: ResearchAction, held_out: bool) -> list[dict]:
        if action.experiment is None:
            return []
        spec = action.experiment
        hamiltonian = self.hamiltonians[spec.hamiltonian_id]
        ansatz = build_hea(hamiltonian.num_qubits, spec.depth, spec.entanglement, allowed_depths=frozenset({1, 2, 3}))
        records = []
        for seed in spec.seed_group:
            experiment_id = f"V02_{run_id}_R{action.round:02d}_S{seed}"
            started = perf_counter()
            try:
                outcome = self.runner.run(experiment_id, hamiltonian, ansatz, seed, self.exact[spec.hamiltonian_id])
                record = outcome | {"error_type": None, "error_message": None}
            except Exception as exc:
                record = {
                    "experiment_id": experiment_id,
                    "hamiltonian_id": spec.hamiltonian_id,
                    "depth": spec.depth,
                    "entanglement": spec.entanglement,
                    "initialization_seed": seed,
                    "exact_energy": self.exact[spec.hamiltonian_id],
                    "initial_energy": None,
                    "final_energy": None,
                    "energy_error": None,
                    "relative_energy_error": None,
                    "optimization_steps": 0,
                    "runtime": perf_counter() - started,
                    "converged": False,
                    "optimization_trajectory": [],
                    "num_parameters": ansatz.num_parameters,
                    "circuit_depth": ansatz.circuit_depth,
                    "num_2q_gates": ansatz.num_2q_gates,
                    "backend": self.backend.name,
                    "status": "FAILED",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            record.update(
                {
                    "run_id": run_id,
                    "round": action.round,
                    "action_id": action.action_id,
                    "held_out": held_out,
                    "configuration": {
                        "hamiltonian": hamiltonian.to_dict(),
                        "ansatz": {"rotation": "ry", "depth": spec.depth, "entanglement": spec.entanglement},
                        "vqe": dict(self.vqe_config) | {"initialization_seed": seed},
                        "backend": self.backend.trace_metadata() if hasattr(self.backend, "trace_metadata") else {
                            "backend": self.backend.name, "noisy": bool(self.backend.noisy), "shots": None,
                        },
                    },
                }
            )
            if hasattr(self.backend, "trace_metadata"):
                record.update(self.backend.trace_metadata())
            records.append(record)
        return records


def judge_current_comparison(
    experiments: list[dict],
    action: ResearchAction,
    hypothesis_id: str,
    thresholds: dict,
    evidence_id: str,
    held_out: bool,
) -> dict:
    """Compare cumulative ring vs linear observations at the action's fixed condition."""

    spec = action.experiment
    matching_records = [
        record for record in experiments
        if record.get("run_id") == experiments[-1].get("run_id")
        and record.get("hamiltonian_id") == spec.hamiltonian_id
        and int(record.get("depth")) == spec.depth
    ]
    aggregates = {item["entanglement"]: item for item in aggregate_experiments(matching_records)}
    minimum = int(thresholds["minimum_seeds"])
    if not {"linear", "ring"} <= set(aggregates) or any(aggregates[name]["number_of_seeds"] < minimum for name in ("linear", "ring")):
        judgment = {
            "decision": "INCONCLUSIVE",
            "rule": "insufficient_paired_replication",
            "candidate": aggregates.get("ring"),
            "control": aggregates.get("linear"),
            "diagnostics": None,
            "thresholds": dict(thresholds),
        }
        reason_codes = ["INSUFFICIENT_REPLICATION"]
    else:
        judgment = EvidenceJudge(thresholds).judge(aggregates["ring"], aggregates["linear"])
        reason_codes = _reason_codes(judgment, held_out)
    return {
        "evidence_id": evidence_id,
        "round": action.round,
        "hypothesis_id": hypothesis_id,
        "action_id": action.action_id,
        "comparison": {"candidate": "ring", "control": "linear", "hamiltonian_id": spec.hamiltonian_id, "depth": spec.depth},
        "experiment_ids": [record["experiment_id"] for record in matching_records],
        "held_out": held_out,
        "reason_codes": reason_codes,
        **judgment,
    }


def _reason_codes(judgment: dict, held_out: bool) -> list[str]:
    decision = judgment["decision"]
    codes = []
    if judgment.get("candidate", {}).get("number_of_seeds", 0) >= 2 and judgment.get("control", {}).get("number_of_seeds", 0) >= 2:
        codes.append("REPLICATED_ACROSS_SEEDS")
    if decision == "SUPPORT":
        codes.append("CONTROL_SUPPORTS_ASSOCIATION")
    elif decision == "COUNTEREXAMPLE":
        codes.append("COUNTEREXAMPLE_FOUND")
    elif decision in {"WEAKEN", "INCONCLUSIVE"}:
        codes.append("EFFECT_NOT_ABOVE_VARIANCE")
    if held_out:
        codes.append("HELD_OUT_REPLICATED" if decision == "SUPPORT" else "FAILED_ON_HELD_OUT")
    return codes
