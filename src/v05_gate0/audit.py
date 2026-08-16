"""Deterministic candidate, compatibility, measurement, and cost audits."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from src.ansatz import build_hea

from .models import HardwareDevice, UNKNOWN


def _read_jsonl(path: str | Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def measurement_decomposition(hamiltonian: dict) -> dict:
    num_qubits = int(hamiltonian["num_qubits"])
    observables = [f"Z_{index}" for index, coefficient in enumerate(hamiltonian.get("h", [])) if float(coefficient) != 0.0]
    observables.extend(
        f"Z_{int(edge['i'])} Z_{int(edge['j'])}"
        for edge in hamiltonian.get("J", [])
        if float(edge["value"]) != 0.0
    )
    only_z_diagonal = all(part.startswith("Z_") for observable in observables for part in observable.split(" "))
    return {
        "num_qubits": num_qubits,
        "required_observables": observables,
        "required_measurement_bases": ["computational_Z"] if only_z_diagonal else UNKNOWN,
        "measurement_group_count": 1 if only_z_diagonal else UNKNOWN,
        "measurement_grouping_simple": bool(only_z_diagonal),
    }


def build_candidate_requirements(
    candidate_path: str | Path,
    experiments_path: str | Path,
    v04_summary_path: str | Path,
) -> list[dict]:
    candidates = json.loads(Path(candidate_path).read_text(encoding="utf-8"))["candidates"]
    experiments = _read_jsonl(experiments_path)
    summary = json.loads(Path(v04_summary_path).read_text(encoding="utf-8"))
    output = []
    for index, candidate in enumerate(candidates, start=1):
        selected = [row for row in experiments if row.get("run_id") == candidate["run_id"]]
        hamiltonians = {}
        for row in selected:
            payload = row.get("configuration", {}).get("hamiltonian")
            if payload:
                hamiltonians[payload["hamiltonian_id"]] = payload
        configs = [{"depth": int(depth), "entanglement": entanglement} for depth, entanglement in candidate["ansatz_configs"]]
        config_stats = []
        for config in configs:
            ansatz = build_hea(4, config["depth"], config["entanglement"], allowed_depths=frozenset({1, 2, 3}))
            one_qubit = int(ansatz.circuit.count_ops().get("ry", 0))
            config_stats.append(config | {
                "num_parameters": ansatz.num_parameters,
                "circuit_depth": ansatz.circuit_depth,
                "num_1q_gates": one_qubit,
                "num_2q_gates": ansatz.num_2q_gates,
            })
        parameter_fields = {"final_parameters", "optimized_parameters", "parameters"}
        has_parameters = any(parameter_fields & set(row) for row in selected)
        depths = sorted({item["depth"] for item in configs})
        output.append({
            "candidate_id": f"HWCAND_{index:02d}",
            "source_run_id": candidate["run_id"],
            "source_path": str(candidate_path).replace("\\", "/"),
            "selection_rule": candidate["selection_rule"],
            "hamiltonian_id": list(candidate["hamiltonian_id"]),
            "hamiltonians": [hamiltonians[key] for key in candidate["hamiltonian_id"] if key in hamiltonians],
            "num_qubits": max((int(item["num_qubits"]) for item in hamiltonians.values()), default=4),
            "ansatz": "Hardware-Efficient Ansatz (RY + CX)",
            "depth": depths,
            "entanglement": sorted({item["entanglement"] for item in configs}),
            "ansatz_config_stats": config_stats,
            "num_parameters": sorted({item["num_parameters"] for item in config_stats}),
            "circuit_depth": sorted({item["circuit_depth"] for item in config_stats}),
            "num_1q_gates": sorted({item["num_1q_gates"] for item in config_stats}),
            "num_2q_gates": sorted({item["num_2q_gates"] for item in config_stats}),
            "required_observables": sorted({obs for ham in hamiltonians.values() for obs in measurement_decomposition(ham)["required_observables"]}),
            "required_measurement_bases": ["computational_Z"],
            "whether_optimized_parameters_already_exist": has_parameters,
            "whether_hardware_side_optimization_is_required": False,
            "fixed_parameter_preparation_gap": None if has_parameters else "Historical V0.4 traces do not contain parameter vectors; offline simulation re-optimization and a separate freeze are required before Hardware-A.",
            "boundary_sides": [
                {"side_id": "side_A", "depth": depths[0], "configs": [item for item in configs if item["depth"] == depths[0]]},
                {"side_id": "side_B", "depth": depths[-1], "configs": [item for item in configs if item["depth"] == depths[-1]]},
            ],
            "N0_behavior": candidate["n0_behavior"],
            "N1_behavior": summary["levels"]["N1"],
            "N2_behavior": summary["levels"]["N2"],
            "N3_behavior": summary["levels"]["N3"],
            "selected_noisy_behavior": {"noise_level": candidate["noise_level"], **candidate["noisy_behavior"]},
            "expected_hardware_question": candidate["why_scientifically_informative"],
            "expected_hardware_observation": candidate["expected_hardware_observation"],
            "falsification_condition": candidate["falsification_condition"],
        })
    if len(output) != 2:
        raise ValueError(f"Expected exactly 2 frozen hardware candidates, found {len(output)}")
    return output


def _gate_set_compatible(device: HardwareDevice) -> bool | str:
    if device.native_gate_set == UNKNOWN:
        return UNKNOWN
    gates = {str(gate).lower() for gate in device.native_gate_set}
    return bool(gates & {"cx", "cz", "ecr", "cnot"}) and bool(gates & {"ry", "u", "u3", "rz", "rx", "sx"})


def build_compatibility_rows(candidates: Iterable[dict], devices: Iterable[HardwareDevice]) -> list[dict]:
    device_list = list(devices)
    if not device_list:
        return [
            {
                "candidate_id": candidate["candidate_id"],
                "device_id": "UNRESOLVED_ACCOUNT_DEVICE",
                "qubit_count_fit": UNKNOWN,
                "gate_set_compatible": UNKNOWN,
                "connectivity_compatible": UNKNOWN,
                "requires_transpilation": UNKNOWN,
                "estimated_transpiled_depth": UNKNOWN,
                "estimated_2q_gate_count": UNKNOWN,
                "observable_supported": UNKNOWN,
                "shot_requirement_supported": UNKNOWN,
                "parameterized_execution_supported": UNKNOWN,
                "batch_execution_supported": UNKNOWN,
                "hardware_vqe_possible": UNKNOWN,
                "fixed_parameter_validation_possible": False,
                "estimated_risk": "HIGH_ACCOUNT_CAPABILITY_UNKNOWN",
                "compatibility_status": "UNKNOWN",
            }
            for candidate in candidates
        ]
    rows = []
    for candidate in candidates:
        for device in device_list:
            qubit_fit = device.num_qubits != UNKNOWN and int(device.num_qubits) >= int(candidate["num_qubits"])
            gate_fit = _gate_set_compatible(device)
            suitable = str(device.suitability).startswith("SUITABLE") or device.suitability == UNKNOWN
            status = "NOT_COMPATIBLE" if qubit_fit is False or suitable is False else "COMPATIBLE_WITH_TRANSPILATION" if qubit_fit and gate_fit is True else "UNKNOWN"
            rows.append({
                "candidate_id": candidate["candidate_id"],
                "device_id": device.device_id,
                "qubit_count_fit": qubit_fit,
                "gate_set_compatible": gate_fit,
                "connectivity_compatible": UNKNOWN if device.connectivity == UNKNOWN else True,
                "requires_transpilation": True,
                "estimated_transpiled_depth": UNKNOWN,
                "estimated_2q_gate_count": UNKNOWN,
                "observable_supported": device.supports_raw_counts if candidate["required_measurement_bases"] == ["computational_Z"] else UNKNOWN,
                "shot_requirement_supported": device.supports_shots,
                "parameterized_execution_supported": device.supports_parameterized_circuit,
                "batch_execution_supported": device.supports_batch_submission,
                "hardware_vqe_possible": bool(qubit_fit and gate_fit is True and suitable),
                "fixed_parameter_validation_possible": bool(qubit_fit and gate_fit is True and suitable and device.supports_raw_counts is True),
                "estimated_risk": "MEDIUM_METADATA_INCOMPLETE" if status != "NOT_COMPATIBLE" else "HIGH",
                "compatibility_status": status,
            })
    return rows


def estimate_hardware_b_cost(
    *, candidates: int = 2, configs_per_candidate: int = 4, max_iterations: int = 40,
    observable_groups: int = 1, shots: int = 2048, repeats: int = 3,
) -> dict:
    circuit_executions = candidates * configs_per_candidate * max_iterations * observable_groups * repeats
    return {
        "status": "AUDIT_ESTIMATE_NOT_EXECUTED",
        "assumptions": {
            "candidates": candidates,
            "configs_per_candidate": configs_per_candidate,
            "optimizer_max_iterations": max_iterations,
            "observable_groups": observable_groups,
            "shots": shots,
            "repeats": repeats,
            "objective_evaluations_assumed_per_iteration": 1,
        },
        "estimated_circuit_executions_lower_bound": circuit_executions,
        "estimated_total_shots_lower_bound": circuit_executions * shots,
        "estimated_job_count_without_batching": circuit_executions,
        "estimated_job_count_with_four_circuit_batches": (circuit_executions + 3) // 4,
        "hardware_b_feasibility": "UNCERTAIN",
        "reason": "Account quota, batching, parameter binding, and optimizer-evaluation behavior are unconfirmed.",
    }


def build_hardware_a_protocol(candidates: Iterable[dict], transpilation: dict) -> dict:
    drafts = []
    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
        circuit_configurations = len(candidate["ansatz_config_stats"]) * len(candidate["hamiltonian_id"])
        repeat_count = 3 * 3
        circuit_executions = circuit_configurations * repeat_count
        drafts.append({
            "candidate_id": candidate_id,
            "status": "DRAFT_BLOCKED_PENDING_CREDENTIALS_AND_FROZEN_PARAMETERS",
            "side_A": candidate["boundary_sides"][0],
            "side_B": candidate["boundary_sides"][1],
            "frozen_parameters": "NOT_AVAILABLE_IN_V04_TRACES",
            "measurement_observable": candidate["required_observables"],
            "measurement_basis": "computational_Z",
            "recommended_shots": 2048,
            "shot_options_audited": [512, 1024, 2048, 4096],
            "repeat_recommendation": {"within_calibration_window": 3, "across_calibration_windows": 3},
            "cost_draft": {
                "unique_circuit_configurations": circuit_configurations,
                "total_repeats_per_configuration": repeat_count,
                "estimated_circuit_executions": circuit_executions,
                "estimated_total_shots": circuit_executions * 2048,
                "estimated_jobs_without_batching": circuit_executions,
                "estimated_jobs_if_all_candidate_circuits_batch_together": repeat_count,
            },
            "physical_qubit_mapping": "UNAVAILABLE_UNTIL_DEVICE_METADATA_QUERY",
            "generic_transpilation_reference": transpilation.get(candidate_id, {}),
            "predictions": {
                "N0": candidate["N0_behavior"],
                "N1": {"primary_status": candidate["N1_behavior"]["primary_status"]},
                "N2": {"primary_status": candidate["N2_behavior"]["primary_status"]},
                "N3": {"primary_status": candidate["N3_behavior"]["primary_status"]},
            },
            "hardware_falsification_condition": candidate["falsification_condition"],
            "scientific_data": False,
        })
    return {
        "protocol_status": "DRAFT_NOT_PREREGISTERED",
        "hardware_a_feasible_now": False,
        "blocking_conditions": ["MOBILE_QUANTUM_CREDENTIAL_NOT_SET", "ACCOUNT_DEVICE_METADATA_UNKNOWN", "FROZEN_PARAMETER_VECTORS_ABSENT"],
        "candidates": drafts,
    }
