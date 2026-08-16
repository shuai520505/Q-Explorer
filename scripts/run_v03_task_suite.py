"""Execute or resume the frozen V0.3 suite for one selection strategy."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.logging import JsonlTrace
from src.research import FrozenConfig, LLMResearchAgent, OpenAICompatibleProvider
from src.v03 import LiveTaskRunner, TaskSuite, V03TaskRunner


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", required=True, choices=("llm", "rule_based", "random", "no_intervention", "fixed"))
    parser.add_argument("--task-suite", type=Path, default=ROOT / "configs" / "frozen_v03_tasks.yaml")
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "frozen_v03.yaml")
    parser.add_argument("--task-id", action="append")
    parser.add_argument("--policy-seed", type=int)
    parser.add_argument("--run-seed", type=int)
    parser.add_argument("--max-rounds", type=int)
    parser.add_argument("--prompt", type=Path)
    parser.add_argument("--prompt-version")
    parser.add_argument("--disable-thinking", action="store_true")
    args = parser.parse_args()
    frozen = FrozenConfig(args.config)
    suite = TaskSuite(args.task_suite)
    result_root = ROOT / "results" / "v03"
    trace_root = ROOT / "traces" / "v03"
    result_root.mkdir(parents=True, exist_ok=True)
    trace_root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(suite.quality_audit()).to_csv(result_root / "task_quality_audit.csv", index=False)
    suite.verify_unchanged()

    if args.strategy == "llm":
        available = all(os.environ.get(name) for name in ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"))
        if not available:
            status = {"live_llm_used": False, "live_llm_blocked_by_credentials": True, "required_environment_variables_present": False}
            (result_root / "live_llm_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
            JsonlTrace(trace_root / "runs.jsonl").append({"event": "LIVE_LLM_BLOCKED", **status})
            JsonlTrace(trace_root / "llm_responses.jsonl").append({"event": "NO_REQUEST_SENT", "reason": "CREDENTIALS_UNAVAILABLE", "raw_response": None, "structured_action": None, "validation_result": "NOT_ATTEMPTED", "repair_attempted": False, "repair_success": False})
            print("LIVE_LLM_USED=NO\nLIVE_LLM_BLOCKED_BY_CREDENTIALS=YES")
            return 2
        live_path = ROOT / "configs" / "frozen_v03_live.yaml"
        live_frozen = FrozenConfig(live_path) if live_path.exists() else None
        live_config = live_frozen.data if live_frozen else {
            "provider": os.environ.get("LLM_PROVIDER"), "model": os.environ.get("LLM_MODEL"),
            "thinking_mode": True, "reasoning_effort": "high",
            "temperature": frozen.data["llm"]["temperature"], "max_tokens": max(4096, frozen.data["llm"]["max_tokens"]),
            "timeout_seconds": frozen.data["llm"]["timeout_seconds"], "retry": frozen.data["llm"]["retry"],
            "prompt_version": frozen.data["llm"]["prompt_version"],
        }
        expected_environment = {
            "LLM_PROVIDER": live_config["provider"], "LLM_BASE_URL": live_config.get("base_url", os.environ.get("LLM_BASE_URL")),
            "LLM_MODEL": live_config["model"],
        }
        for name, expected in expected_environment.items():
            actual = os.environ.get(name, "")
            if (actual.rstrip("/") if name == "LLM_BASE_URL" else actual) != (str(expected).rstrip("/") if name == "LLM_BASE_URL" else str(expected)):
                raise RuntimeError(f"{name} does not match the frozen live configuration")
        thinking_mode = False if args.disable_thinking else live_config["thinking_mode"]
        provider = OpenAICompatibleProvider(
            max_tokens=live_config["max_tokens"], timeout=live_config["timeout_seconds"], retry=live_config["retry"],
            thinking_mode=thinking_mode, reasoning_effort=live_config.get("reasoning_effort") if thinking_mode else None,
        )
        prompt = args.prompt or ROOT / live_config.get("prompt_path", "prompts/research_agent_v03.txt")
        prompt_version = args.prompt_version or live_config["prompt_version"]
        prompt_hash = hashlib.sha256(prompt.read_bytes()).hexdigest()
        if live_config.get("prompt_hash") and prompt_hash != live_config["prompt_hash"]:
            raise RuntimeError("Live prompt hash does not match frozen_v03_live.yaml")
        agent = LLMResearchAgent(
            provider, prompt, prompt_version, temperature=live_config["temperature"],
            max_repair_attempts=frozen.data["llm"]["max_repair_attempts"], require_v03_fields=True,
        )
        git_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        runner = LiveTaskRunner(
            frozen.data, frozen.sha256, suite.sha256, trace_root, result_root / "checkpoints", agent,
            live_frozen.sha256 if live_frozen else None,
        )
        tasks = [task for task in suite.tasks if not args.task_id or task.task_id in args.task_id]
        if not tasks:
            raise ValueError("No matching tasks")
        seeds = [args.run_seed] if args.run_seed is not None else list(live_config.get("independent_run_seeds", [301, 302, 303]))
        summaries = []
        for task in tasks:
            for seed in seeds:
                summary = runner.run_task(task, int(seed), git_commit, prompt_hash, args.max_rounds)
                summaries.append(summary)
                print(json.dumps({"run_id": summary["run_id"], "budget_spent": summary["budget_spent"], "validated": summary["validated_judgment"]["validated"]}))
        if args.max_rounds:
            smoke = {
                "live_llm_used": True, "task_count": len(tasks), "rounds_requested": args.max_rounds,
                "runs": summaries, "structured_output_pass": all(item["invalid_responses"] == 0 for item in summaries),
                "feedback_sensitivity_pass": all(item["feedback_changed_action"] for item in summaries),
            }
            (result_root / "live_llm_smoke_test.json").write_text(json.dumps(smoke, indent=2), encoding="utf-8")
        return 0 if all(item["failed_vqe_runs"] == 0 and item["invalid_responses"] == 0 for item in summaries) else 1

    git_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    prompt_hash = hashlib.sha256((ROOT / "prompts" / "research_agent_v03.txt").read_bytes()).hexdigest()
    runner = V03TaskRunner(frozen.data, frozen.sha256, suite.sha256, trace_root, result_root / "checkpoints")
    tasks = [task for task in suite.tasks if not args.task_id or task.task_id in args.task_id]
    if not tasks:
        raise ValueError("No matching tasks")
    seeds = ([args.policy_seed] if args.policy_seed is not None else frozen.data["strategies"]["random"]["policy_seeds"]) if args.strategy == "random" else [None]
    summaries = []
    for task in tasks:
        for seed in seeds:
            suite.verify_unchanged()
            summary = runner.run_task(task, args.strategy, seed, git_commit, prompt_hash)
            summaries.append(summary)
            print(json.dumps({"run_id": summary["run_id"], "budget_spent": summary["budget_spent"], "validated": summary["validated_judgment"]["validated"], "resumed": summary.get("resumed", False)}))
    return 0 if all(item["budget_spent"] == item["budget"] and item["failed_vqe_runs"] == 0 for item in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
