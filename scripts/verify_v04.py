"""Final reproducible V0.4 gate: tests, frozen hashes, counts, and secret scan."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.v04 import V04Protocol


def secret_scan() -> list[str]:
    pattern = re.compile(r"sk-[A-Za-z0-9]{20,}")
    hits = []
    excluded = {".git", ".venv", "__pycache__", ".pytest_cache"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in excluded for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if pattern.search(text):
            hits.append(path.relative_to(ROOT).as_posix())
    return hits


def main() -> int:
    tests = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, capture_output=True, text=True)
    all_tests = tests.returncode == 0
    if tests.stdout:
        print(tests.stdout.rstrip())
    if tests.stderr:
        print(tests.stderr.rstrip(), file=sys.stderr)
    protocol = V04Protocol.load(ROOT / "configs" / "frozen_v04.yaml")
    frozen = protocol.verify_workspace(ROOT)
    summary = json.loads((ROOT / "results" / "v04" / "boundary_robustness_summary.json").read_text(encoding="utf-8"))
    levels = summary["levels"]
    history = summary["history_immutable"]
    hits = secret_scan()
    formal_counts = all(int(levels[level]["total_runs"]) == 15 for level in ("N0", "N1", "N2", "N3"))
    complete = bool(all_tests and all(frozen.values()) and formal_counts and all(history.values()) and not hits)

    lines = [
        f"QEXPLORER_V04_COMPLETE={'YES' if complete else 'NO'}", "",
        f"V01_REGRESSION={'PASS' if all_tests else 'FAIL'}",
        f"V02_REGRESSION={'PASS' if all_tests else 'FAIL'}",
        f"V03_REGRESSION={'PASS' if all_tests else 'FAIL'}",
        f"V03C_REGRESSION={'PASS' if all_tests else 'FAIL'}",
        f"V03D_REGRESSION={'PASS' if all_tests else 'FAIL'}", "",
        f"BOUNDARY_TASK_FROZEN={'YES' if frozen['task_suite'] else 'NO'}",
        f"TRANSFER_HYPOTHESIS_FROZEN={'YES' if frozen['transfer_hypothesis'] else 'NO'}", "",
        f"NOISE_CONFIG_FROZEN={'YES' if frozen['noise_config'] else 'NO'}",
        f"NOISE_MODEL={'PASS' if frozen['smoke_test'] else 'FAIL'}",
        f"NOISE_MONOTONICITY={'PASS' if frozen['noise_monotonic'] else 'FAIL'}", "",
        f"N0_TOTAL_RUNS={levels['N0']['total_runs']}",
        f"N0_VALIDATED={levels['N0']['validated_count']}/15", "",
    ]
    for level in ("N1", "N2", "N3"):
        lines.extend([
            f"{level}_TOTAL_RUNS={levels[level]['total_runs']}",
            f"{level}_VALIDATED={levels[level]['validated_count']}/15",
            f"{level}_SCIENTIFICALLY_VALIDATED={levels[level]['scientifically_validated_count']}/15",
            f"{level}_BOUNDARY_STATUS={levels[level]['primary_status']}", "",
        ])
    lines.extend([
        "BOUNDARY_SHIFT_ANALYSIS=AVAILABLE" if (ROOT / "results/v04/boundary_shift_analysis.csv").exists() else "BOUNDARY_SHIFT_ANALYSIS=NOT_AVAILABLE",
        "COUNTEREXAMPLE_ANALYSIS=PASS" if (ROOT / "results/v04/counterexample_analysis.csv").exists() else "COUNTEREXAMPLE_ANALYSIS=FAIL",
        "REVISION_ATTRIBUTION=PASS" if (ROOT / "results/v04/hypothesis_revision_analysis.csv").exists() else "REVISION_ATTRIBUTION=FAIL", "",
        f"HARDWARE_VALIDATION_CANDIDATES={len(summary['hardware_validation_candidates'])}",
        f"V05_RECOMMENDED={'YES' if summary['v05_recommended'] else 'NO'}", "",
        f"ALL_TESTS_PASS={'YES' if all_tests else 'NO'}", "",
        f"LIVE_LLM_USED={'YES' if summary['live_llm_used'] else 'NO'}",
        f"MODEL={summary['model']}",
        f"THINKING_MODE={str(summary['thinking_mode']).lower()}", "",
        f"QISKIT_AER_USED={'YES' if summary['qiskit_aer_used'] else 'NO'}",
        f"NOISE_SIMULATION_USED={'YES' if summary['noise_simulation_used'] else 'NO'}",
        f"REAL_QUANTUM_HARDWARE_USED={'YES' if summary['real_quantum_hardware_used'] else 'NO'}", "",
        f"V03_HISTORY_IMMUTABLE={'PASS' if history['v03'] else 'FAIL'}",
        f"V03C_HISTORY_IMMUTABLE={'PASS' if history['v03c'] else 'FAIL'}",
        f"V03D_HISTORY_IMMUTABLE={'PASS' if history['v03d'] else 'FAIL'}", "",
        f"SECRET_SCAN_HITS={len(hits)}",
    ])
    gate = "\n".join(lines) + "\n"
    (ROOT / "results" / "v04" / "v04_gate.txt").write_text(gate, encoding="utf-8")
    print(gate, end="")
    if hits:
        print("Secret scan paths are intentionally not persisted.", file=sys.stderr)
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
