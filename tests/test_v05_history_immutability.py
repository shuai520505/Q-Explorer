from src.v03d import compare_snapshots, snapshot_paths


def test_v05_history_immutability_covers_v03_through_v04(tmp_path):
    for name in ("v03", "v03c", "v03d", "v04"):
        (tmp_path / name).write_text(name, encoding="utf-8")
    groups = {name: [name] for name in ("v03", "v03c", "v03d", "v04")}
    before = snapshot_paths(tmp_path, groups)
    assert compare_snapshots(before, snapshot_paths(tmp_path, groups)) == {name: True for name in groups}
