from src.ansatz import build_hea
from src.backend import AerBackend
from src.exact_solver import solve_exact
from src.hamiltonian.ising import Coupling, IsingHamiltonian
from src.vqe import VQEConfig, VQERunner


def two_qubit_problem():
    return IsingHamiltonian("HAM_VQE_TEST", 2, "chain", (1.0, 1.0), (Coupling(0, 1, 0.5),), 0)


def test_aer_backend_health_check():
    health = AerBackend().health_check()
    assert health["success"] is True
    assert health["probability_one"] == 1.0


def test_vqe_runner_produces_complete_trajectory():
    hamiltonian = two_qubit_problem()
    exact = solve_exact(hamiltonian).exact_ground_energy
    runner = VQERunner(AerBackend(), VQEConfig(max_iterations=10, convergence_energy_error=0.5))
    result = runner.run("EXP_000001", hamiltonian, build_hea(2, 1, "linear"), 17, exact)
    required = {
        "experiment_id",
        "hamiltonian_id",
        "initial_energy",
        "final_energy",
        "energy_error",
        "relative_energy_error",
        "optimization_steps",
        "runtime",
        "converged",
        "optimization_trajectory",
    }
    assert required <= result.keys()
    assert result["status"] == "SUCCESS"
    assert result["optimization_trajectory"][0]["phase"] == "initial"
    assert len(result["optimization_trajectory"]) == result["optimization_steps"] + 1
    assert result["final_energy"] <= result["initial_energy"] + 1e-10

