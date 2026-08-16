from src.v05_gate0 import HardwareDevice, build_compatibility_rows


def test_v05_candidate_compatibility_is_unknown_without_account_devices():
    candidate = {"candidate_id": "C1", "num_qubits": 4, "required_measurement_bases": ["computational_Z"]}
    assert build_compatibility_rows([candidate], [])[0]["compatibility_status"] == "UNKNOWN"
    device = HardwareDevice(
        "D1", "gate-device", num_qubits=5, native_gate_set=["rz", "cx"],
        supports_raw_counts=True, supports_shots=True, suitability="SUITABLE_FOR_QEXPLORER_VQE",
    )
    assert build_compatibility_rows([candidate], [device])[0]["compatibility_status"] == "COMPATIBLE_WITH_TRANSPILATION"
