"""Ising Hamiltonians of the form sum_i h_i Z_i + sum_ij J_ij Z_i Z_j."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Iterable

import networkx as nx
import numpy as np
from qiskit.quantum_info import SparsePauliOp


SUPPORTED_TOPOLOGIES = {"chain", "ring", "random"}


@dataclass(frozen=True)
class Coupling:
    i: int
    j: int
    value: float


@dataclass(frozen=True)
class IsingHamiltonian:
    """Serializable Ising instance with explicit qubit-indexed coefficients."""

    hamiltonian_id: str
    num_qubits: int
    topology: str
    h: tuple[float, ...]
    J: tuple[Coupling, ...]
    seed: int

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["h"] = list(self.h)
        payload["J"] = [asdict(edge) for edge in self.J]
        return payload

    @classmethod
    def from_dict(cls, payload: dict) -> "IsingHamiltonian":
        return cls(
            hamiltonian_id=payload["hamiltonian_id"],
            num_qubits=int(payload["num_qubits"]),
            topology=payload["topology"],
            h=tuple(float(value) for value in payload["h"]),
            J=tuple(Coupling(int(edge["i"]), int(edge["j"]), float(edge["value"])) for edge in payload["J"]),
            seed=int(payload["seed"]),
        )

    def to_sparse_pauli_op(self) -> SparsePauliOp:
        """Convert to Qiskit's little-endian qubit convention correctly."""

        terms: list[tuple[str, complex]] = []
        for qubit, coefficient in enumerate(self.h):
            label = ["I"] * self.num_qubits
            label[self.num_qubits - 1 - qubit] = "Z"
            terms.append(("".join(label), coefficient))
        for edge in self.J:
            label = ["I"] * self.num_qubits
            label[self.num_qubits - 1 - edge.i] = "Z"
            label[self.num_qubits - 1 - edge.j] = "Z"
            terms.append(("".join(label), edge.value))
        if not terms:
            return SparsePauliOp.from_list([("I" * self.num_qubits, 0.0)])
        return SparsePauliOp.from_list(terms).simplify()


def _interaction_edges(num_qubits: int, topology: str, seed: int, random_edge_probability: float) -> list[tuple[int, int]]:
    if topology == "chain":
        graph = nx.path_graph(num_qubits)
    elif topology == "ring":
        graph = nx.cycle_graph(num_qubits)
    elif topology == "random":
        graph = nx.gnp_random_graph(num_qubits, random_edge_probability, seed=seed, directed=False)
        if num_qubits > 1 and graph.number_of_edges() == 0:
            graph.add_edge(0, 1)
    else:
        raise ValueError(f"Unsupported topology {topology!r}; choose from {sorted(SUPPORTED_TOPOLOGIES)}")
    return sorted((min(i, j), max(i, j)) for i, j in graph.edges())


def _stable_id(num_qubits: int, topology: str, h: Iterable[float], couplings: Iterable[Coupling], seed: int) -> str:
    canonical = {
        "num_qubits": num_qubits,
        "topology": topology,
        "h": list(h),
        "J": [asdict(edge) for edge in couplings],
        "seed": seed,
    }
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12]
    return f"HAM_{digest.upper()}"


def generate_ising_hamiltonian(
    num_qubits: int,
    topology: str,
    seed: int,
    coefficient_low: float = -1.0,
    coefficient_high: float = 1.0,
    random_edge_probability: float = 0.5,
) -> IsingHamiltonian:
    """Generate a deterministic Ising instance from an explicit random seed."""

    if num_qubits < 1:
        raise ValueError("num_qubits must be positive")
    if coefficient_low >= coefficient_high:
        raise ValueError("coefficient_low must be smaller than coefficient_high")
    if not 0.0 <= random_edge_probability <= 1.0:
        raise ValueError("random_edge_probability must be in [0, 1]")
    edges = _interaction_edges(num_qubits, topology, seed, random_edge_probability)
    rng = np.random.default_rng(seed)
    fields = tuple(float(value) for value in rng.uniform(coefficient_low, coefficient_high, size=num_qubits))
    couplings = tuple(
        Coupling(i, j, float(value))
        for (i, j), value in zip(edges, rng.uniform(coefficient_low, coefficient_high, size=len(edges)), strict=True)
    )
    return IsingHamiltonian(
        hamiltonian_id=_stable_id(num_qubits, topology, fields, couplings, seed),
        num_qubits=num_qubits,
        topology=topology,
        h=fields,
        J=couplings,
        seed=seed,
    )

