from src.v05_gate0 import CalibrationSnapshot


def test_v05_calibration_snapshot_preserves_unknowns():
    snapshot = CalibrationSnapshot("D1", "2026-01-01T00:00:00Z")
    assert snapshot.to_dict()["availability"] == "UNKNOWN"
    assert snapshot.to_dict()["two_qubit_errors"] == "UNKNOWN"
