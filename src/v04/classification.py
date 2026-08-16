"""Pre-registered discovery-signal classification for noisy boundary levels."""

from __future__ import annotations


DISCOVERY_SIGNALS = frozenset({
    "PRESERVED", "SHIFTED", "WEAKENED", "DISAPPEARED", "COUNTEREXAMPLE_EMERGED", "INCONCLUSIVE",
})


def classify_noise_level(metrics: dict, thresholds: dict) -> dict:
    """Return primary and secondary signals without inventing post-hoc labels."""

    scientific_rate = float(metrics["scientifically_validated_rate"])
    retention = float(metrics["boundary_retention_rate"])
    resolved = float(metrics["resolved_signature_rate"])
    no_shift = float(metrics["no_shift_rate_among_resolved"])
    magnitude_ratio = metrics.get("median_effect_magnitude_ratio")
    counterexample = float(metrics["counterexample_emergence_rate"])
    secondary = []
    if counterexample >= float(thresholds["counterexample_emergence_rate"]):
        secondary.append("COUNTEREXAMPLE_EMERGED")
    if scientific_rate <= float(thresholds["disappeared_max_scientific_rate"]) and resolved <= float(thresholds["disappeared_max_resolved_rate"]):
        primary = "DISAPPEARED"
    elif retention >= float(thresholds["preserved_min_retention"]) and no_shift >= float(thresholds["preserved_min_no_shift"]) and magnitude_ratio is not None and magnitude_ratio >= float(thresholds["preserved_min_magnitude_ratio"]):
        primary = "PRESERVED"
    elif scientific_rate >= float(thresholds["shifted_min_scientific_rate"]) and no_shift < float(thresholds["shifted_max_no_shift"]):
        primary = "SHIFTED"
    elif scientific_rate >= float(thresholds["weakened_min_scientific_rate"]) and magnitude_ratio is not None and magnitude_ratio < float(thresholds["preserved_min_magnitude_ratio"]):
        primary = "WEAKENED"
    else:
        primary = "INCONCLUSIVE"
    if primary == "INCONCLUSIVE" and "COUNTEREXAMPLE_EMERGED" in secondary:
        primary = "COUNTEREXAMPLE_EMERGED"
        secondary = []
    return {"primary": primary, "secondary": secondary}
