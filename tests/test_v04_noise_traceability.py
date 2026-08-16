from src.backend import AerNoiseBackend, NoiseConfig
from src.hamiltonian import generate_ising_hamiltonian
from src.research import ActiveExperimentExecutor, ExperimentSpec, ResearchAction


def test_v04_every_noisy_experiment_records_full_noise_config():
    ham = generate_ising_hamiltonian(4, "chain", 24)
    backend = AerNoiseBackend(NoiseConfig("N1", "low", 0.0005, 0.005, 0.005))
    executor = ActiveExperimentExecutor({ham.hamiltonian_id: ham}, {"optimizer": "COBYLA", "max_iterations": 6, "optimizer_tolerance": 1e-6, "convergence_energy_error": 1e-2}, backend)
    action = ResearchAction("ACT_000001", 1, "H", "BOUNDARY_PROBE", "probe", ExperimentSpec(ham.hamiltonian_id, 1, "linear", (1,)), ("hamiltonian",), ("depth",), "effect", "no effect", "boundary")
    record = executor.execute("RUN", action, False)[0]
    assert record["noise_level_id"] == "N1"
    assert record["noise_config"]["p_2q"] == 0.005
    assert record["configuration"]["backend"]["shots"] is None
