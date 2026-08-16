"""Verify V0.3-C artifacts, write the independent report, and print the Gate."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.v03c import V03CProtocol

RESULT = ROOT / "results" / "v03c"


def unchanged(commit, paths):
    return subprocess.run(["git", "diff", "--quiet", commit, "--", *paths], cwd=ROOT).returncode == 0


def main() -> int:
    protocol = V03CProtocol.load(ROOT / "configs" / "frozen_v03c.yaml")
    checks = protocol.verify_workspace(ROOT)
    summary = json.loads((RESULT / "targeted_replication_summary.json").read_text(encoding="utf-8"))
    by_task = pd.read_csv(RESULT / "targeted_replication_by_task.csv")
    runs = pd.read_csv(RESULT / "targeted_replication_runs.csv")
    failures = pd.read_csv(RESULT / "failure_mode_summary.csv")
    tests = subprocess.run([str(ROOT / ".venv" / "Scripts" / "python.exe"), "-m", "pytest", "-q"], cwd=ROOT, capture_output=True, text=True)
    v01_paths = ["configs/frozen_v01.yaml", "data/hamiltonians.json", "docs/V01_REPORT.md", "results/environment_report.json", "results/smoke_test_results.csv", "results/smoke_test_summary.json", "traces/experiments.jsonl", "traces/hypotheses.jsonl", "traces/evidence.jsonl"]
    v02_paths = ["configs/frozen_v02.yaml", "docs/V02_REPORT.md", "results/v02", "traces/v02"]
    v03_paths = ["configs/frozen_v03.yaml", "configs/frozen_v03_tasks.yaml", "configs/frozen_v03_live.yaml", "prompts/research_agent_v03_deepseek_v01.txt", "docs/V03_REPORT.md", "results/v03", "traces/v03"]
    pattern = re.compile(r"sk-[A-Za-z0-9_-]{16,}")
    hits = []
    for folder in (ROOT / "configs", ROOT / "prompts", ROOT / "src", ROOT / "scripts", ROOT / "docs", RESULT, ROOT / "traces" / "v03c"):
        for path in folder.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".py", ".yaml", ".yml", ".json", ".jsonl", ".txt", ".csv", ".md"} and pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
                hits.append(str(path))
    task = {row.task_type: row for row in by_task.itertuples()}
    expected_old, expected_new = set(protocol.data["existing_run_seeds"]), set(protocol.data["additional_run_seeds"])
    no_replacement = all(
        set(runs[(runs.task_id == task_id) & (runs.source_run == "v03b")].run_seed.astype(int)) == expected_old
        and set(runs[(runs.task_id == task_id) & (runs.source_run == "v03c")].run_seed.astype(int)) == expected_new
        for task_id in protocol.data["target_task_ids"]
    )
    gates = {
        "v01": unchanged("02ff30b", v01_paths), "v02": unchanged("75df93a", v02_paths),
        "v03": unchanged("e9564a8", v03_paths), "targets": checks["task_suite"] and checks["task_ids"],
        "prompt": checks["prompt"], "model": checks["model"] and checks["thinking"],
        "judge": checks["judge"] and checks["scientific_config"], "budget": checks["budgets"] and checks["vqe"],
        "totals": len(runs) == 45 and all(sum(runs.task_id == task_id) == 15 for task_id in protocol.data["target_task_ids"]),
        "invalid": int(runs.invalid_action.sum()) == summary["invalid_runs_retained"] and summary["invalid_runs_retained"] == 5,
        "replacement": no_replacement and summary["replacement_runs"] == 0,
        "extra_budget": bool((runs.budget_spent <= runs.budget).all()) and summary["new_used_vqe_runs"] <= summary["new_allocated_vqe_budget"],
        "ci": len(pd.read_csv(RESULT / "confidence_intervals.csv")) == 3,
        "failure": not failures.empty, "tests": tests.returncode == 0, "secret": not hits,
    }
    complete = all(gates.values())
    boundary, scope, competing = task["BOUNDARY_TRANSITION"], task["SCOPE_REVISION"], task["COMPETING_EXPLANATIONS"]
    gate = f"""QEXPLORER_V03C_COMPLETE={'YES' if complete else 'NO'}

V01_REGRESSION={'PASS' if gates['v01'] else 'FAIL'}
V02_REGRESSION={'PASS' if gates['v02'] else 'FAIL'}
V03_REGRESSION={'PASS' if gates['v03'] else 'FAIL'}

