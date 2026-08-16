from src.v05_gate0 import estimate_hardware_b_cost


def test_v05_job_cost_estimate_is_transparent_lower_bound():
    result = estimate_hardware_b_cost(candidates=2, configs_per_candidate=4, max_iterations=40, shots=2048, repeats=3)
    assert result["estimated_circuit_executions_lower_bound"] == 960
    assert result["estimated_total_shots_lower_bound"] == 1_966_080
    assert result["hardware_b_feasibility"] == "UNCERTAIN"
