from src.v04 import classify_noise_level


THRESHOLDS = {"counterexample_emergence_rate": 0.3, "disappeared_max_scientific_rate": 0.1, "disappeared_max_resolved_rate": 0.2, "preserved_min_retention": 0.5, "preserved_min_no_shift": 0.5, "preserved_min_magnitude_ratio": 0.7, "shifted_min_scientific_rate": 0.2, "shifted_max_no_shift": 0.5, "weakened_min_scientific_rate": 0.2}


def test_v04_discovery_classifier_keeps_primary_and_secondary_signals():
    preserved = classify_noise_level({"scientifically_validated_rate": 0.6, "boundary_retention_rate": 0.6, "resolved_signature_rate": 0.8, "no_shift_rate_among_resolved": 0.8, "median_effect_magnitude_ratio": 0.9, "counterexample_emergence_rate": 0.4}, THRESHOLDS)
    assert preserved == {"primary": "PRESERVED", "secondary": ["COUNTEREXAMPLE_EMERGED"]}
    disappeared = classify_noise_level({"scientifically_validated_rate": 0.0, "boundary_retention_rate": 0.0, "resolved_signature_rate": 0.1, "no_shift_rate_among_resolved": 0.0, "median_effect_magnitude_ratio": None, "counterexample_emergence_rate": 0.0}, THRESHOLDS)
    assert disappeared["primary"] == "DISAPPEARED"
