"""V0.1 evidence rules: deterministic and fully inspectable, never LLM-based."""

from __future__ import annotations


ALLOWED_DECISIONS = {"SUPPORT", "WEAKEN", "INCONCLUSIVE", "COUNTEREXAMPLE"}


class EvidenceJudge:
    """Judge whether candidate A has lower error than control B."""

    def __init__(self, thresholds: dict) -> None:
        required = {
            "minimum_seeds",
            "support_relative_improvement",
            "counterexample_relative_worsening",
            "variance_ratio_limit",
            "failure_rate_difference_limit",
            "epsilon",
        }
        missing = required - thresholds.keys()
        if missing:
            raise ValueError(f"Missing evidence thresholds: {sorted(missing)}")
        self.thresholds = dict(thresholds)

    def judge(self, candidate: dict, control: dict) -> dict:
        """Return one allowed decision plus all numeric inputs and triggered rule."""

        minimum = int(self.thresholds["minimum_seeds"])
        if candidate["number_of_seeds"] < minimum or control["number_of_seeds"] < minimum:
            return self._result("INCONCLUSIVE", "insufficient_seeds", candidate, control, None)

        epsilon = float(self.thresholds["epsilon"])
        relative_improvement = (control["mean_energy_error"] - candidate["mean_energy_error"]) / max(
            abs(control["mean_energy_error"]), epsilon
        )
        candidate_variance = float(candidate["variance_energy_error"])
        control_variance = float(control["variance_energy_error"])
        variance_acceptable = candidate_variance <= max(
            control_variance * float(self.thresholds["variance_ratio_limit"]), epsilon
        )
        failure_acceptable = candidate["failure_rate"] <= (
            control["failure_rate"] + float(self.thresholds["failure_rate_difference_limit"])
        )

        if relative_improvement <= -float(self.thresholds["counterexample_relative_worsening"]):
            decision, rule = "COUNTEREXAMPLE", "relative_worsening_threshold"
        elif (
            relative_improvement >= float(self.thresholds["support_relative_improvement"])
            and variance_acceptable
            and failure_acceptable
        ):
            decision, rule = "SUPPORT", "improvement_with_stability"
        elif relative_improvement < 0 or not variance_acceptable or not failure_acceptable:
            decision, rule = "WEAKEN", "negative_trend_or_instability"
        else:
            decision, rule = "INCONCLUSIVE", "effect_below_support_threshold"
        diagnostics = {
            "relative_improvement": float(relative_improvement),
            "variance_acceptable": bool(variance_acceptable),
            "failure_rate_acceptable": bool(failure_acceptable),
        }
        return self._result(decision, rule, candidate, control, diagnostics)

    def _result(self, decision: str, rule: str, candidate: dict, control: dict, diagnostics: dict | None) -> dict:
        if decision not in ALLOWED_DECISIONS:
            raise RuntimeError(f"Internal invalid decision: {decision}")
        return {
            "decision": decision,
            "rule": rule,
            "candidate": dict(candidate),
            "control": dict(control),
            "diagnostics": diagnostics,
            "thresholds": dict(self.thresholds),
        }

