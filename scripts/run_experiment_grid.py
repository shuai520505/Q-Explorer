"""Run the frozen 2x2x2x2 Q-Explorer V0.1 smoke grid and close H001."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ansatz import build_hea
from src.backend import AerBackend
from src.evidence import EvidenceJudge, aggregate_experiments
from src.exact_solver import solve_exact
from src.hamiltonian import generate_ising_hamiltonian
from src.hypothesis import Hypothesis, update_hypothesis
from src.logging import ExperimentLogger, JsonlTrace
from src.logging.jsonl_logger import utc_now
from src.vqe import VQEConfig, VQERunner


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if config["project"]["version"] != "0.1":
        raise ValueError("This runner only accepts the V0.1 configuration")
    return config


def resolve_output(config: dict, key: str) -> Path:
    return ROOT / config["outputs"][key]


def stable_fingerprint(records: list[dict]) -> str:
    fields = [
        "hamiltonian_id",
        "depth",
        "entanglement",
        "initialization_seed",
        "exact_energy",
        "initial_energy",
        "final_energy",
        "energy_error",
        "relative_energy_error",
        "converged",
        "status",
        "optimization_trajectory",
    ]
    canonical = [{field: record.get(field) for field in fields} for record in records]
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def next_trace_id(trace: JsonlTrace, prefix: str) -> str:
    maximum = 0
    for record in trace.read_all():
        value = str(record.get("evidence_id", ""))
        if value.startswith(prefix):
            try:
                maximum = max(maximum, int(value.removeprefix(prefix)))
            except ValueError:
                continue
    return f"{prefix}{maximum + 1:06d}"


def _configuration_snapshot(config: dict, hamiltonian: dict, depth: int, entanglement: str, seed: int) -> dict:
    return {
        "project_version": config["project"]["version"],
        "hamiltonian": hamiltonian,
        "ansatz": {"rotation": config["ansatz"]["rotation"], "depth": depth, "entanglement": entanglement},
        "vqe": {
            "backend": config["vqe"]["backend"],
            "noiseless": config["vqe"]["noiseless"],
            "optimizer": config["vqe"]["optimizer"],
            "max_iterations": config["vqe"]["max_iterations"],
            "optimizer_tolerance": config["vqe"]["optimizer_tolerance"],
            "convergence_energy_error": config["vqe"]["convergence_energy_error"],
            "initialization_seed": seed,
        },
    }


def run_grid(config_path: Path) -> dict:
    config = load_config(config_path)
    hcfg = config["hamiltonians"]
    hamiltonians = [
        generate_ising_hamiltonian(
            num_qubits=hcfg["num_qubits"],
            topology=instance["topology"],
            seed=instance["seed"],
            coefficient_low=hcfg["coefficient_low"],
            coefficient_high=hcfg["coefficient_high"],
            random_edge_probability=hcfg["random_edge_probability"],
        )
        for instance in hcfg["instances"]
    ]
    exact_solutions = {ham.hamiltonian_id: solve_exact(ham) for ham in hamiltonians}
    hamiltonian_path = resolve_output(config, "hamiltonians_data")
    hamiltonian_path.parent.mkdir(parents=True, exist_ok=True)
    hamiltonian_path.write_text(
        json.dumps(
            [ham.to_dict() | {"exact_ground_energy": exact_solutions[ham.hamiltonian_id].exact_ground_energy} for ham in hamiltonians],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    experiment_logger = ExperimentLogger(resolve_output(config, "experiments_trace"))
    hypothesis_trace = JsonlTrace(resolve_output(config, "hypotheses_trace"))
    evidence_trace = JsonlTrace(resolve_output(config, "evidence_trace"))
    hypothesis = Hypothesis(config["hypothesis"]["hypothesis_id"], config["hypothesis"]["claim"])
    loop_run_id = f"LOOP_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
    hypothesis_trace.append({"event": "CREATED", "loop_run_id": loop_run_id, "recorded_at": utc_now(), **hypothesis.to_dict()})

    vcfg = config["vqe"]
    runner = VQERunner(
        AerBackend(),
        VQEConfig(
            optimizer=vcfg["optimizer"],
            max_iterations=vcfg["max_iterations"],
            optimizer_tolerance=vcfg["optimizer_tolerance"],
            convergence_energy_error=vcfg["convergence_energy_error"],
        ),
    )
    records: list[dict] = []
    for hamiltonian in hamiltonians:
        exact_energy = exact_solutions[hamiltonian.hamiltonian_id].exact_ground_energy
        for depth in config["ansatz"]["depths"]:
            for entanglement in config["ansatz"]["entanglements"]:
                ansatz = build_hea(hamiltonian.num_qubits, depth, entanglement)
                for seed in vcfg["initialization_seeds"]:
                    experiment_id = experiment_logger.next_experiment_id()
                    configuration = _configuration_snapshot(config, hamiltonian.to_dict(), depth, entanglement, seed)
                    started = perf_counter()
                    try:
                        outcome = runner.run(experiment_id, hamiltonian, ansatz, seed, exact_energy)
                        record = outcome | {"configuration": configuration, "loop_run_id": loop_run_id}
                    except Exception as exc:
                        record = {
                            "experiment_id": experiment_id,
                            "hamiltonian_id": hamiltonian.hamiltonian_id,
                            "depth": depth,
                            "entanglement": entanglement,
                            "initialization_seed": seed,
                            "exact_energy": exact_energy,
                            "initial_energy": None,
                            "final_energy": None,
                            "energy_error": None,
                            "relative_energy_error": None,
                            "optimization_steps": 0,
                            "runtime": float(perf_counter() - started),
                            "converged": False,
                            "optimization_trajectory": [],
                            "num_parameters": ansatz.num_parameters,
                            "circuit_depth": ansatz.circuit_depth,
                            "num_2q_gates": ansatz.num_2q_gates,
                            "backend": runner.backend.name,
                            "status": "FAILED",
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                            "configuration": configuration,
                            "loop_run_id": loop_run_id,
                        }
                    experiment_logger.append_experiment(record)
                    records.append(record)

    aggregates = aggregate_experiments(records)
    target_hamiltonian = hamiltonians[int(config["hypothesis"]["evaluation_hamiltonian_index"])]
    target_depth = int(config["hypothesis"]["evaluation_depth"])
    matching = {
        item["entanglement"]: item
        for item in aggregates
        if item["hamiltonian_id"] == target_hamiltonian.hamiltonian_id and item["depth"] == target_depth
    }
    if set(matching) != {"linear", "ring"} or any(item["mean_energy_error"] is None for item in matching.values()):
        judgment = {
            "decision": "INCONCLUSIVE",
            "rule": "missing_successful_comparison_group",
            "candidate": matching.get("ring"),
            "control": matching.get("linear"),
            "diagnostics": None,
            "thresholds": dict(config["evidence_judge"]),
        }
    else:
        judgment = EvidenceJudge(config["evidence_judge"]).judge(matching["ring"], matching["linear"])
    evidence_id = next_trace_id(evidence_trace, "EVID_")
    compared_ids = [
        record["experiment_id"]
        for record in records
        if record["hamiltonian_id"] == target_hamiltonian.hamiltonian_id and record["depth"] == target_depth
    ]
    evidence_record = {
        "evidence_id": evidence_id,
        "hypothesis_id": hypothesis.hypothesis_id,
        "loop_run_id": loop_run_id,
        "recorded_at": utc_now(),
        "comparison": {"candidate": "ring", "control": "linear", "hamiltonian_id": target_hamiltonian.hamiltonian_id, "depth": target_depth},
        "experiment_ids": compared_ids,
        **judgment,
    }
    evidence_trace.append(evidence_record)
    update_hypothesis(hypothesis, evidence_record, compared_ids)
    hypothesis_trace.append({"event": "UPDATED", "loop_run_id": loop_run_id, "recorded_at": utc_now(), **hypothesis.to_dict()})

    csv_path = resolve_output(config, "results_csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_records = []
    for record in records:
        row = dict(record)
        row["optimization_trajectory"] = json.dumps(row["optimization_trajectory"], separators=(",", ":"), allow_nan=False)
        row["configuration"] = json.dumps(row["configuration"], sort_keys=True, separators=(",", ":"), allow_nan=False)
        csv_records.append(row)
    pd.DataFrame(csv_records).to_csv(csv_path, index=False)

    summary = {
        "project_version": "0.1",
        "loop_run_id": loop_run_id,
        "config_path": str(config_path.relative_to(ROOT)),
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "run_count": len(records),
        "successful_runs": sum(record["status"] == "SUCCESS" for record in records),
        "failed_runs": sum(record["status"] == "FAILED" for record in records),
        "aggregates": aggregates,
        "reproducibility_fingerprint": stable_fingerprint(records),
        "evidence": evidence_record,
        "hypothesis": hypothesis.to_dict(),
        "real_quantum_hardware_used": False,
        "llm_agent_used": False,
    }
    summary_path = resolve_output(config, "summary_json")
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "frozen_v01.yaml")
    args = parser.parse_args()
    summary = run_grid(args.config.resolve())
    print(json.dumps({"run_count": summary["run_count"], "failed_runs": summary["failed_runs"], "decision": summary["evidence"]["decision"], "hypothesis_status": summary["hypothesis"]["status"], "fingerprint": summary["reproducibility_fingerprint"]}, indent=2))
    return 0 if summary["failed_runs"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

