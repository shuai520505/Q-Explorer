"""Non-formal one-instance smoke test for the frozen synthetic NoiseModel."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ansatz import build_hea
from src.backend import AerBackend, AerNoiseBackend, NoiseConfig
from src.exact_solver import solve_exact
from src.hamiltonian import generate_ising_hamiltonian
from src.vqe import VQEConfig, VQERunner


def main() -> int:
    payload = yaml.safe_load((ROOT / "configs" / "frozen_v04_noise.yaml").read_text(encoding="utf-8"))
    ham = generate_ising_hamiltonian(4, "chain", 404)
    ansatz = build_hea(4, 1, "linear")
    exact = solve_exact(ham).exact_ground_energy
    vqe = VQEConfig(max_iterations=6, convergence_energy_error=1e-2)
    rows = []
    ideal = VQERunner(AerBackend(), vqe).run("SMOKE_N0", ham, ansatz, 404, exact)
    rows.append({"noise_level_id": "N0", "energy": ideal["final_energy"], "backend": ideal["backend"]})
    for level_id in ("N1", "N2", "N3"):
        config = NoiseConfig(level_id, shots=payload["shots"], **payload["noise_levels"][level_id])
        backend = AerNoiseBackend(config)
        outcome = VQERunner(backend, vqe).run(f"SMOKE_{level_id}", ham, ansatz, 404, exact)
        rows.append({"noise_level_id": level_id, "energy": outcome["final_energy"], "backend": outcome["backend"], "health": backend.health_check(), "noise_config": config.to_dict()})
    differences = [abs(row["energy"] - rows[0]["energy"]) for row in rows[1:]]
    report = {
        "formal_scientific_data": False, "hamiltonian_id": ham.hamiltonian_id,
        "ansatz": {"depth": 1, "entanglement": "linear"}, "max_iterations": 6,
        "rows": rows, "noise_model_works": all(row.get("health", {"success": True})["success"] for row in rows),
        "differs_numerically_from_ideal": all(value > 1e-9 for value in differences),
        "trace_records_noise_config": all("noise_config" in row for row in rows[1:]),
    }
    output = ROOT / "results" / "v04" / "noise_smoke_test.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if all((report["noise_model_works"], report["differs_numerically_from_ideal"], report["trace_records_noise_config"])) else 1


if __name__ == "__main__":
    raise SystemExit(main())
