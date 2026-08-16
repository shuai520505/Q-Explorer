import numpy as np
import pytest

from src.hamiltonian import generate_ising_hamiltonian


@pytest.mark.parametrize("topology,expected_edges", [("chain", 3), ("ring", 4)])
def test_structured_topology_edge_counts(topology, expected_edges):
    hamiltonian = generate_ising_hamiltonian(4, topology, seed=7)
    assert len(hamiltonian.J) == expected_edges
    assert hamiltonian.num_qubits == 4
    assert hamiltonian.topology == topology


def test_generator_is_reproducible_and_seed_sensitive():
    first = generate_ising_hamiltonian(4, "random", seed=19)
    repeat = generate_ising_hamiltonian(4, "random", seed=19)
    different = generate_ising_hamiltonian(4, "random", seed=20)
    assert first == repeat
    assert first.hamiltonian_id == repeat.hamiltonian_id
    assert first.hamiltonian_id != different.hamiltonian_id
    assert len(first.J) >= 1


def test_sparse_pauli_operator_is_hermitian():
    hamiltonian = generate_ising_hamiltonian(4, "ring", seed=3)
    matrix = hamiltonian.to_sparse_pauli_op().to_matrix()
    np.testing.assert_allclose(matrix, matrix.conj().T, atol=1e-12)


def test_invalid_topology_is_rejected():
    with pytest.raises(ValueError, match="Unsupported topology"):
        generate_ising_hamiltonian(4, "full", seed=1)

