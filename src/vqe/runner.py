"""A deliberately small, fixed-optimizer VQE runner for controlled experiments."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

import numpy as np
from scipy.optimize import minimize

from src.ansatz import HEAResult
from src.hamiltonian import IsingHamiltonian


@dataclass(frozen=True)
class VQEConfig:
    optimizer: str = "COBYLA"
    max_iterations: int = 40
    optimizer_tolerance: float = 1e-6
    convergence_energy_error: float = 1e-3

    def __post_init__(self) -> None:
        if self.optimizer != "COBYLA":
            raise ValueError("V0.1 fixes the optimizer to COBYLA")
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be positive")


class VQERunner:
    def __init__(self, backend, config: VQEConfig) -> None:
        self.backend = backend
        self.config = config

    def run(
        self,
        experiment_id: str,
        hamiltonian: IsingHamiltonian,
        ansatz: HEAResult,
        initialization_seed: int,
        exact_energy: float,
    ) -> dict:
        """Run one seed without logging policy; orchestration records success or failure."""

        started = perf_counter()
        rng = np.random.default_rng(initialization_seed)
        initial_parameters = rng.uniform(-np.pi, np.pi, size=ansatz.num_parameters)
        operator = hamiltonian.to_sparse_pauli_op()
        trajectory: list[dict] = []

        initial_energy = self.backend.energy(
            ansatz.circuit, operator, initial_parameters, seed_simulator=initialization_seed
        )
        trajectory.append({"evaluation": 0, "phase": "initial", "energy": initial_energy})

        def objective(parameters: np.ndarray) -> float:
            energy = self.backend.energy(
                ansatz.circuit, operator, parameters, seed_simulator=initialization_seed
            )
            trajectory.append({"evaluation": len(trajectory), "phase": "optimization", "energy": energy})
            return energy

        result = minimize(
            objective,
            initial_parameters,
            method=self.config.optimizer,
            options={"maxiter": self.config.max_iterations, "tol": self.config.optimizer_tolerance},
        )
        final_energy = float(result.fun)
        energy_error = float(abs(final_energy - exact_energy))
        relative_error = float(energy_error / max(abs(exact_energy), 1e-12))
        runtime = float(perf_counter() - started)
        return {
            "experiment_id": experiment_id,
            "hamiltonian_id": hamiltonian.hamiltonian_id,
            "depth": ansatz.depth,
            "entanglement": ansatz.entanglement,
            "initialization_seed": initialization_seed,
            "exact_energy": float(exact_energy),
            "initial_energy": float(initial_energy),
            "final_energy": final_energy,
            "energy_error": energy_error,
            "relative_energy_error": relative_error,
            "optimization_steps": int(result.nfev),
            "runtime": runtime,
            "converged": bool(energy_error <= self.config.convergence_energy_error),
            "optimizer_success": bool(result.success),
            "optimizer_message": str(result.message),
            "optimization_trajectory": trajectory,
            "num_parameters": ansatz.num_parameters,
            "circuit_depth": ansatz.circuit_depth,
            "num_2q_gates": ansatz.num_2q_gates,
            "backend": self.backend.name,
            "status": "SUCCESS",
        }
