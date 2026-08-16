import pytest

from src.v04 import wilson_interval


def test_wilson_interval_is_bounded_and_contains_rate():
    low, high = wilson_interval(8, 15)
    assert low == pytest.approx(0.3012, abs=0.001)
    assert high == pytest.approx(0.7519, abs=0.001)
    assert low < 8 / 15 < high


def test_wilson_interval_rejects_empty_sample():
    with pytest.raises(ValueError):
        wilson_interval(0, 0)
