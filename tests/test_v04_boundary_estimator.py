from src.v04 import BoundarySignature, shift_category


def signature(location):
    region = None if location is None else (int(location - 0.5), int(location + 0.5))
    return BoundarySignature("R", "N", True, region, location, "RING_WORSE", 1.0, 0.1, (), (), (), "SUPPORT", "H")


def test_v04_shift_categories_are_frozen_and_transparent():
    assert shift_category(signature(2.5), signature(2.5), 1.0) == ("NO_SHIFT", 0.0)
    assert shift_category(signature(2.5), signature(1.5), 1.0) == ("SMALL_SHIFT", 1.0)
    assert shift_category(signature(2.5), signature(None), 1.0) == ("UNRESOLVED", None)
