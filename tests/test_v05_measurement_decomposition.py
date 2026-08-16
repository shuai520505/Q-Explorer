from src.v05_gate0 import measurement_decomposition


def test_v05_ising_measurement_decomposition_uses_one_z_basis_group():
    result = measurement_decomposition({"num_qubits": 2, "h": [1, -1], "J": [{"i": 0, "j": 1, "value": 0.5}]})
    assert result["measurement_grouping_simple"] is True
    assert result["measurement_group_count"] == 1
    assert result["required_measurement_bases"] == ["computational_Z"]
