import json

from src.v05_gate0 import build_candidate_requirements


def test_v05_candidate_loader_requires_two_frozen_candidates(tmp_path):
    candidate = {
        "ansatz_configs": [[1, "linear"], [1, "ring"], [2, "linear"], [2, "ring"]],
        "expected_hardware_observation": "paired contrast",
        "falsification_condition": "ordering changes",
        "hamiltonian_id": ["H1", "H2"],
        "n0_behavior": {"region": [2, 3]},
        "noise_level": "N1",
        "noisy_behavior": {"region": [1, 2]},
        "run_id": "R1",
        "selection_rule": "frozen",
        "why_scientifically_informative": "transfer",
    }
    candidate_path = tmp_path / "candidates.json"
    candidate_path.write_text(json.dumps({"candidates": [candidate, candidate | {"run_id": "R2"}]}), encoding="utf-8")
    experiment_path = tmp_path / "experiments.jsonl"
    hamiltonian = {"hamiltonian_id": "H1", "num_qubits": 4, "h": [1, 1, 1, 1], "J": []}
    rows = [{"run_id": run, "configuration": {"hamiltonian": hamiltonian}} for run in ("R1", "R2")]
    experiment_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(json.dumps({"levels": {level: {"primary_status": "SHIFTED"} for level in ("N1", "N2", "N3")}}), encoding="utf-8")
    loaded = build_candidate_requirements(candidate_path, experiment_path, summary_path)
    assert [row["candidate_id"] for row in loaded] == ["HWCAND_01", "HWCAND_02"]
    assert loaded[0]["whether_optimized_parameters_already_exist"] is False
