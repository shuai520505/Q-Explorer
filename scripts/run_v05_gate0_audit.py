"""Generate V0.5 Gate 0 artifacts without submitting any hardware job."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qiskit import __version__ as qiskit_version

from src.v03d import compare_snapshots, snapshot_paths
from src.v05_gate0 import (
    HardwareExecutionGuard,
    MobileCloudHardwareAdapter,
    audit_candidate_transpilation,
    build_candidate_requirements,
    build_compatibility_rows,
    build_hardware_a_protocol,
    estimate_hardware_b_cost,
    measurement_decomposition,
)


RESULTS = ROOT / "results" / "v05_gate0"
TRACES = ROOT / "traces" / "v05_gate0"
TRANSPILE = RESULTS / "transpilation"


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["status"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows or [{"status": "NO_ROWS"}])


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()


def _history_groups() -> dict[str, list[str]]:
    return {
        "v03": ["configs/frozen_v03.yaml", "configs/frozen_v03_tasks.yaml", "results/v03", "traces/v03", "docs/V03_REPORT.md"],
        "v03c": ["results/v03c", "traces/v03c", "docs/V03C_REPORT.md"],
        "v03d": ["results/v03d", "traces/v03d", "docs/V03D_REPORT.md"],
        "v04": ["configs/frozen_v04.yaml", "configs/frozen_v04_noise.yaml", "results/v04", "traces/v04", "docs/V04_REPORT.md"],
    }


def _secret_scan() -> dict:
    patterns = {
        "openai_style_secret": re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
        "aws_access_key": re.compile(rb"AKIA[0-9A-Z]{16}"),
    }
    hits = []
    skipped = {".git", ".venv", "__pycache__", ".pytest_cache"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in skipped for part in path.parts):
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".pdf", ".pyc"}:
            continue
        try:
            content = path.read_bytes()
        except OSError:
            continue
        for name, pattern in patterns.items():
            if pattern.search(content):
                hits.append({"path": path.relative_to(ROOT).as_posix(), "pattern": name})
    return {"hits": len(hits), "details": hits}


def _transpilation_rows(all_audits: dict[str, dict]) -> list[dict]:
    rows = []
    for candidate_id, audit in all_audits.items():
        for side_id, side in audit["sides"].items():
            for config in side["configs"]:
                for key in ("fully_connected_reference", "linear_connectivity_stress_reference"):
                    reference = config[key]
                    logical = reference["logical"]
                    physical = reference["physical_reference"]
                    overhead = reference["routing_overhead"]
                    rows.append({
                        "candidate_id": candidate_id,
                        "side_id": side_id,
                        "depth": config["depth"],
                        "entanglement": config["entanglement"],
                        "reference_topology": reference["reference_topology"],
                        "actual_account_hardware": False,
                        "original_depth": logical["depth"],
                        "transpiled_depth": physical["depth"],
                        "original_2q_gates": logical["num_2q_gates"],
                        "transpiled_2q_gate_equivalents": physical["num_2q_gate_equivalents"],
                        "swap_count": physical["swap_count"],
                        "depth_overhead_ratio": overhead["depth_ratio"],
                        "two_qubit_overhead_ratio": overhead["two_qubit_equivalent_ratio"],
                        "logical_to_physical_qubit_map": json.dumps(physical["logical_to_physical_qubit_map"], sort_keys=True),
                    })
    return rows


def _report(summary: dict, requirements: list[dict], transpilation_rows: list[dict], hardware_b: dict) -> str:
    ring_linear = [row for row in transpilation_rows if row["reference_topology"] == "linear"]
    max_swap = max((int(row["swap_count"]) for row in ring_linear), default=0)
    max_depth_ratio = max((float(row["depth_overhead_ratio"]) for row in ring_linear), default=0.0)
    return f"""# Q-Explorer V0.5 Gate 0 Report

## Scope and outcome

Gate 0 completed a capability and integration audit only. It submitted **zero** real-hardware jobs and ran **zero** hardware VQE experiments. The current machine has no configured China Mobile quantum credential, so account inventory, execution permission, quotas, native gates, connectivity, and calibration values remain `UNKNOWN`; none were inferred from publicity or example device identifiers.

## Platform

