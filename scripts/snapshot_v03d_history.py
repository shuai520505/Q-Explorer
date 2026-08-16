"""Create or verify immutable history snapshots for V0.3-D."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.v03d import compare_snapshots, snapshot_paths


def _groups(config: dict) -> dict[str, list[str]]:
    return {name: list(section["paths"]) for name, section in config["historical_sources"].items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    args = parser.parse_args()
    config = yaml.safe_load((ROOT / "configs" / "frozen_v03d.yaml").read_text(encoding="utf-8"))
    output = ROOT / config["history_snapshot"][f"{args.phase}_path"]
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot = snapshot_paths(ROOT, _groups(config))
    snapshot["phase"] = args.phase
    snapshot["base_commit"] = config["base_commit"]
    output.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    if args.phase == "after":
        before = json.loads((ROOT / config["history_snapshot"]["before_path"]).read_text(encoding="utf-8"))
        comparison = compare_snapshots(before, snapshot)
        print(json.dumps(comparison, sort_keys=True))
        return 0 if all(comparison.values()) else 1
    print(json.dumps({name: data["aggregate_sha256"] for name, data in snapshot["groups"].items()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
