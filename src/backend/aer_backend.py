"""Noiseless statevector execution backed by Qiskit Aer."""

from __future__ import annotations

from collections.abc import Sequence

from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp, Statevector
from qiskit_aer import AerSimulator


class AerBackend:
    """Evaluate exact ansatz expectation values using an Aer statevector job."""

    name = "qiskit_aer_statevector"
    noisy = False
    real_hardware = False

    def __init__(self) -> None:
        self._simulator = AerSimulator(method="statevector")

    def energy(
        self,
        circuit: QuantumCircuit,
        operator: SparsePauliOp,
        parameter_values: Sequence[float],
        seed_simulator: int,
    ) -> float:
        if len(parameter_values) != circuit.num_parameters:
            raise ValueError(f"Expected {circuit.num_parameters} parameter values, got {len(parameter_values)}")
        bound = circuit.assign_parameters(parameter_values, inplace=False)
        bound.save_statevector()
        job = self._simulator.run(bound, seed_simulator=seed_simulator)
        result = job.result()
        if not result.success:
            raise RuntimeError(f"Aer execution failed: {result.status}")
        statevector = Statevector(result.get_statevector(bound))
        return float(statevector.expectation_value(operator).real)

    def health_check(self) -> dict:
        circuit = QuantumCircuit(1)
        circuit.x(0)
        circuit.save_statevector()
        result = self._simulator.run(circuit, seed_simulator=0).result()
        statevector = Statevector(result.get_statevector(circuit))
        probability_one = float(statevector.probabilities()[1])
        return {
            "backend": self.name,
            "success": bool(result.success and abs(probability_one - 1.0) <= 1e-12),
            "probability_one": probability_one,
            "status": str(result.status),
        }