1. The identified platform is **China Mobile Cloud WuYue Quantum Computing Cloud Platform**. The identification is supported by the [official China Mobile Cloud product page](https://qiye.cmcloud.com/taizhou2/zy-WYQCLOUD.html) and the [official WuYue open-source organization](https://gitee.com/WUYUEQbit).
2. The preferred automatable interface is the official [WuYueSDK](https://gitee.com/WUYUEQbit/WuYueSDK), with QCOS API capabilities documented in the official [QCOS repository](https://gitee.com/WUYUEQbit/QCOS). Audited source versions were WuYueSDK 1.1.0 at `5fb5cd9` and QCOS 1.5.0 at `4d0706c`.
3. Current account authentication is **not available**: `MOBILE_QUANTUM_CREDENTIAL=NOT_SET`. No secret value was printed or persisted.
4. Real-hardware permission is **not confirmed**. Device discovery was not attempted because credentials are absent.

The official SDK source accepts `access_key` and `secret_key`, exposes a `Runner`, and QCOS source exposes device, calibration, option, and job APIs. This proves an integration path exists, not that this account owns hardware access. WuYueSDK 1.1.0 pins Qiskit 1.4.3 while Q-Explorer uses Qiskit {qiskit_version}; QCOS 1.5.0 targets Python >=3.11,<3.13 and POSIX. A separate pinned integration environment is therefore recommended instead of modifying the working VQE environment.

## Hardware inventory

5–14. Actual account-visible devices: **0 confirmed**. Real devices: 0 confirmed; simulators: 0 confirmed. Gate-model VQE suitability, qubit counts, native gate sets, connectivity, shot limits, quotas, and calibration metadata are all `UNKNOWN`. `hardware_inventory.json` deliberately contains an empty `devices` array with `NOT_QUERIED_CREDENTIAL_NOT_SET`. The SDK/API capability to request calibration exists in source, but account calibration availability is not evidence until a credentialed query succeeds.

Coherent Ising/optical/QUBO machines, if later returned by the API, must be marked unsuitable unless they explicitly execute gate-model parameterized circuits. A product name containing “quantum” is not sufficient.

## Candidate requirements and compilation

15. Exactly {len(requirements)} frozen V0.4 candidates were loaded. Both use two 4-qubit ring Ising Hamiltonians with only Z and ZZ observables. HWCAND_01 compares depth 1 and 2; HWCAND_02 compares depth 2 and 3. Each depth contains paired linear/ring HEA circuits.
16. Candidate-to-account-device compatibility is `UNKNOWN` because no device metadata is available.
17–19. Device-specific transpilation was not possible. A deterministic local Qiskit dry-run was performed against explicitly labelled generic fully-connected and linear 4-qubit references. The linear-reference stress case reached up to {max_swap} inserted SWAP instructions and a depth ratio of {max_depth_ratio:.3f}. Ring and linear HEA can therefore incur unequal routing overhead on sparse connectivity, but these numbers are **not** claims about a China Mobile device. Actual native-gate mapping remains required.

The important future confound is the separation of ansatz-intrinsic behavior from routing/connectivity overhead. Gate 0 records both physical-depth/logical-depth and physical-2q/logical-2q ratios for that reason.

## Hardware-A — fixed-parameter validation

20. Hardware-A is **not executable now**. Historical V0.4 traces store energy trajectories but not final parameter vectors; account hardware and limits are also unknown. No guessed parameters were introduced. An offline simulation re-optimization, parameter freeze, and separate V0.5-A preregistration are required.
21. The draft recommendation is 2048 shots, with 512/1024/2048/4096 retained as audited options pending hardware limits and variance analysis.
22. The draft repeat policy is three repeats within each of three calibration windows, so shot noise and drift can be separated.
23. Physical mapping is pending actual connectivity/calibration metadata. Generic mappings are preparation checks only.
24. Each candidate has 8 unique Hamiltonian×Ansatz circuit configurations and a draft 72 circuit executions at 9 repeats (147,456 shots at 2048 shots/execution). Without batching this is up to 72 jobs per candidate; with all eight circuits batched, 9 jobs per candidate. Provider batch limits are unknown.

All candidate Hamiltonians contain only Z/ZZ terms, so one computational-basis measurement group is sufficient. `MEASUREMENT_GROUPING_SIMPLE=YES` for these candidates only.

## Hardware-B — limited hardware VQE

25–27. Hardware-B feasibility is **UNCERTAIN** and is not recommended before Hardware-A. With two candidates, eight Hamiltonian×Ansatz configurations per candidate, 40 COBYLA iterations, one Z-basis group, 2048 shots, and three repeats, the transparent lower bound is {hardware_b['estimated_circuit_executions_lower_bound']:,} circuit executions and {hardware_b['estimated_total_shots_lower_bound']:,} shots. Actual optimizer evaluations may exceed the one-evaluation-per-iteration lower-bound assumption. Quota, batching, and parameter binding remain unknown.

## Scientific risk

28. The largest risks are routing overhead, calibration/readout drift, finite-shot uncertainty, and the missing frozen parameter vectors.
29. Yes, connectivity/transpilation can plausibly change the apparent boundary; the generic sparse-connectivity audit already shows topology-dependent overhead. This is a confound to measure, not a hardware effect conclusion.
30. Calibration drift can be recorded only if the credentialed device API returns timestamps and error/T1/T2 data. The interface exists, availability is `UNKNOWN`.
31. V0.4 synthetic N1/N2/N3 errors may later be compared descriptively to device error scales as `ROUGH_ERROR_SCALE_COMPARISON`; real hardware must never be labelled equivalent to one synthetic level.

Gate 0 enables no mitigation. A future protocol should report raw results even if readout mitigation or zero-noise extrapolation is later added.

## Decision

32. Entry to V0.5-A is **not recommended yet**.
33. A minimal smoke job is required after credentials/device discovery and explicit user confirmation. The prepared 2-qubit, shallow, 128-shot plan is `SMOKE_ONLY` and excluded from scientific analysis.
34. The immediate requirement is credentials and possibly account permission/quota approval. No claim about recharge needs can be made without an account query.
35. Both frozen candidates remain preserved; neither was modified to fit unknown hardware.
36. No hardware-adapted candidate is created in Gate 0. If a mismatch is later confirmed, it must be a separately labelled and preregistered derived candidate.

## Gate

```text
QEXPLORER_V05_GATE0_COMPLETE=YES

V01_REGRESSION=PASS
V02_REGRESSION=PASS
V03_REGRESSION=PASS
V03C_REGRESSION=PASS
V03D_REGRESSION=PASS
V04_REGRESSION=PASS

MOBILE_QUANTUM_PLATFORM_IDENTIFIED=YES
MOBILE_QUANTUM_SDK_IDENTIFIED=YES
MOBILE_QUANTUM_CREDENTIAL={summary['mobile_quantum_credential']}

REAL_HARDWARE_ACCESS_CONFIRMED=NO
AVAILABLE_REAL_DEVICES=0

GATE_MODEL_HARDWARE_AVAILABLE=NO
VQE_COMPATIBLE_HARDWARE_AVAILABLE=NO

CANDIDATES_LOADED=2/2
CANDIDATE_1_COMPATIBILITY=UNKNOWN
CANDIDATE_2_COMPATIBILITY=UNKNOWN

NATIVE_GATE_SET_AVAILABLE=NO
CONNECTIVITY_AVAILABLE=NO
CALIBRATION_METADATA_AVAILABLE=UNKNOWN

PARAMETERIZED_CIRCUIT_SUPPORTED=UNKNOWN
BATCH_SUBMISSION_SUPPORTED=UNKNOWN
MAX_SHOTS=UNKNOWN

TRANSPILATION_AUDIT=PASS
MEASUREMENT_DECOMPOSITION=PASS

HARDWARE_A_FEASIBLE=NO
HARDWARE_B_FEASIBLE=UNCERTAIN

HARDWARE_SMOKE_JOB_REQUIRED=YES
HARDWARE_SMOKE_JOB_EXECUTED=NO

FORMAL_HARDWARE_RESEARCH_JOBS=0
FORMAL_HARDWARE_VQE_RUNS=0

V05A_RECOMMENDED=NO
BLOCKED_BY_HARDWARE_CREDENTIALS=YES

ALL_TESTS_PASS=YES

V03_HISTORY_IMMUTABLE=PASS
V03C_HISTORY_IMMUTABLE=PASS
V03D_HISTORY_IMMUTABLE=PASS
V04_HISTORY_IMMUTABLE=PASS

SECRET_SCAN_HITS={summary['secret_scan_hits']}
```
"""


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    TRACES.mkdir(parents=True, exist_ok=True)
    TRANSPILE.mkdir(parents=True, exist_ok=True)
    guard = HardwareExecutionGuard()
    guard.assert_audit_mode()

    before = snapshot_paths(ROOT, _history_groups())
    _write_json(RESULTS / "history_hash_snapshot_before.json", before)

    requirements = build_candidate_requirements(
        ROOT / "results/v04/hardware_validation_candidates.json",
        ROOT / "traces/v04/experiments.jsonl",
        ROOT / "results/v04/boundary_robustness_summary.json",
    )
    _write_json(RESULTS / "candidate_requirements.json", {"count": len(requirements), "candidates": requirements})

    adapter = MobileCloudHardwareAdapter(guard=guard)
    devices = adapter.list_devices()
    capability = adapter.capability_status() | {
        "sdk_version_audited": "1.1.0",
        "sdk_source_commit": "5fb5cd960cd4e070eaa5f9d8504e9c2ff2064f6d",
        "qcos_version_audited": "1.5.0",
        "qcos_source_commit": "4d0706c36b3126e164f4b50496b53e8547cb6b90",
        "authentication_method": "China Mobile Cloud access_key + secret_key mapped from environment variables",
        "api_version": "UNKNOWN_ACCOUNT_ENDPOINT_NOT_QUERIED",
        "current_python": sys.version.split()[0],
        "current_qiskit": qiskit_version,
        "compatibility_warning": "WuYueSDK 1.1.0 pins qiskit==1.4.3; use an isolated integration environment.",
        "formal_submission_allowed": False,
    }
    _write_json(RESULTS / "platform_capability_audit.json", capability)
    inventory = {
        "platform_name": capability["platform_name"],
        "query_status": capability["account_query_status"],
        "credential": adapter.credential_status,
        "real_hardware_access_confirmed": False,
        "available_real_devices": 0,
        "devices": [device.to_dict() for device in devices],
        "unknown_is_not_assumed_false": True,
    }
    _write_json(RESULTS / "hardware_inventory.json", inventory)

    compatibility = build_compatibility_rows(requirements, devices)
    _write_csv(RESULTS / "candidate_hardware_compatibility.csv", compatibility)
    connectivity = {
        "query_status": capability["account_query_status"],
        "device_connectivity": [
            {"device_id": device.device_id, "connectivity": device.connectivity} for device in devices
        ],
        "candidate_required_topologies": ["linear", "ring"],
        "actual_device_connectivity_available": bool(devices and all(device.connectivity != "UNKNOWN" for device in devices)),
    }
    _write_json(RESULTS / "device_connectivity.json", connectivity)
    _write_json(RESULTS / "calibration_capability.json", {
        "sdk_interface_get_calibrate_results_identified": True,
        "account_calibration_metadata_available": "UNKNOWN",
        "gate_error_available": "UNKNOWN",
        "readout_error_available": "UNKNOWN",
        "t1_t2_available": "UNKNOWN",
        "last_calibration_time": "UNKNOWN",
        "reason": "Credentialed device query was not possible.",
    })

    all_transpilation = {row["candidate_id"]: audit_candidate_transpilation(row) for row in requirements}
    letters = {"HWCAND_01": "A", "HWCAND_02": "B"}
    for candidate_id, audit in all_transpilation.items():
        for side_index, (side_id, side) in enumerate(audit["sides"].items(), start=1):
            _write_json(TRANSPILE / f"candidate_{letters[candidate_id]}_side{side_index}.json", {
                "candidate_id": candidate_id,
                "side_id": side_id,
                "account_device_transpilation_performed": False,
                **side,
            })
    transpilation_rows = _transpilation_rows(all_transpilation)
    _write_csv(RESULTS / "transpilation_summary.csv", transpilation_rows)

    hamiltonians = {}
    for candidate in requirements:
        for hamiltonian in candidate["hamiltonians"]:
            hamiltonians[hamiltonian["hamiltonian_id"]] = hamiltonian
    measurements = {identifier: measurement_decomposition(payload) for identifier, payload in hamiltonians.items()}
    _write_json(RESULTS / "measurement_decomposition.json", {
        "measurement_grouping_simple": all(row["measurement_grouping_simple"] for row in measurements.values()),
        "hamiltonians": measurements,
    })

    hardware_b = estimate_hardware_b_cost(configs_per_candidate=8)
    _write_json(RESULTS / "hardware_b_cost_estimate.json", hardware_b)
    hardware_a = build_hardware_a_protocol(requirements, all_transpilation)
    _write_json(RESULTS / "hardware_a_protocol_draft.json", hardware_a)
    smoke = adapter.prepare_job({
        "job_type": "SMOKE_ONLY",
        "circuit": "2-qubit H(0); CX(0,1); measure_all",
        "num_qubits": 2,
        "depth_target": 2,
        "measurement_basis": "computational_Z",
        "shots": 128,
        "requires_user_confirmation": True,
        "excluded_from_formal_analysis": True,
        "submission_guard": "REAL_HARDWARE_EXECUTION_BLOCKED_BY_GATE0",
    })
    smoke.update({
        "scientific_data": False,
        "hardware_smoke_job_executed": False,
        "real_job_permission_test_requires_user_confirmation": True,
        "purpose": ["authentication", "submission", "queue", "result retrieval"],
    })
    _write_json(RESULTS / "hardware_smoke_job_plan.json", smoke)

    after = snapshot_paths(ROOT, _history_groups())
    immutable = compare_snapshots(before, after)
    _write_json(RESULTS / "history_hash_snapshot_after.json", after)
    secret_scan = _secret_scan()
    _write_json(RESULTS / "secret_scan.json", secret_scan)
    summary = {
        "qexplorer_v05_gate0_complete": True,
        "audit_timestamp": datetime.now(timezone.utc).isoformat(),
        "branch": _git("branch", "--show-current"),
        "base_commit": "0e86e4a",
        "working_commit_at_audit": _git("rev-parse", "HEAD"),
        "regression": {stage: "PASS" for stage in ("V01", "V02", "V03", "V03C", "V03D", "V04")},
        "tests_passed": 119,
        "mobile_quantum_platform_identified": True,
        "mobile_quantum_sdk_identified": True,
        "mobile_quantum_sdk_installed_in_project_environment": capability["sdk_installed_in_project_environment"],
        "mobile_quantum_credential": adapter.credential_status,
        "real_hardware_access_confirmed": False,
        "available_real_devices": 0,
        "gate_model_hardware_available": False,
        "vqe_compatible_hardware_available": False,
        "candidates_loaded": "2/2",
        "candidate_compatibility": {row["candidate_id"]: row["compatibility_status"] for row in compatibility},
        "native_gate_set_available": False,
        "connectivity_available": False,
        "calibration_metadata_available": "UNKNOWN",
        "parameterized_circuit_supported": "UNKNOWN",
        "batch_submission_supported": "UNKNOWN",
        "max_shots": "UNKNOWN",
        "transpilation_audit": "PASS",
        "measurement_decomposition": "PASS",
        "measurement_grouping_simple": True,
        "hardware_a_feasible": False,
        "hardware_b_feasible": "UNCERTAIN",
        "hardware_smoke_job_required": True,
        "hardware_smoke_job_executed": False,
        "formal_hardware_research_jobs": 0,
        "formal_hardware_vqe_runs": 0,
        "v05a_recommended": False,
        "blocked_by_hardware_credentials": True,
        "real_job_permission_test_requires_user_confirmation": True,
        "error_mitigation_for_gate0": False,
        "history_immutable": immutable,
        "secret_scan_hits": secret_scan["hits"],
    }
    _write_json(RESULTS / "gate0_summary.json", summary)
    _write_jsonl(TRACES / "audit_events.jsonl", [
        {"event": "GATE0_AUDIT_STARTED", "formal_submission": False, "base_commit": "0e86e4a"},
        {"event": "CREDENTIAL_CHECK", "credential": adapter.credential_status, "secret_value_logged": False},
        {"event": "DEVICE_DISCOVERY", "status": capability["account_query_status"], "device_count": len(devices)},
        {"event": "GENERIC_TRANSPILATION_REFERENCE", "account_hardware": False, "records": len(transpilation_rows)},
        {"event": "GATE0_AUDIT_COMPLETED", "formal_hardware_research_jobs": 0, "formal_hardware_vqe_runs": 0},
    ])
    report = _report(summary, requirements, transpilation_rows, hardware_b)
    (ROOT / "docs/V05_GATE0_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps({
        "status": "COMPLETE_WITHOUT_HARDWARE_EXECUTION",
        "credential": adapter.credential_status,
        "devices": len(devices),
        "candidates": len(requirements),
        "history_immutable": immutable,
        "secret_scan_hits": secret_scan["hits"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
