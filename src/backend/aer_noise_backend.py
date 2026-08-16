"""Transparent synthetic NISQ-style Aer noise backend for diagonal Ising energy."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from collections.abc import Sequence

from qiskit import QuantumCircuit
from qiskit.quantum_info import DensityMatrix, SparsePauliOp
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel, ReadoutError, depolarizing_error


@dataclass(frozen=True)
class NoiseConfig:
    noise_level_id: str
    label: str
    p_1q: float
    p_2q: float
    p_readout: float
    shots: int | None = None

    def __post_init__(self) -> None:
        if not self.noise_level_id.startswith("N"):
            raise ValueError("noise_level_id must start with N")
        for name in ("p_1q", "p_2q", "p_readout"):
            value = float(getattr(self, name))
            if not 0.0 <= value < 1.0:
                raise ValueError(f"{name} must be in [0, 1)")
        if self.shots is not None:
            raise ValueError("V0.4 freezes shots=null to avoid adding shot noise")

    def to_dict(self) -> dict:
        return asdict(self)


def build_noise_model(config: NoiseConfig) -> NoiseModel:
    """Build gate channels plus a recorded symmetric readout channel."""

    model = NoiseModel()
    if config.p_1q:
        model.add_all_qubit_quantum_error(depolarizing_error(config.p_1q, 1), ["ry"])
    if config.p_2q:
        model.add_all_qubit_quantum_error(depolarizing_error(config.p_2q, 2), ["cx"])
    if config.p_readout:
        p = config.p_readout
        model.add_all_qubit_readout_error(ReadoutError([[1.0 - p, p], [p, 1.0 - p]]))
    return model


class AerNoiseBackend:
    """Exact density-matrix expectation under gate noise and analytic readout attenuation.

    Q-Explorer Hamiltonians contain only Z and ZZ terms. Independent symmetric
    readout flips attenuate each Pauli-Z factor by ``1 - 2 p``. Applying that
    factor analytically incorporates the frozen readout channel without adding
    a second, finite-shot noise source.
    """

    name = "qiskit_aer_density_matrix_synthetic_noise"
    noisy = True
    real_hardware = False

    def __init__(self, noise_config: NoiseConfig) -> None:
        self.noise_config = noise_config
        self.noise_level_id = noise_config.noise_level_id
        self.noise_model = build_noise_model(noise_config)
        self._simulator = AerSimulator(method="density_matrix", noise_model=self.noise_model)

    def energy(
        self,
        circuit: QuantumCircuit,
        operator: SparsePauliOp,
        parameter_values: Sequence[float],
        seed_simulator: int,
    ) -> float:
        if len(parameter_values) != circuit.num_parameters:
            raise ValueError(f"Expected {circuit.num_parameters} parameter values, got {len(parameter_values)}")
        if any(char not in {"I", "Z"} for label in operator.paulis.to_labels() for char in label):
            raise ValueError("AerNoiseBackend V0.4 supports diagonal Ising I/Z operators only")
        bound = circuit.assign_parameters(parameter_values, inplace=False)
        bound.save_density_matrix()
        result = self._simulator.run(bound, seed_simulator=seed_simulator).result()
        if not result.success:
            raise RuntimeError(f"Aer noisy execution failed: {result.status}")
        density = DensityMatrix(result.data(bound)["density_matrix"])
        attenuation = 1.0 - 2.0 * self.noise_config.p_readout
        energy = 0.0
        for label, coefficient in operator.to_list():
            weight = label.count("Z")
            term = SparsePauliOp.from_list([(label, 1.0)])
            expectation = float(density.expectation_value(term).real)
            energy += float(complex(coefficient).real) * expectation * attenuation**weight
        return float(energy)

    def trace_metadata(self) -> dict:
        return {
            "noise_level_id": self.noise_level_id,
            "noise_config": self.noise_config.to_dict(),
            "noise_model": "depolarizing_1q_2q_plus_symmetric_readout",
            "readout_evaluation": "analytic_diagonal_attenuation",
            "shots": None,
            "synthetic_noise": True,
        }

    def health_check(self) -> dict:
        circuit = QuantumCircuit(1)
        circuit.x(0)
        circuit.save_density_matrix()
        result = self._simulator.run(circuit, seed_simulator=0).result()
        density = DensityMatrix(result.data(circuit)["density_matrix"])
        return {
            "backend": self.name,
            "success": bool(result.success and abs(float(density.trace().real) - 1.0) <= 1e-10),
            "density_trace": float(density.trace().real),
            **self.trace_metadata(),
        }
