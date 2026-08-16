import pytest

from src.ansatz import build_hea


def test_linear_hea_metadata():
    ansatz = build_hea(4, depth=1, entanglement="linear")
    assert ansatz.num_parameters == 4
    assert ansatz.num_2q_gates == 3
    assert ansatz.circuit_depth > 0
    assert ansatz.circuit.num_qubits == 4


def test_ring_depth_two_hea_metadata():
    ansatz = build_hea(4, depth=2, entanglement="ring")
    assert ansatz.num_parameters == 8
    assert ansatz.num_2q_gates == 8
    assert ansatz.depth == 2


@pytest.mark.parametrize("depth", [0, 3, 4])
def test_v01_rejects_out_of_scope_depth(depth):
    with pytest.raises(ValueError, match="depth 1 or 2"):
        build_hea(4, depth, "linear")

