"""Run only the pre-frozen V0.3-C targeted DeepSeek replications."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.logging import JsonlTrace
from src.research import FrozenConfig, LLMResearchAgent, OpenAICompatibleProvider, redact_sensitive_text
from src.v03 import LiveTaskRunner, TaskSuite
from src.v03c import V03CProtocol


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=ROOT / "configs" / "frozen_v03c.yaml")
    parser.add_argument("--task-id", action="append")
    parser.add_argument("--run-seed", type=int, action="append")
    args = parser.parse_args()

    protocol = V03CProtocol.load(args.protocol)
    checks = protocol.verify_workspace(ROOT)
    if not all(checks.values()):
        raise RuntimeError(f"Frozen V0.3-C workspace check failed: {[key for key, value in checks.items() if not value]}")
    required = ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")
    present = {name: bool(os.environ.get(name)) for name in required}
    print("LLM_API_KEY=" + ("SET" if present["LLM_API_KEY"] else "NOT_SET"))
    if not all(present.values()):
        return 2
    expected = {
        "LLM_PROVIDER": protocol.data["provider"], "LLM_BASE_URL": protocol.data["base_url"],
        "LLM_MODEL": protocol.data["model"],
    }
    for name, value in expected.items():
        actual = os.environ[name].rstrip("/") if name == "LLM_BASE_URL" else os.environ[name]
        expected_value = value.rstrip("/") if name == "LLM_BASE_URL" else value
        if actual != expected_value:
            raise RuntimeError(f"{name} does not match frozen_v03c.yaml")

    scientific = FrozenConfig(ROOT / protocol.data["scientific_config_path"])
    live = FrozenConfig(ROOT / protocol.data["live_config_path"])
    suite = TaskSuite(ROOT / protocol.data["task_suite_path"])
    targets = [task for task in suite.tasks if task.task_id in protocol.data["target_task_ids"]]
    if args.task_id:
        requested = set(args.task_id)
        if not requested <= set(protocol.data["target_task_ids"]):
            raise ValueError("Requested task is outside the frozen V0.3-C target set")
        targets = [task for task in targets if task.task_id in requested]
    seeds = args.run_seed or protocol.data["additional_run_seeds"]
    if not set(seeds) <= set(protocol.data["additional_run_seeds"]):
        raise ValueError("Run seed is outside the frozen V0.3-C replication seeds")

    provider = OpenAICompatibleProvider(
        max_tokens=protocol.data["max_tokens"], timeout=protocol.data["timeout_seconds"],
        retry=protocol.data["retry"], thinking_mode=protocol.data["thinking_mode"], reasoning_effort=None,
    )
    prompt = ROOT / protocol.data["prompt_path"]
    agent = LLMResearchAgent(
        provider, prompt, live.data["prompt_version"], temperature=protocol.data["temperature"],
        max_repair_attempts=scientific.data["llm"]["max_repair_attempts"], require_v03_fields=True,
    )
    git_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    trace_root = ROOT / protocol.data["traces_root"]
    result_root = ROOT / protocol.data["results_root"]
    trace_root.mkdir(parents=True, exist_ok=True)
    result_root.mkdir(parents=True, exist_ok=True)
    runner = LiveTaskRunner(
        scientific.data, scientific.sha256, suite.sha256, trace_root, result_root / "checkpoints", agent,
        live.sha256, {"v03c_protocol_hash": protocol.sha256, "source_run": "v03c"},
    )
    summaries = []
    errors = JsonlTrace(trace_root / "provider_errors.jsonl")
    for task in targets:
        for seed in seeds:
            try:
                summary = runner.run_task(task, int(seed), git_commit, protocol.data["prompt_hash"])
            except RuntimeError as exc:
                errors.append({
                    "event": "PROVIDER_TRANSIENT_ERROR", "task_id": task.task_id, "run_seed": int(seed),
                    "v03c_protocol_hash": protocol.sha256,
                    "error": redact_sensitive_text(str(exc), [os.environ.get("LLM_API_KEY", "")])[:1000],
                })
                print(f"PROVIDER_TRANSIENT_ERROR task={task.task_id} seed={seed}")
                return 3
            summaries.append(summary)
            print(json.dumps({
                "run_id": summary["run_id"], "task_id": task.task_id, "run_seed": seed,
                "budget_spent": summary["budget_spent"], "validated": summary["validated_judgment"]["validated"],
            }))
    return 0 if all(item["failed_vqe_runs"] == 0 for item in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
