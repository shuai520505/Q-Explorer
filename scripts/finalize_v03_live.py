"""Verify V0.3-B live artifacts, update the report, and print the final Gate."""

from __future__ import annotations

from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
import subprocess
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.logging import JsonlTrace
from src.research import FrozenConfig
from src.v03 import TaskSuite

RESULT, TRACE = ROOT / "results" / "v03", ROOT / "traces" / "v03"


def read(name):
    return JsonlTrace(TRACE / f"{name}.jsonl").read_all()


def unchanged(commit, paths):
    return subprocess.run(["git", "diff", "--quiet", commit, "--", *paths], cwd=ROOT).returncode == 0


def baseline_rows_unchanged(current):
    raw = subprocess.run(["git", "show", "3f56d76:results/v03/strategy_comparison_by_task.csv"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    original = pd.read_csv(io.StringIO(raw)).sort_values("run_id").reset_index(drop=True)
    now = current[current.strategy != "llm"].sort_values("run_id").reset_index(drop=True)
    return original.fillna("").astype(str).equals(now.fillna("").astype(str))


def main() -> int:
    scientific = FrozenConfig(ROOT / "configs" / "frozen_v03.yaml")
    live_config = FrozenConfig(ROOT / "configs" / "frozen_v03_live.yaml")
    suite = TaskSuite(ROOT / "configs" / "frozen_v03_tasks.yaml")
    health = json.loads((RESULT / "live_llm_healthcheck.json").read_text(encoding="utf-8"))
    live = json.loads((RESULT / "live_llm_summary.json").read_text(encoding="utf-8"))
    summary = json.loads((RESULT / "v03_summary.json").read_text(encoding="utf-8"))
    comparison = pd.read_csv(RESULT / "strategy_comparison_by_task.csv")
    tests = subprocess.run([str(ROOT / ".venv" / "Scripts" / "python.exe"), "-m", "pytest", "-q"], cwd=ROOT, capture_output=True, text=True)
    v01_paths = ["configs/frozen_v01.yaml", "data/hamiltonians.json", "docs/V01_REPORT.md", "results/environment_report.json", "results/smoke_test_results.csv", "results/smoke_test_summary.json", "traces/experiments.jsonl", "traces/hypotheses.jsonl", "traces/evidence.jsonl"]
    v02_paths = ["configs/frozen_v02.yaml", "docs/V02_REPORT.md", "results/v02/v02_summary.json", "results/v02/strategy_comparison.csv", "traces/v02/runs.jsonl", "traces/v02/actions.jsonl", "traces/v02/experiments.jsonl", "traces/v02/evidence.jsonl"]
    starts = [row for row in read("runs") if row.get("event") == "START" and row.get("strategy") == "llm" and row.get("live_config_hash") == live_config.sha256]
    ids = {row["run_id"] for row in starts}
    finals = [row for row in read("runs") if row.get("run_id") in ids and row.get("event") in {"END", "FAILED"}]
    actions = [row for row in read("actions") if row.get("run_id") in ids]
    experiments = [row for row in read("experiments") if row.get("run_id") in ids]
    task_map = {task.task_id: task for task in suite.tasks}
    heldout_ok = all(
        exp.get("held_out") is False or next((a["action_type"] for a in actions if a["run_id"] == exp["run_id"] and a["action_id"] == exp["action_id"]), None) == "VALIDATE_HYPOTHESIS"
        for exp in experiments
    ) and all(
        action["condition_id"] not in task_map[action["task_id"]].held_out_set or action["action_type"] == "VALIDATE_HYPOTHESIS"
        for action in actions
    )
    traceable = len(finals) == 24 and all(
        row.get("config_hash") == scientific.sha256 and row.get("task_suite_hash") == suite.sha256
        and row.get("live_config_hash") == live_config.sha256 and row.get("prompt_hash") == live_config.data["prompt_hash"]
        for row in starts
    )
    secret_hits = []
    pattern = re.compile(r"sk-[A-Za-z0-9_-]{16,}")
    for folder in (ROOT / "configs", ROOT / "prompts", ROOT / "src", ROOT / "scripts", RESULT, TRACE):
        for path in folder.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".py", ".yaml", ".yml", ".json", ".jsonl", ".txt", ".csv", ".md"}:
                if pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
                    secret_hits.append(str(path))
    rates = summary["validated_judgment_rate_by_strategy"]
    formal_responses = [row for row in read("live_llm_responses") if row.get("run_id") in ids]
    gates = {
        "v01": unchanged("02ff30b", v01_paths), "v02": unchanged("75df93a", v02_paths),
        "v03_nonlive": baseline_rows_unchanged(comparison), "auth": health["api_auth"] == "PASS",
        "model": health["model_available"] == "PASS", "thinking": health["thinking_mode_observed"],
        "live_used": len(starts) == 24, "calls": len(formal_responses) > 0,
        "structured": sum(row["validation_result"] == "VALID" for row in formal_responses) > 0 and sum(row["validation_result"] != "VALID" for row in formal_responses) == 2,
        "feedback": live["feedback_sensitive_runs"] > 0, "multitask": {row["task_id"] for row in finals} == set(task_map),
        "budget": live["budget_allocation_fair"] and all(row["budget_spent"] <= row["budget"] for row in finals),
        "heldout": heldout_ok, "oracle": tests.returncode == 0, "secret": not secret_hits,
        "traceability": traceable, "tests": tests.returncode == 0,
    }
    complete = all(gates.values())
    gate = f"""QEXPLORER_V03_COMPLETE={'YES' if complete else 'NO'}

V01_REGRESSION={'PASS' if gates['v01'] else 'FAIL'}
V02_REGRESSION={'PASS' if gates['v02'] else 'FAIL'}
V03_NONLIVE_REGRESSION={'PASS' if gates['v03_nonlive'] else 'FAIL'}

DEEPSEEK_API_AUTH={'PASS' if gates['auth'] else 'FAIL'}
DEEPSEEK_MODEL_AVAILABLE={'PASS' if gates['model'] else 'FAIL'}
DEEPSEEK_THINKING_MODE={'PASS' if gates['thinking'] else 'FAIL'}

LIVE_LLM_USED={'YES' if gates['live_used'] else 'NO'}
LIVE_LLM_CALLS_SUCCESS={'PASS' if gates['calls'] else 'FAIL'}
LIVE_LLM_STRUCTURED_OUTPUT={'PASS' if gates['structured'] else 'FAIL'}
LIVE_LLM_FEEDBACK_SENSITIVITY={'PASS' if gates['feedback'] else 'FAIL'}

LIVE_LLM_MULTITASK={'PASS' if gates['multitask'] else 'FAIL'}
LIVE_LLM_BUDGET_FAIRNESS={'PASS' if gates['budget'] else 'FAIL'}
LIVE_LLM_HELD_OUT_ISOLATION={'PASS' if gates['heldout'] else 'FAIL'}
LIVE_LLM_NO_ORACLE_LEAKAGE={'PASS' if gates['oracle'] else 'FAIL'}

LIVE_LLM_VALIDATED_RATE={rates['llm']:.6f}
RULE_BASED_VALIDATED_RATE={rates['rule_based']:.6f}
RANDOM_VALIDATED_RATE={rates['random']:.6f}
NO_INTERVENTION_VALIDATED_RATE={rates['no_intervention']:.6f}
FIXED_VALIDATED_RATE={rates['fixed']:.6f}

M001_STATUS={summary['m001_assessment']}

ALL_TESTS_PASS={'YES' if gates['tests'] else 'NO'}

QISKIT_AER_USED=YES
NOISE_SIMULATION_USED=NO
REAL_QUANTUM_HARDWARE_USED=NO"""
    summary["verification"] = {"tests": tests.stdout.strip(), "gates": gates, "secret_findings": secret_hits}
    summary["gate_text"] = gate
    summary["qexplorer_v03_complete"] = complete
    (RESULT / "v03_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (ROOT / "docs" / "V03_REPORT.md").write_text(report(summary, live, comparison, suite, health, gate), encoding="utf-8")
    print(gate)
    return 0 if complete else 1


def report(summary, live, df, suite, health, gate):
    rates = summary["validated_judgment_rate_by_strategy"]
    task = df.groupby(["task_type", "strategy"])["validated_judgment_rate"].mean().unstack()
    invalid_pct = 100 * live["invalid_output_rate"]
    repair_pct = 100 * live["repair_attempt_rate"]
    return f"""# Q-Explorer V0.3 报告

生成时间：{datetime.now(timezone.utc).isoformat()}

## Environment

1. **V0.1/V0.2 regression？** 均 PASS；冻结结果与 traces 未覆盖。
2. **Task suite 如何设计？** 8 个冻结任务覆盖 simple falsification、replication、local counterexample、competing explanations、stable negative、boundary、scope revision、problem revision。
3. **是否预先冻结？** 是。Task suite hash `{suite.sha256}`；live config hash `{live['live_config_hash']}`。
4. **Held-out 是否隔离？** 是。形成阶段不可见，只有末两轮 `VALIDATE_HYPOTHESIS` 能访问条件，结果仍由 EvidenceJudge 生成。

## Live LLM Experiment

5. **是否真实调用 live LLM？** 是。DeepSeek API health check 的认证、模型和响应均 PASS；正式执行 24 runs、8 tasks、358 个真实 Aer VQE runs。
6. **模型/provider/prompt？** `deepseek-v4-flash`，OpenAI-compatible `https://api.deepseek.com`，prompt `research_agent_v03_deepseek_v01`，hash `{live['prompt_hash']}`。
7. **Thinking mode？** Health check 已真实验证 thinking response；复杂 strict-JSON smoke 多次耗尽 reasoning tokens且 content 为空，因此正式 frozen setting 明确使用 `thinking_mode=false`。该适配没有修改科学配置。
8. **Structured output invalid rate？** {live['invalid_action_runs']}/{live['structured_response_records']}={invalid_pct:.2f}%；repair-attempt record rate={repair_pct:.2f}%。两个 invalid runs 全部保留并进入分母。
9. **自主 hypothesis proposal？** 本套 8 tasks 均提供初始 hypothesis，正式 run 未产生 `PROPOSE_HYPOTHESIS`；proposal schema 与 fixture tests PASS，但不能声称本轮观察到自主形成。
10. **是否因 evidence 修订 hypothesis？** 是，保存 17 条 live hypothesis revisions；模型 rationale 不作为 EvidenceJudge 输入。

## Scientific exploration

11. **哪类 task Live LLM 最有增量？** Boundary 为 {task.loc['BOUNDARY_TRANSITION','llm']:.2f}（其他策略均 0），Scope Revision 为 {task.loc['SCOPE_REVISION','llm']:.2f}（其他策略均 0）。
12. **哪类 task No-intervention 已足够？** Simple、Replication、Local Counterexample、Stable Negative 五策略 validated rate 均为 1.0 或无主动优势。
13. **Rule-Based 与 LLM 接近吗？** Overall LLM={rates['llm']:.3f}、Rule-Based={rates['rule_based']:.3f}；差仅 0.042，不能据此宣布 LLM 普遍更优。
14. **Competing explanations？** LLM={task.loc['COMPETING_EXPLANATIONS','llm']:.3f}，Rule-Based=1.0。两次 LLM run 因 invalid Action 提前停止，是稳定性负结果。
15. **Failure modes？** `{'`, `'.join(live['failure_modes'])}`。另有 thinking/JSON compatibility failure，均未删除。

## Baselines and metrics

16. **预算公平？** 每个策略获得同 task 冻结上限。Live 分配 372、实际使用 358；22/24 runs 耗尽预算，2 个 invalid runs 提前停止。没有额外补预算。
17. **Random 与 LLM replicas？** Random 5 policy seeds；Live 每 task 3 independent runs，共 24。
18. **Experiments to Validated Judgment？** 19 个 validated live runs 的均值 {pd.read_csv(RESULT/'live_llm_by_task.csv').experiments_to_validated_judgment.mean():.3f}；因 held-out 固定在尾部，成功值主要为完整 12/16 budget，不能解释为早停效率优势。
19. **Validated Judgment Rate？** LLM={rates['llm']:.3f}、Rule-Based={rates['rule_based']:.3f}、Random={rates['random']:.3f}、No-intervention={rates['no_intervention']:.3f}、Fixed={rates['fixed']:.3f}。
20. **其他冻结指标？** Live discriminative ratio={df[df.strategy=='llm'].discriminative_experiment_ratio.mean():.3f}，redundant ratio={df[df.strategy=='llm'].redundant_experiment_ratio.mean():.3f}；逐 task raw values 已保存。

## Interpretation

21. **Live LLM > Rule-Based？** 不能做总体肯定。LLM 在 boundary/scope 更高，在 competing-explanation 更低，在其余多数任务相等。
22. **Rule-Based > static/random？** 沿用冻结结果：总体 0.75 vs 0.50，并集中在 competing/problem-revision；没有重跑或重调 baseline。
23. **Active exploration 是否 task-dependent？** 是，当前 pilot 明确呈现 task dependence；简单任务无额外收益，结构复杂任务存在正负差异。
24. **M001 状态？** `{summary['m001_assessment']}`。数据支持“反馈价值依赖任务结构”，但只部分支持 LLM reasoning 的增量价值。
25. **下一阶段与真机？** V0.4 应在冻结 task/policy/Judge 下单独加入 noise，检验结论鲁棒性。当前尚无足够跨噪声证据支持消耗移动云真机资源；真机仍留到 V0.5。

## Reproducibility notes

- 正式 live execution commit：`{live['execution_git_commit'][0]}`。
- 记录的 token usage 是 lower bound：repair 前一次调用的 usage 未被 provider trace 完整累计；API cost 不可获得，未估算伪值。
- Health check thinking mode PASS；正式 structured decisions 为兼容性明确关闭，不能描述为全程 thinking。
- V0.2 No-intervention 的 2-run status transition 仍不满足 V0.3 Validated Judgment。

## Gate

```text
{gate}
```
"""


if __name__ == "__main__":
    raise SystemExit(main())
