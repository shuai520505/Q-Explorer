"""A fixed RY rotation layer with configurable depth and CX topology."""

from __future__ import annotations

from dataclasses import dataclass

from qiskit import QuantumCircuit
from qiskit.circuit import ParameterVector


@dataclass(frozen=True)
class HEAResult:
    circuit: QuantumCircuit
    num_parameters: int
    circuit_depth: int
    num_2q_gates: int
    depth: int
    entanglement: str


def _entangling_edges(num_qubits: int, entanglement: str) -> list[tuple[int, int]]:
    if entanglement == "linear":
        return [(i, i + 1) for i in range(num_qubits - 1)]
    if entanglement == "ring":
        edges = [(i, i + 1) for i in range(num_qubits - 1)]
        if num_qubits > 2:
            edges.append((num_qubits - 1, 0))
        return edges
    raise ValueError("entanglement must be 'linear' or 'ring'")


def build_hea(
    num_qubits: int,
    depth: int,
    entanglement: str,
    *,
    allowed_depths: frozenset[int] = frozenset({1, 2}),
) -> HEAResult:
    """Build V0.1 HEA: depth repetitions of RY on all qubits then CX edges."""

    if num_qubits < 2:
        raise ValueError("HEA requires at least 2 qubits")
    if depth not in allowed_depths:
        ordered = sorted(allowed_depths)
        allowed = " or ".join(str(value) for value in ordered) if len(ordered) <= 2 else ", ".join(str(value) for value in ordered[:-1]) + f", or {ordered[-1]}"
        raise ValueError(f"This experiment supports depth {allowed} only")
    edges = _entangling_edges(num_qubits, entanglement)
    parameters = ParameterVector("theta", length=num_qubits * depth)
    circuit = QuantumCircuit(num_qubits, name=f"hea_d{depth}_{entanglement}")
    offset = 0
    for _ in range(depth):
        for qubit in range(num_qubits):
            circuit.ry(parameters[offset], qubit)
            offset += 1
        for control, target in edges:
            circuit.cx(control, target)
    num_2q_gates = sum(count for instruction, count in circuit.count_ops().items() if instruction in {"cx", "cz", "ecr", "swap"})
    return HEAResult(circuit, circuit.num_parameters, circuit.depth(), num_2q_gates, depth, entanglement)
