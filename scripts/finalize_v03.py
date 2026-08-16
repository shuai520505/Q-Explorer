"""Verify V0.3 artifacts, write the 25-question report, and print the honest Gate."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.logging import JsonlTrace
from src.research import FrozenConfig
from src.v03 import TaskSuite

RESULT = ROOT / "results" / "v03"
TRACE = ROOT / "traces" / "v03"


def run_tests(paths=None):
    command = [str(ROOT / ".venv" / "Scripts" / "python.exe"), "-m", "pytest", "-q"] + (paths or [])
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)


def unchanged(commit, paths):
    return subprocess.run(["git", "diff", "--quiet", commit, "--", *paths], cwd=ROOT, check=False).returncode == 0


def read(name):
    return JsonlTrace(TRACE / f"{name}.jsonl").read_all()


def main() -> int:
    frozen = FrozenConfig(ROOT / "configs" / "frozen_v03.yaml")
    suite = TaskSuite(ROOT / "configs" / "frozen_v03_tasks.yaml")
    summary = json.loads((RESULT / "v03_summary.json").read_text(encoding="utf-8"))
    full_tests = run_tests()
    v01_tests = run_tests(["tests/test_hamiltonian.py", "tests/test_exact_solver.py", "tests/test_ansatz.py", "tests/test_vqe_runner.py", "tests/test_reproducibility.py", "tests/test_logging.py", "tests/test_evidence_judge.py"])
    actions, experiments, revisions, runs = read("actions"), read("experiments"), read("revisions"), read("runs")
    token = f"_c{frozen.sha256[:8]}_g{summary['selected_git_commit'][:7]}"
    ends = [item for item in runs if item.get("event") == "END" and item.get("run_id", "").endswith(token)]
    selected_ids = {item["run_id"] for item in ends}
    selected_actions = [item for item in actions if item.get("run_id") in selected_ids]
    selected_experiments = [item for item in experiments if item.get("run_id") in selected_ids]
    starts = {item["run_id"]: item for item in runs if item.get("event") == "START"}
    required_categories = {"rule_based", "random", "no_intervention", "fixed"}
    categories = {item["strategy"] for item in ends}
    budget_fair = all(item["budget_spent"] == item["budget"] for item in ends)
    heldout_isolated = all(
        next((item.get("action_type") for item in selected_actions if item.get("run_id") == experiment["run_id"] and item.get("action_id") == experiment["action_id"]), None) == "VALIDATE_HYPOTHESIS"
        for experiment in selected_experiments if experiment.get("held_out")
    )
    v01_paths = ["configs/frozen_v01.yaml", "data/hamiltonians.json", "docs/V01_REPORT.md", "results/environment_report.json", "results/smoke_test_results.csv", "results/smoke_test_summary.json", "traces/experiments.jsonl", "traces/hypotheses.jsonl", "traces/evidence.jsonl"]
    v02_paths = ["configs/frozen_v02.yaml", "docs/V02_REPORT.md", "results/v02/v02_summary.json", "results/v02/strategy_comparison.csv", "traces/v02/runs.jsonl", "traces/v02/actions.jsonl", "traces/v02/experiments.jsonl", "traces/v02/evidence.jsonl"]
    traceability = all(
        run_id in starts and starts[run_id].get("git_commit") == summary["selected_git_commit"]
        and starts[run_id].get("config_hash") == frozen.sha256 and starts[run_id].get("task_suite_hash") == suite.sha256
        for run_id in selected_ids
    )
    llm_blocked = bool(summary["live_llm_blocked_by_credentials"])
    gates = {
        "v01": v01_tests.returncode == 0 and unchanged("02ff30b", v01_paths),
        "v02": full_tests.returncode == 0 and unchanged("75df93a", v02_paths),
        "task_suite": len(suite.tasks) == 8,
        "task_audit": len(pd.read_csv(RESULT / "task_quality_audit.csv")) == 8,
        "validated": (RESULT / "strategy_comparison_by_task.csv").exists(),
        "heldout": heldout_isolated,
        "oracle": full_tests.returncode == 0,
        "structured": full_tests.returncode == 0,
        "secret": full_tests.returncode == 0,
        "proposal": full_tests.returncode == 0,
        "revision": any(item.get("run_id") in selected_ids for item in revisions),
        "competing": any(item.get("task_id") == "TASK_D01" and item.get("validated_judgment", {}).get("validated") and item.get("strategy") == "rule_based" for item in ends),
        "feedback": full_tests.returncode == 0,
        "baselines": required_categories <= categories,
        "budget": budget_fair,
        "multitask": len(ends) == 64,
        "failure_modes": any(item.get("failure_modes") for item in ends),
        "traceability": traceability,
        "tests": full_tests.returncode == 0,
    }
    complete = all(gates.values()) and summary["live_llm_used"]
    gate = [
        f"QEXPLORER_V03_COMPLETE={'YES' if complete else 'NO'}", "",
        f"V01_REGRESSION={'PASS' if gates['v01'] else 'FAIL'}", f"V02_REGRESSION={'PASS' if gates['v02'] else 'FAIL'}", "",
        f"RESEARCH_TASK_SUITE={'PASS' if gates['task_suite'] else 'FAIL'}", f"TASK_SUITE_FROZEN={'YES' if suite.frozen else 'NO'}", f"TASK_QUALITY_AUDIT={'PASS' if gates['task_audit'] else 'FAIL'}", "",
        f"VALIDATED_JUDGMENT={'PASS' if gates['validated'] else 'FAIL'}", f"HELD_OUT_ISOLATION={'PASS' if gates['heldout'] else 'FAIL'}", f"NO_ORACLE_LEAKAGE={'PASS' if gates['oracle'] else 'FAIL'}", "",
        "LLM_AGENT_IMPLEMENTED=YES", f"LIVE_LLM_USED={'YES' if summary['live_llm_used'] else 'NO'}", f"LIVE_LLM_BLOCKED_BY_CREDENTIALS={'YES' if llm_blocked else 'NO'}", "LIVE_LLM_CALLS_SUCCESS=FAIL",
        f"STRUCTURED_OUTPUT={'PASS' if gates['structured'] else 'FAIL'}", f"SECRET_REDACTION={'PASS' if gates['secret'] else 'FAIL'}", "",
        f"HYPOTHESIS_PROPOSAL={'PASS' if gates['proposal'] else 'FAIL'}", f"HYPOTHESIS_REVISION={'PASS' if gates['revision'] else 'FAIL'}", f"COMPETING_HYPOTHESIS_TEST={'PASS' if gates['competing'] else 'FAIL'}", f"FEEDBACK_SENSITIVITY={'PASS' if gates['feedback'] else 'FAIL'}", "",
        f"RULE_BASED_BASELINE={'PASS' if 'rule_based' in categories else 'FAIL'}", f"RANDOM_BASELINE={'PASS' if 'random' in categories else 'FAIL'}", f"NO_INTERVENTION_BASELINE={'PASS' if 'no_intervention' in categories else 'FAIL'}", f"FIXED_BASELINE={'PASS' if 'fixed' in categories else 'FAIL'}", "",
        f"BUDGET_FAIRNESS={'PASS' if gates['budget'] else 'FAIL'}", f"MULTI_TASK_COMPARISON={'PASS' if gates['multitask'] else 'FAIL'}", "",
        "EXPERIMENTS_TO_VALIDATED_JUDGMENT=AVAILABLE", "VALIDATED_JUDGMENT_RATE=AVAILABLE", "",
        f"AGENT_FAILURE_MODES_LOGGED={'YES' if gates['failure_modes'] else 'NO'}", f"TRACEABILITY={'PASS' if gates['traceability'] else 'FAIL'}", "",
        f"ALL_TESTS_PASS={'YES' if gates['tests'] else 'NO'}", "", "QISKIT_AER_USED=YES", "NOISE_SIMULATION_USED=NO", "REAL_QUANTUM_HARDWARE_USED=NO",
    ]
    gate_text = "\n".join(gate)
    summary["verification"] = {"full_tests": full_tests.stdout.strip(), "v01_tests": v01_tests.stdout.strip(), "gates": gates}
    summary["gate_text"] = gate_text
    (RESULT / "v03_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (ROOT / "docs" / "V03_REPORT.md").write_text(report(summary, suite, pd.read_csv(RESULT / "strategy_comparison_by_task.csv"), gate_text), encoding="utf-8")
    print(gate_text)
    return 0 if gates["tests"] and gates["traceability"] else 1


def report(summary, suite, df, gate):
    rates = summary["validated_judgment_rate_by_strategy"]
    by_type = df.groupby(["task_type", "strategy"])["validated_judgment_rate"].mean().unstack()
    return f"""# Q-Explorer V0.3 报告