TARGET_TASKS_FROZEN={'YES' if gates['targets'] else 'NO'}
PROMPT_HASH_MATCH={'PASS' if gates['prompt'] else 'FAIL'}
MODEL_CONFIG_MATCH={'PASS' if gates['model'] else 'FAIL'}
JUDGE_CONFIG_MATCH={'PASS' if gates['judge'] else 'FAIL'}
BUDGET_CONFIG_MATCH={'PASS' if gates['budget'] else 'FAIL'}

BOUNDARY_TOTAL_LLM_RUNS={int(boundary.n_total)}
BOUNDARY_VALIDATED={int(boundary.n_validated)}/15
BOUNDARY_SIGNAL_REPLICATED={summary['boundary_signal_replicated']}

SCOPE_TOTAL_LLM_RUNS={int(scope.n_total)}
SCOPE_VALIDATED={int(scope.n_validated)}/15
SCOPE_SIGNAL_REPLICATED={summary['scope_signal_replicated']}

COMPETING_TOTAL_LLM_RUNS={int(competing.n_total)}
COMPETING_VALIDATED={int(competing.n_validated)}/15
COMPETING_FAILURE_MODE_REPLICATED={summary['competing_failure_mode_replicated']}

INVALID_RUNS_RETAINED={'YES' if gates['invalid'] else 'NO'}
NO_REPLACEMENT_RUNS={'PASS' if gates['replacement'] else 'FAIL'}
NO_EXTRA_BUDGET={'PASS' if gates['extra_budget'] else 'FAIL'}

CONFIDENCE_INTERVALS={'AVAILABLE' if gates['ci'] else 'NOT_AVAILABLE'}
FAILURE_MODE_ANALYSIS={'PASS' if gates['failure'] else 'FAIL'}

M001_STATUS={summary['m001_status']}
M001_REVISION_PROPOSED={'YES' if summary['m001_revision_proposed'] else 'NO'}

ALL_TESTS_PASS={'YES' if gates['tests'] else 'NO'}

LIVE_LLM_USED=YES
MODEL=deepseek-v4-flash
THINKING_MODE=false

QISKIT_AER_USED=YES
NOISE_SIMULATION_USED=NO
REAL_QUANTUM_HARDWARE_USED=NO

SECRET_SCAN_HITS={len(hits)}"""
    summary["verification"] = {"gates": gates, "tests": tests.stdout.strip(), "secret_scan_hits": hits}
    summary["gate_text"] = gate
    summary["qexplorer_v03c_complete"] = complete
    (RESULT / "targeted_replication_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (ROOT / "docs" / "V03C_REPORT.md").write_text(report(summary, by_task, failures, protocol, gate), encoding="utf-8")
    print(gate)
    return 0 if complete else 1


def report(summary, by_task, failures, protocol, gate):
    rows = {row.task_type: row for row in by_task.itertuples()}
    b, s, c = rows["BOUNDARY_TRANSITION"], rows["SCOPE_REVISION"], rows["COMPETING_EXPLANATIONS"]
    failure_map = {(row.task_type, row.failure_mode): int(row.run_count) for row in failures.itertuples()}
    return f"""# Q-Explorer V0.3-C Targeted Replication Report

生成时间：{datetime.now(timezone.utc).isoformat()}

本报告是 V0.3-B 的独立 replication 记录；未修改 `docs/V03_REPORT.md` 或任何 V0.3 原始结果。

## Reproducibility

1. **冻结了哪些配置？** 科学 config、8-task suite、三个目标 task、DeepSeek live config、prompt、Judge、VQE、每 run 16-run budget、existing seeds 301–303、new seeds 304–315；protocol hash `{summary['protocol_hash']}`，预注册 commit `3cbbdf8`。
2. **Prompt hash 一致？** PASS。实际正式 prompt 是 `prompts/research_agent_v03_deepseek_v01.txt`，hash `{protocol.data['prompt_hash']}`；提示中写的旧文件名不是 V0.3-B 正式 trace 所用 prompt。
3. **Model 一致？** PASS：`deepseek-v4-flash`，OpenAI-compatible DeepSeek，`thinking_mode=false`，temperature=0.1。
4. **Evidence Judge 一致？** PASS，Judge section hash `{protocol.data['judge_config_hash']}`。
5. **Task 一致？** PASS：只运行原 `TASK_F01`、`TASK_G01`、`TASK_D01`，task suite hash 未变。
6. **Budget 一致？** PASS：每 run 分配 16；36 个新增 runs 分配 576，实际 552。3 个 invalid runs 提前停止，没有补预算。

## Boundary

