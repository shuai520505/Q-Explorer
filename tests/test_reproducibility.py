from src.ansatz import build_hea
from src.backend import AerBackend
from src.exact_solver import solve_exact
from src.hamiltonian import generate_ising_hamiltonian
from src.vqe import VQEConfig, VQERunner


def test_same_seed_reproduces_vqe_energies_and_trajectory():
    hamiltonian = generate_ising_hamiltonian(4, "chain", seed=12)
    exact = solve_exact(hamiltonian).exact_ground_energy
    config = VQEConfig(max_iterations=6)
    ansatz = build_hea(4, 1, "ring")
    first = VQERunner(AerBackend(), config).run("EXP_000001", hamiltonian, ansatz, 31, exact)
    second = VQERunner(AerBackend(), config).run("EXP_000002", hamiltonian, ansatz, 31, exact)
    assert first["initial_energy"] == second["initial_energy"]
    assert first["final_energy"] == second["final_energy"]
    assert first["optimization_trajectory"] == second["optimization_trajectory"]

