"""Exhaustive exact solver, intentionally limited to small V0.1 systems."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.hamiltonian import IsingHamiltonian


@dataclass(frozen=True)
class ExactSolution:
    exact_ground_energy: float
    ground_state_bitstrings: tuple[str, ...]
    degeneracy: int


def solve_exact(hamiltonian: IsingHamiltonian) -> ExactSolution:
    """Enumerate computational basis states and return the true diagonal minimum."""

    n = hamiltonian.num_qubits
    state_indices = np.arange(1 << n, dtype=np.uint64)
    bit_positions = np.arange(n, dtype=np.uint64)
    bits = ((state_indices[:, None] >> bit_positions[None, :]) & 1).astype(np.int8)
    z = 1.0 - 2.0 * bits
    energies = z @ np.asarray(hamiltonian.h, dtype=float)
    for edge in hamiltonian.J:
        energies += edge.value * z[:, edge.i] * z[:, edge.j]
    minimum = float(np.min(energies))
    ground_indices = np.flatnonzero(np.isclose(energies, minimum, rtol=0.0, atol=1e-12))
    bitstrings = tuple(format(int(index), f"0{n}b") for index in ground_indices)
    return ExactSolution(minimum, bitstrings, len(bitstrings))

