from src.research import Observation


def test_v04_agent_noise_metadata_contains_no_future_or_n0_outcomes():
    metadata = {"noise_present": True, "noise_level_id": "N2", "synthetic": True}
    forbidden = {"validated_rate", "future_results", "held_out_result", "n0_successful_runs"}
    assert not forbidden & metadata.keys()
    assert "environment_metadata" in Observation.__dataclass_fields__
