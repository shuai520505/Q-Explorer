"""Deterministic local transpilation references; never a claim about account hardware."""

from __future__ import annotations

from qiskit import transpile
from qiskit.transpiler import CouplingMap

from src.ansatz import build_hea


def _count_1q_2q(circuit) -> tuple[int, int]:
    one = two = 0
    for item in circuit.data:
        arity = len(item.qubits)
        if arity == 1:
            one += 1
        elif arity == 2:
            two += 1
    return one, two


def _mapping(circuit) -> dict[str, int]:
    layout = getattr(circuit, "layout", None)
    if layout is None or layout.initial_layout is None:
        return {}
    result = {}
    for physical, virtual in layout.initial_layout.get_physical_bits().items():
        index = getattr(virtual, "_index", None)
        if index is not None:
            result[f"logical_{index}"] = int(physical)
    return dict(sorted(result.items()))


def _transpile_reference(num_qubits: int, depth: int, entanglement: str, topology: str) -> dict:
    ansatz = build_hea(num_qubits, depth, entanglement, allowed_depths=frozenset({1, 2, 3}))
    circuit = ansatz.circuit
    coupling = CouplingMap.from_full(num_qubits, bidirectional=True) if topology == "fully_connected" else CouplingMap.from_line(num_qubits, bidirectional=True)
    compiled = transpile(
        circuit,
        basis_gates=["rz", "sx", "x", "cx", "swap"],
        coupling_map=coupling,
        optimization_level=1,
        seed_transpiler=73,
    )
    logical_1q, logical_2q = _count_1q_2q(circuit)
    physical_1q, physical_two_instructions = _count_1q_2q(compiled)
    swap_count = int(compiled.count_ops().get("swap", 0))
    cx_count = int(compiled.count_ops().get("cx", 0))
    physical_2q_equivalent = cx_count + 3 * swap_count
    return {
        "reference_topology": topology,
        "actual_account_hardware": False,
        "basis_gate_reference": ["rz", "sx", "x", "cx", "swap"],
        "logical": {
            "depth": int(circuit.depth()), "num_1q_gates": logical_1q, "num_2q_gates": logical_2q,
            "gate_counts": {key: int(value) for key, value in circuit.count_ops().items()},
        },
        "physical_reference": {
            "depth": int(compiled.depth()), "num_1q_gates": physical_1q,
            "num_2q_instructions": physical_two_instructions,
            "num_2q_gate_equivalents": physical_2q_equivalent,
            "swap_count": swap_count,
            "gate_counts": {key: int(value) for key, value in compiled.count_ops().items()},
            "logical_to_physical_qubit_map": _mapping(compiled),
        },
        "routing_overhead": {
            "depth_ratio": float(compiled.depth() / max(circuit.depth(), 1)),
            "two_qubit_equivalent_ratio": float(physical_2q_equivalent / max(logical_2q, 1)),
        },
    }


def audit_candidate_transpilation(candidate: dict) -> dict:
    sides = {}
    for side in candidate["boundary_sides"]:
        configs = []
        for config in side["configs"]:
            configs.append({
                **config,
                "fully_connected_reference": _transpile_reference(candidate["num_qubits"], config["depth"], config["entanglement"], "fully_connected"),
                "linear_connectivity_stress_reference": _transpile_reference(candidate["num_qubits"], config["depth"], config["entanglement"], "linear"),
            })
        sides[side["side_id"]] = {
            "depth": side["depth"],
            "configs": configs,
            "warning": "Generic local reference only; account-native gates, connectivity, and calibration were unavailable.",
        }
    return {
        "candidate_id": candidate["candidate_id"],
        "status": "PASS_GENERIC_REFERENCE_DEVICE_MAPPING_PENDING",
        "account_device_transpilation_performed": False,
        "sides": sides,
    }
