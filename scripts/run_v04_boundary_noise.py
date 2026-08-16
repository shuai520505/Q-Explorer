"""Execute only pre-registered noisy TASK_F01 Boundary runs."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.backend import AerNoiseBackend, NoiseConfig
from src.logging import JsonlTrace
from src.research import ActiveExperimentExecutor, FrozenConfig, LLMResearchAgent, OpenAICompatibleProvider, redact_sensitive_text
from src.v03 import LiveTaskRunner, TaskSuite, V03TaskRunner
from src.v04 import V04Protocol


def _clean_commit() -> str:
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    disallowed: list[str] = []
    for line in status.splitlines():
        # Formal checkpoints are append-only outputs.  Source, prompt, task,
        # judge, and protocol changes remain forbidden throughout execution.
        path = line[3:].replace("\\", "/")
        if not (path.startswith("results/v04/") or path.startswith("traces/v04/")):
            disallowed.append(line)
    if disallowed:
        raise RuntimeError(
            "Formal V0.4 execution requires committed scientific inputs; "
            f"disallowed worktree changes: {disallowed}"
        )
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def _noise_config(protocol: V04Protocol, level: str) -> NoiseConfig:
    payload = yaml.safe_load((ROOT / protocol.data["noise_config_path"]).read_text(encoding="utf-8"))
    return NoiseConfig(level, shots=payload["shots"], **payload["noise_levels"][level])


def _factory(noise_config: NoiseConfig):
    return lambda hamiltonians, vqe_config: ActiveExperimentExecutor(hamiltonians, vqe_config, AerNoiseBackend(noise_config))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=ROOT / "configs" / "frozen_v04.yaml")
    parser.add_argument("--noise-level", choices=("N1", "N2", "N3"), required=True)
    parser.add_argument("--run-seed", type=int, action="append")
    parser.add_argument("--rule-based-control", action="store_true")
    args = parser.parse_args()
    protocol = V04Protocol.load(args.protocol)
    checks = protocol.verify_workspace(ROOT)
    if not all(checks.values()):
        raise RuntimeError(f"Frozen V0.4 workspace mismatch: {[key for key, value in checks.items() if not value]}")
    commit = _clean_commit()
    scientific = FrozenConfig(ROOT / protocol.data["scientific_config_path"])
    suite = TaskSuite(ROOT / protocol.data["task_suite_path"])
    targets = [task for task in suite.tasks if task.task_id == protocol.data["target_task_id"] and task.task_type == protocol.data["target_task_type"]]
    if len(targets) != 1:
        raise RuntimeError("Frozen Boundary task resolution failed")
    task = targets[0]
    noise = _noise_config(protocol, args.noise_level)
    transfer = json.loads((ROOT / protocol.data["transfer_hypothesis_path"]).read_text(encoding="utf-8"))
    public_transfer = {key: transfer[key] for key in protocol.data["agent_visible_transfer_fields"]}
    trace_root = ROOT / protocol.data["traces_root"]
    checkpoint_root = ROOT / protocol.data["results_root"] / "checkpoints"
    metadata = {
        "v04_protocol_hash": protocol.sha256, "source_run": "v04",
        "noise_level_id": args.noise_level, "noise_config": noise.to_dict(),
        "transfer_hypothesis_id": transfer["hypothesis_id"], "synthetic_noise": True,
    }
    executor_factory = _factory(noise)
    if args.rule_based_control:
        if args.noise_level != protocol.data["noise_control"]["noise_level_id"]:
            raise ValueError("Frozen Rule-Based control is permitted only at N2")
        runner = V03TaskRunner(
            scientific.data, scientific.sha256, suite.sha256, trace_root, checkpoint_root,
            executor_factory=executor_factory,
            run_id_factory=lambda task, strategy, suffix, config_hash, git_commit: f"V04_{task.task_id}_{args.noise_level}_{strategy}_{suffix}_c{config_hash[:8]}_g{git_commit[:7]}",
            trace_metadata=metadata, initial_hypothesis=public_transfer,
        )
        summary = runner.run_task(task, "rule_based", None, commit, protocol.data["agent"]["prompt_hash"])
        print(json.dumps({"run_id": summary["run_id"], "budget_spent": summary["budget_spent"], "validated": summary["validated_judgment"]["validated"]}))
        return 0 if summary["failed_vqe_runs"] == 0 else 1

    required = ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")
    present = {name: bool(os.environ.get(name)) for name in required}
    print("LLM_API_KEY=" + ("SET" if present["LLM_API_KEY"] else "NOT_SET"))
    if not all(present.values()):
        return 2
    expected = {"LLM_PROVIDER": protocol.data["agent"]["provider"], "LLM_BASE_URL": protocol.data["agent"]["base_url"], "LLM_MODEL": protocol.data["agent"]["model"]}
    for name, expected_value in expected.items():
        actual = os.environ[name]
        if (actual.rstrip("/") if name == "LLM_BASE_URL" else actual) != (expected_value.rstrip("/") if name == "LLM_BASE_URL" else expected_value):
            raise RuntimeError(f"{name} does not match frozen V0.4 protocol")
    provider = OpenAICompatibleProvider(
        max_tokens=protocol.data["agent"]["max_tokens"], timeout=protocol.data["agent"]["timeout_seconds"],
        retry=protocol.data["agent"]["retry"], thinking_mode=protocol.data["agent"]["thinking_mode"], reasoning_effort=None,
    )
    agent = LLMResearchAgent(
        provider, ROOT / protocol.data["agent"]["prompt_path"], protocol.data["agent"]["prompt_version"],
        temperature=protocol.data["agent"]["temperature"], max_repair_attempts=protocol.data["agent"]["max_repair_attempts"], require_v03_fields=True,
    )
    seeds = args.run_seed or protocol.data["run_seeds"][args.noise_level]
    if not set(seeds) <= set(protocol.data["run_seeds"][args.noise_level]):
        raise ValueError("Run seed is outside the frozen noise-level seed set")
    runner = LiveTaskRunner(
        scientific.data, scientific.sha256, suite.sha256, trace_root, checkpoint_root, agent,
        live_config_hash=protocol.sha256, trace_metadata=metadata, executor_factory=executor_factory,
        run_id_factory=lambda task, seed, config_hash, git_commit: f"V04_{task.task_id}_{args.noise_level}_llm_{seed}_c{config_hash[:8]}_g{git_commit[:7]}",
        initial_hypothesis=public_transfer,
        environment_metadata={"noise_present": True, "noise_level_id": args.noise_level, "synthetic": True},
    )
    errors = JsonlTrace(trace_root / "provider_errors.jsonl")
    for seed in seeds:
        try:
            summary = runner.run_task(task, int(seed), commit, protocol.data["agent"]["prompt_hash"])
        except RuntimeError as exc:
            errors.append({"event": "PROVIDER_TRANSIENT_ERROR", "noise_level_id": args.noise_level, "run_seed": int(seed), "v04_protocol_hash": protocol.sha256, "error": redact_sensitive_text(str(exc), [os.environ.get("LLM_API_KEY", "")])[:1000]})
            print(f"PROVIDER_TRANSIENT_ERROR noise={args.noise_level} seed={seed}")
            return 3
        print(json.dumps({"run_id": summary["run_id"], "noise_level_id": args.noise_level, "run_seed": seed, "budget_spent": summary["budget_spent"], "validated": summary["validated_judgment"]["validated"]}))
        if summary["failed_vqe_runs"]:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
