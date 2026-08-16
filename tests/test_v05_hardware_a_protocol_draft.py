from src.v05_gate0 import build_hardware_a_protocol


def test_v05_hardware_a_protocol_is_draft_and_not_scientific_data():
    candidate = {
        "candidate_id": "C1", "boundary_sides": [{"side_id": "A"}, {"side_id": "B"}],
        "ansatz_config_stats": [{}, {}, {}, {}], "hamiltonian_id": ["H1", "H2"],
        "required_observables": ["Z_0"], "N0_behavior": {},
        "N1_behavior": {"primary_status": "SHIFTED"}, "N2_behavior": {"primary_status": "SHIFTED"},
        "N3_behavior": {"primary_status": "SHIFTED"}, "falsification_condition": "different ordering",
    }
    result = build_hardware_a_protocol([candidate], {})
    assert result["hardware_a_feasible_now"] is False
    assert result["candidates"][0]["scientific_data"] is False
