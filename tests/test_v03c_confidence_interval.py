from src.v03c import wilson_interval


def test_wilson_interval_is_bounded_and_contains_observed_rate():
    low, high = wilson_interval(10, 15)
    assert 0 < low < 10 / 15 < high < 1
    assert wilson_interval(0, 15)[0] == 0
    assert wilson_interval(15, 15)[1] == 1
