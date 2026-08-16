import pytest

from src.evidence import EvidenceJudge
from src.hypothesis import Hypothesis, update_hypothesis


@pytest.fixture
def judge():
    return EvidenceJudge(
        {
            "minimum_seeds": 2,
            "support_relative_improvement": 0.10,
            "counterexample_relative_worsening": 0.10,
            "variance_ratio_limit": 2.0,
            "failure_rate_difference_limit": 0.25,
            "epsilon": 1e-12,
        }
    )


def stats(mean, variance=0.001, failure=0.0, seeds=5):
    return {
        "mean_energy_error": mean,
        "variance_energy_error": variance,
        "failure_rate": failure,
        "number_of_seeds": seeds,
    }


@pytest.mark.parametrize(
    "candidate,control,decision",
    [
        (stats(0.1), stats(0.2), "SUPPORT"),
        (stats(0.21), stats(0.2), "WEAKEN"),
        (stats(0.19), stats(0.2), "INCONCLUSIVE"),
        (stats(0.3), stats(0.2), "COUNTEREXAMPLE"),
        (stats(0.1, seeds=1), stats(0.2), "INCONCLUSIVE"),
    ],
)
def test_transparent_decision_rules(judge, candidate, control, decision):
    result = judge.judge(candidate, control)
    assert result["decision"] == decision
    assert result["rule"]
    assert result["thresholds"]["minimum_seeds"] == 2


def test_hypothesis_is_updated_from_evidence(judge):
    hypothesis = Hypothesis("H001", "ring is better")
    evidence = judge.judge(stats(0.1), stats(0.2)) | {"evidence_id": "EVID_000001"}
    updated = update_hypothesis(hypothesis, evidence, ["EXP_000001", "EXP_000002"])
    assert updated.status == "PRELIMINARY_SUPPORT"
    assert updated.supporting_experiments == ["EXP_000001", "EXP_000002"]
    assert updated.revision_history[-1]["decision"] == "SUPPORT"

