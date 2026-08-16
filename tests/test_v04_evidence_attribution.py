from src.v03.live_runner import LiveTaskRunner


def test_v04_live_revision_api_accepts_prior_visible_evidence():
    assert "prior_evidence" in LiveTaskRunner._update_hypothesis.__code__.co_varnames