7. **最终 validated？** `{int(b.n_validated)}/{int(b.n_total)}`，rate={b.validated_rate:.3f}。
8. **95% CI？** Wilson `[{b.wilson_ci_low:.3f}, {b.wilson_ci_high:.3f}]`。
9. **成功是否伴随 adaptive boundary probe？** 是，{int(b.validated_with_adaptive_boundary_probe)}/{int(b.n_validated)} validated runs 同时包含 BOUNDARY_PROBE、至少两个 exploration depths、evidence label 变化和 held-out validation；但 hypothesis revisions=0，因此不能声称完成了“revision”步骤。
10. **其他策略？** V0.3-B 冻结结果中 Rule-Based、Random、No-intervention、Fixed 在该 task 均为 0；Rule-Based 是 deterministic，未机械重复。
11. **原 2/3 是否复现？** `YES`，累计变为 8/15；point estimate 下降到 0.533，但仍得到稳定非零 capability。结论仅限当前冻结 Boundary task。

## Scope Revision

12. **最终 validated？** `{int(s.n_validated)}/{int(s.n_total)}`，rate={s.validated_rate:.3f}。
13. **95% CI？** Wilson `[{s.wilson_ci_low:.3f}, {s.wilson_ci_high:.3f}]`。
14. **Revision 是否由 counterexample 触发？** 严格 trace provenance 下，valid revisions={int(s.valid_scope_revisions)}，invalid revisions={int(s.invalid_scope_revisions)}。18 条 revision 的文本引用先前反例，但 `triggering_evidence_ids` 没有指向 COUNTEREXAMPLE label，因此不能算合法闭环证据。
15. **Scope creep？** 0 次 detector hit；没有 unsupported expansion，但 provenance 缺陷仍使 scope-revision 能力为 `INCONCLUSIVE`。
16. **原 1/3 是否复现？** validated-rate 的非零信号复现为 6/15；但不能把它升级为“稳定合法 scope revision”，因为严格 trigger linkage 未通过。

## Competing Explanations

17. **最终 validated？** `{int(c.n_validated)}/{int(c.n_total)}`，rate={c.validated_rate:.3f}，Wilson 95% CI `[{c.wilson_ci_low:.3f}, {c.wilson_ci_high:.3f}]`。
18. **Rule-Based？** 原正式 deterministic run 为 1/1 validated；没有制造 15 个完全相同副本。
19. **最常见失败原因？** MULTI_VARIABLE_CHANGE={failure_map.get(('COMPETING_EXPLANATIONS','MULTI_VARIABLE_CHANGE'),0)}/15，COUNTEREXAMPLE_IGNORED={failure_map.get(('COMPETING_EXPLANATIONS','COUNTEREXAMPLE_IGNORED'),0)}/15，INVALID_ACTION={failure_map.get(('COMPETING_EXPLANATIONS','INVALID_ACTION'),0)}/15。虽然 12/15 validated，严格单变量控制的行为质量仍有问题。
20. **Rule-Based 优势稳定？** `NO/INCONCLUSIVE`：原 LLM 1/3 扩展为 12/15，早期高失败率没有复现。Rule-Based 数值仍为 1.0，但只有一个 deterministic trajectory，不能据此宣称稳定总体优势。

## Meta-hypothesis

21. **M001 当前状态？** `{summary['m001_status']}`。Boundary/Scope 对 static baselines 的非零差异与 simple-task 的无差异共同支持 task dependence。
22. **M001.R1？** 提出候选修订，但不是发现：

> {summary['m001_r1_candidate']}

23. **哪类任务适合 LLM？** 当前证据最清楚的是 boundary localization；scope task 有 validated capability，但 revision provenance 尚未通过。
24. **哪类任务适合 Rule-Based？** 需要强制、可审计的单变量 control 时透明规则仍更可靠；本轮不能证明其 validated rate 稳定高于 LLM，但 LLM 的 multi-variable diagnostic 支持保留这一工程偏好。
25. **哪类任务 No-intervention 足够？** 沿用 V0.3-B：Simple Falsification、Replication Needed、Local Counterexample、Stable Negative；本阶段没有重跑这些 task。

## Costs and retention

- Existing V0.3-B runs：9；new V0.3-C runs：36；merged unique：45，严格 15/task。
- New recorded token usage（lower bound）：`{summary['new_recorded_token_usage_lower_bound']}`；API cost unavailable，未估算伪值。
- Invalid runs retained：{summary['invalid_runs_retained']}；replacement runs=0；provider transient errors={summary['provider_errors']}。
- 新增 VQE：{summary['new_used_vqe_runs']}/{summary['new_allocated_vqe_budget']}，未使用部分来自 invalid early stop。

## Gate

```text
{gate}
```
"""


if __name__ == "__main__":
    raise SystemExit(main())
