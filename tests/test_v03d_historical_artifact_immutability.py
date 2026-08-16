from src.v03d import compare_snapshots, snapshot_paths


def test_v03d_history_snapshot_detects_any_byte_change(tmp_path):
    path = tmp_path / "history.txt"
    path.write_text("before", encoding="utf-8")
    before = snapshot_paths(tmp_path, {"v03": ["history.txt"]})
    assert compare_snapshots(before, snapshot_paths(tmp_path, {"v03": ["history.txt"]})) == {"v03": True}
    path.write_text("after", encoding="utf-8")
    assert compare_snapshots(before, snapshot_paths(tmp_path, {"v03": ["history.txt"]})) == {"v03": False}
