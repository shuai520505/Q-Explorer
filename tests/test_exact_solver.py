import numpy as np

from src.exact_solver import solve_exact
from src.hamiltonian.ising import Coupling, IsingHamiltonian


def test_two_qubit_exact_ground_energy():
    hamiltonian = IsingHamiltonian(
        hamiltonian_id="HAM_TEST_2Q",
        num_qubits=2,
        topology="chain",
        h=(1.0, 1.0),
        J=(Coupling(0, 1, 0.5),),
        seed=0,
    )
    solution = solve_exact(hamiltonian)
    # Energies: |00>=2.5, |01>=-0.5, |10>=-0.5, |11>=-1.5.
    assert solution.exact_ground_energy == -1.5
    assert solution.ground_state_bitstrings == ("11",)
    assert solution.degeneracy == 1


def test_exact_solver_matches_sparse_pauli_eigenspectrum():
    from src.hamiltonian import generate_ising_hamiltonian

    hamiltonian = generate_ising_hamiltonian(4, "random", seed=44)
    classical = solve_exact(hamiltonian).exact_ground_energy
    matrix_minimum = float(np.linalg.eigvalsh(hamiltonian.to_sparse_pauli_op().to_matrix())[0])
    assert np.isclose(classical, matrix_minimum, atol=1e-12)

