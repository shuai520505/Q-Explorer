from src.v05_gate0 import audit_candidate_transpilation


def test_v05_transpilation_audit_reports_generic_routing_overhead():
    candidate = {
        "candidate_id": "C1", "num_qubits": 4,
        "boundary_sides": [
            {"side_id": "side_A", "depth": 1, "configs": [{"depth": 1, "entanglement": "linear"}, {"depth": 1, "entanglement": "ring"}]},
            {"side_id": "side_B", "depth": 2, "configs": [{"depth": 2, "entanglement": "linear"}, {"depth": 2, "entanglement": "ring"}]},
        ],
    }
    result = audit_candidate_transpilation(candidate)
    assert result["account_device_transpilation_performed"] is False
    ring = result["sides"]["side_B"]["configs"][1]
    assert ring["linear_connectivity_stress_reference"]["routing_overhead"]["two_qubit_equivalent_ratio"] >= 1.0