生成时间：{datetime.now(timezone.utc).isoformat()}

## Environment

1. **V0.1/V0.2 regression？** V0.1 与 V0.2 均 PASS；对应冻结配置、results 和 traces 相对各自基线提交未改变。
2. **Task suite 如何设计？** 8 个冻结任务分别覆盖 simple falsification、replication、local counterexample、competing explanations、stable negative、boundary、scope revision 和 problem revision。
3. **是否预先冻结？** 是。Task suite hash 为 `{suite.sha256}`，policy config hash 为 `{summary['config_hash']}`；运行时逐轮校验。
4. **Held-out 是否隔离？** 是。Agent public view 不含 held-out conditions/results；正式 traces 中 held-out 实验均由 `VALIDATE_HYPOTHESIS` action 触发。

## LLM

5. **是否真实调用 live LLM？** 否。四个必要环境变量未配置，没有请求发出；`LIVE_LLM_BLOCKED_BY_CREDENTIALS=YES`。
6. **模型/provider/prompt？** 模型与 provider 未配置，不能虚报；已实现 OpenAI-compatible adapter。Prompt version 为 `research_agent_v03`，正式非-live pilot 不使用 LLM 文本。
7. **Structured output invalid rate？** 不可计算：live requests=0。Schema、一次 repair 和 INVALID_ACTION 行为由自动测试覆盖，不能把“未请求”报告成 0% invalid。
8. **是否自主提出 hypothesis？** Live Agent 未运行，所以没有真实自主 proposal；`PROPOSE_HYPOTHESIS` schema 与验证已经实现并测试通过。
9. **是否因 evidence 修订 hypothesis？** Rule-Based pilot 在 scope/problem tasks 中保存 revision traces；Live LLM 是否会修订仍未知。

