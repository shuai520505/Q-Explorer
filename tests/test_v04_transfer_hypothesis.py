import json
from pathlib import Path


def test_v04_transfer_hypothesis_is_programmatic_and_scoped():
    path = Path("results/v04/n0_transfer_hypothesis.json")
    if not path.exists():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["hypothesis_id"] == "H_BOUNDARY_N0"
    assert payload["source"].startswith("PROGRAMMATIC_RECONSTRUCTION")
    assert payload["total_runs"] == 15 and payload["validated_runs"] == 8
    assert payload["scope"]["task_id"] == "TASK_F01"
