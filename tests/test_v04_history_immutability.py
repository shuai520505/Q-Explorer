from src.v03d import compare_snapshots, snapshot_paths


def test_v04_history_snapshot_covers_three_prior_stages(tmp_path):
    for name in ("v03", "v03c", "v03d"):
        (tmp_path / name).write_text(name, encoding="utf-8")
    groups = {name: [name] for name in ("v03", "v03c", "v03d")}
    before = snapshot_paths(tmp_path, groups)
    assert compare_snapshots(before, snapshot_paths(tmp_path, groups)) == {"v03": True, "v03c": True, "v03d": True}
