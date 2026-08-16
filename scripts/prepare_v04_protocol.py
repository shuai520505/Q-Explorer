"""Prepare N0 transfer evidence and immutable history snapshot before noisy runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.v03 import TaskSuite
from src.v03d import EvidenceGraph, snapshot_paths
from src.v04 import BoundaryEstimator, build_n0_transfer_hypothesis


def main() -> int:
    result = ROOT / "results" / "v04"
    result.mkdir(parents=True, exist_ok=True)
    suite = TaskSuite(ROOT / "configs" / "frozen_v03_tasks.yaml")
    task = next(row for row in suite.tasks if row.task_id == "TASK_F01" and row.task_type == "BOUNDARY_TRANSITION")
    graph = EvidenceGraph.from_trace_roots((ROOT / "traces" / "v03", ROOT / "traces" / "v03c"))
    ids = {
        *(f"V03_TASK_F01_llm_{seed}_cc47285bd_geff123b" for seed in (301, 302, 303)),
        *(f"V03_TASK_F01_llm_{seed}_cc47285bd_g3cbbdf8" for seed in range(304, 316)),
    }
    runs = [graph.get_run(run_id) for run_id in sorted(ids)]
    if len(runs) != 15 or any(row.get("status") == "MISSING_LINK" for row in runs):
        raise RuntimeError("Frozen N0 Boundary runs are incomplete")
    estimator = BoundaryEstimator(absolute_effect_deadband=0.05, minimum_boundary_change=0.20)
    transfer = build_n0_transfer_hypothesis(task, runs, graph.records["experiments"], graph.records["evidence"], estimator)
    transfer_path = result / "n0_transfer_hypothesis.json"
    transfer_path.write_text(json.dumps(transfer, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    noise_path = ROOT / "configs" / "frozen_v04_noise.yaml"
    noise = yaml.safe_load(noise_path.read_text(encoding="utf-8"))
    snapshot = {
        "noise_config_sha256": hashlib.sha256(noise_path.read_bytes()).hexdigest(),
        "noise_config": noise,
    }
    (result / "noise_config_snapshot.json").write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    history = snapshot_paths(ROOT, {
        "v03": ["configs/frozen_v03.yaml", "configs/frozen_v03_tasks.yaml", "configs/frozen_v03_live.yaml", "prompts/research_agent_v03_deepseek_v01.txt", "docs/V03_REPORT.md", "results/v03", "traces/v03"],
        "v03c": ["configs/frozen_v03c.yaml", "docs/V03C_REPORT.md", "results/v03c", "traces/v03c"],
        "v03d": ["configs/frozen_v03d.yaml", "docs/V03D_REPORT.md", "results/v03d", "traces/v03d"],
    })
    (result / "history_hash_snapshot_before.json").write_text(json.dumps(history, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"transfer_hypothesis": transfer["hypothesis_id"], "candidate_boundary_region": transfer["boundary_signature"]["candidate_boundary_region"], "history": {key: value["aggregate_sha256"] for key, value in history["groups"].items()}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
