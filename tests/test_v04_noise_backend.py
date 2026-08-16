import numpy as np

from src.ansatz import build_hea
from src.backend import AerBackend, AerNoiseBackend, NoiseConfig
from src.hamiltonian import generate_ising_hamiltonian


def test_v04_noise_backend_runs_and_differs_from_ideal():
    ham = generate_ising_hamiltonian(4, "chain", 14)
    ansatz = build_hea(4, 1, "linear")
    parameters = np.linspace(-0.5, 0.5, ansatz.num_parameters)
    ideal = AerBackend().energy(ansatz.circuit, ham.to_sparse_pauli_op(), parameters, 1)
    noisy = AerNoiseBackend(NoiseConfig("N2", "medium", 0.001, 0.01, 0.01)).energy(ansatz.circuit, ham.to_sparse_pauli_op(), parameters, 1)
    assert np.isfinite(noisy)
    assert not np.isclose(noisy, ideal, atol=1e-8)