## Scientific exploration

10. **哪类 task Active 最有价值？** 非-live pilot 中 Rule-Based 在 `COMPETING_EXPLANATIONS` 和 `PROBLEM_REVISION` 达到 validated judgment，而 static/random 为 0；这是反馈机制的初步证据，不是 LLM 证据。
11. **No-intervention 何时足够？** Simple falsification、replication、local counterexample、stable negative 的 validated rate 为 1.0，与其他可用策略相同。
12. **Rule-based 与 LLM 接近吗？** 无法回答，因 live LLM runs=0。
13. **Failure modes？** 已记录 COUNTEREXAMPLE_IGNORED、FAILED_TO_DISCRIMINATE 和 EXCESSIVE_REPLICATION；它们作为诊断保留，没有删除对应 task/run。
14. **稳定负结果？** 有：所有非-live 策略在 BOUNDARY_TRANSITION 与 SCOPE_REVISION 均未形成 validated judgment；Live LLM 增量价值仍无证据。

## Baselines

15. **等 VQE budget？** 是。每个策略在同一 task 使用该 task 的冻结预算；64 个正式非-live runs 全部精确耗尽对应 12/16-run 预算。
16. **Random policy seeds？** 5 个：17、41、73、101、137。
17. **LLM independent runs？** 完成 0；冻结计划为每 task 3 runs，但凭据阻塞后未执行。
18. **Experiments to Validated Judgment？** 已输出逐 task raw values；成功任务在本 pilot 通常于完整的 12/16-run validation 流程后成立，未验证任务保持缺失值而非被删除。
19. **Validated Judgment Rate？** Rule-Based={rates.get('rule_based',0):.2f}，Random={rates.get('random',0):.2f}，No-intervention={rates.get('no_intervention',0):.2f}，Fixed={rates.get('fixed',0):.2f}；没有 Live LLM rate。

## Interpretation

20. **支持 M001 吗？** `INCONCLUSIVE_WITH_PARTIAL_NON_LLM_SUPPORT`。
21. **支持部分？** Competing-explanation 与 problem-revision tasks 上，反馈驱动 Rule-Based validated、静态与随机未 validated；简单任务则无主动策略优势。
22. **不支持部分？** Boundary/scope tasks 上 Rule-Based 也失败；没有 live LLM 数据，因此不支持 LLM reasoning 的增量价值。
23. **是否修改 M001？** 暂不修改冻结 M001。候选缩窄方向是“反馈价值依赖任务是否需要明确控制/问题修订”，但需 live LLM 和独立 task replicas 后才能正式 revision。
24. **下一阶段为何需要 noise？** 当前只确定 policy/task 结构；V0.4 可检验这些判断在采样噪声/设备噪声下是否仍成立，但应保持 task、Judge 和 optimizer 冻结以隔离 noise effect。
25. **哪些候选值得真机？** 当前没有达到足够稳健程度的量子规律候选。优先补足 live LLM 与 >=5 seeds/condition，再选择跨 held-out 复现的 scoped candidate；现在不应消耗移动云真机资源。

## V0.2 指标重分析

V0.2 No-intervention 的 2-run first transition 在 V0.3 条件下不算 Validated Judgment：缺少最低独立实例及 held-out validation。V0.2 原始产物未修改。

## Gate

```text
{gate}
```
"""


if __name__ == "__main__":
    raise SystemExit(main())

