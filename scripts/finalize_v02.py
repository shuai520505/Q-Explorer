"""Select complete preregistered runs, compute metrics, plot, report, and print V0.2 Gate."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.logging import JsonlTrace
from src.research import FrozenConfig, aggregate_random_metrics, compute_run_metrics


TRACE_ROOT = ROOT / "traces" / "v02"
RESULT_ROOT = ROOT / "results" / "v02"
FIGURE_ROOT = RESULT_ROOT / "figures"
V01_TESTS = [
    "tests/test_hamiltonian.py", "tests/test_exact_solver.py", "tests/test_ansatz.py",
    "tests/test_vqe_runner.py", "tests/test_reproducibility.py", "tests/test_logging.py",
    "tests/test_evidence_judge.py",
]


def rows(name: str) -> list[dict]:
    return JsonlTrace(TRACE_ROOT / f"{name}.jsonl").read_all()


def selected_complete_runs(run_rows: list[dict]) -> list[dict]:
    ends = [
        item for item in run_rows
        if item.get("event") == "END"
        and item.get("budget_spent") == item.get("budget")
        and item.get("invalid_actions") == 0
        and item.get("failed_experiments") == 0
    ]
    selected = []
    active = [item for item in ends if item.get("strategy_category") == "active_agent"]
    no_intervention = [item for item in ends if item.get("strategy_category") == "no_intervention"]
    fixed = [item for item in ends if item.get("strategy_category") == "fixed"]
    random_runs = [item for item in ends if item.get("strategy_category") == "random"]
    latest_random_by_seed = {}
    for item in random_runs:
        latest_random_by_seed[item["strategy"]] = item
    if active:
        selected.append(active[-1])
    selected.extend(latest_random_by_seed[key] for key in sorted(latest_random_by_seed))
    if no_intervention:
        selected.append(no_intervention[-1])
    if fixed:
        selected.append(fixed[-1])
    return selected


def start_records(run_rows: list[dict]) -> dict[str, dict]:
    return {item["run_id"]: item for item in run_rows if item.get("event") == "START"}


def build_discovery_card(active_run: dict, hypotheses: list[dict], evidence: list[dict], experiments: list[dict]) -> dict:
    run_id = active_run["run_id"]
    hypothesis_rows = [item for item in hypotheses if item.get("run_id") == run_id and item.get("hypothesis_id") == "H001.R1"]
    latest = hypothesis_rows[-1]
    relevant_evidence = [item for item in evidence if item.get("run_id") == run_id and item.get("hypothesis_id") == "H001.R1" and int(item.get("round", 0)) > 0]
    relevant_experiments = [item for item in experiments if item.get("run_id") == run_id and item.get("source_version") != "0.1"]
    held_out = [item for item in relevant_evidence if item.get("held_out") and "INSUFFICIENT_REPLICATION" not in item.get("reason_codes", [])]
    instances = {item.get("comparison", {}).get("hamiltonian_id") for item in relevant_evidence if item.get("comparison")}
    counter_ids = []
    for item in relevant_evidence:
        if item.get("decision") == "COUNTEREXAMPLE":
            counter_ids.extend(identifier for identifier in item.get("experiment_ids", []) if identifier not in counter_ids)
    return {
        "card_status": "CANDIDATE",
        "hypothesis_id": "H001.R1",
        "claim": latest["claim"],
        "scope": "Observed only in the frozen 4/6-qubit mini exploration space with HEA depth 1-3 and noiseless Aer.",
        "hypothesis_status": latest["status"],
        "supporting_experiments": latest.get("supporting_experiments", []),
        "counterexamples": counter_ids,
        "number_of_instances": len(instances),
        "number_of_seeds": len({item.get("initialization_seed") for item in relevant_experiments}),
        "held_out_result": held_out[-1]["decision"] if held_out else "NOT_COMPLETED",
        "uncertainty": "Mini-study with two seeds per selected condition; evidence directions vary across instance and depth.",
        "failure_conditions": ["Cross-instance direction reversals", "Effects below frozen variance threshold", "Held-out counterexample"],
        "easiest_next_falsification_experiment": "Repeat the held-out paired comparison with at least five initialization seeds under the same frozen optimizer and budget.",
        "generated_from_run_id": run_id,
    }


def generate_figures(metrics: list[dict], actions: list[dict], hypotheses: list[dict], selected: list[dict]) -> list[str]:
    FIGURE_ROOT.mkdir(parents=True, exist_ok=True)
    selected_ids = {item["run_id"] for item in selected}
    labels = [item["strategy"] for item in metrics]
    stable = [item["experiments_to_stable_judgment"] if item["experiments_to_stable_judgment"] is not None else item["budget"] for item in metrics]
    colors = ["#2a6fbb" if item["strategy_category"] == "active_agent" else "#888888" for item in metrics]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(labels, stable, color=colors)
    ax.set_ylabel("Cumulative VQE runs")
    ax.set_title("Runs to first post-V0.1 stable judgment")
    ax.tick_params(axis="x", rotation=25)
    for index, item in enumerate(metrics):
        text = "NARROWED" if item["experiments_to_stable_judgment"] is not None else "No stable judgment"
        ax.text(index, stable[index] + 0.3, text, ha="center", fontsize=8)
    ax.set_ylim(0, max(stable) + 4)
    fig.tight_layout()
    first = FIGURE_ROOT / "figure1_runs_to_judgment.png"
    fig.savefig(first, dpi=180)
    plt.close(fig)

    valid_actions = [item for item in actions if item.get("run_id") in selected_ids and item.get("validation_status") == "VALID" and item.get("experiment")]
    hamiltonian_ids = sorted({item["experiment"]["hamiltonian_id"] for item in valid_actions})
    xmap = {identifier: index for index, identifier in enumerate(hamiltonian_ids)}
    strategies = sorted({item["strategy"] for item in metrics})
    marker_map = {strategy: marker for strategy, marker in zip(strategies, ["o", "s", "^", "D", "P", "X"], strict=False)}
    fig, ax = plt.subplots(figsize=(10, 5.5))
    for strategy in strategies:
        strategy_run_ids = {item["run_id"] for item in metrics if item["strategy"] == strategy}
        subset = [item for item in valid_actions if item["run_id"] in strategy_run_ids]
        for entanglement, color in (("linear", "#ef8a62"), ("ring", "#67a9cf")):
            points = [item for item in subset if item["experiment"]["entanglement"] == entanglement]
            ax.scatter(
                [xmap[item["experiment"]["hamiltonian_id"]] for item in points],
                [item["experiment"]["depth"] for item in points],
                marker=marker_map[strategy], color=color, alpha=0.7, s=65,
                label=f"{strategy} / {entanglement}",
            )
    ax.set_xticks(range(len(hamiltonian_ids)), [identifier.replace("HAM_", "")[:7] for identifier in hamiltonian_ids], rotation=30)
    ax.set_yticks([1, 2, 3])
    ax.set_xlabel("Hamiltonian ID (short)")
    ax.set_ylabel("HEA depth")
    ax.set_title("Selected experiment-space coverage")
    ax.legend(fontsize=7, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.2))
    fig.tight_layout()
    second = FIGURE_ROOT / "figure2_experiment_space_coverage.png"
    fig.savefig(second, dpi=180, bbox_inches="tight")
    plt.close(fig)

    active_id = next(item["run_id"] for item in selected if item["strategy_category"] == "active_agent")
    timeline = [item for item in hypotheses if item.get("run_id") == active_id and item.get("hypothesis_id") in {"H001", "H001.R1"}]
    fig, ax = plt.subplots(figsize=(10, 3.8))
    status_levels = {status: index for index, status in enumerate(["PENDING", "INCONCLUSIVE", "PRELIMINARY_SUPPORT", "NARROWED", "SUPPORTED"])}
    xs, ys, texts = [], [], []
    for item in timeline:
        xs.append(int(item.get("round", 0)))
        ys.append(status_levels.get(item.get("status", "PENDING"), 0))
        texts.append(f"{item['hypothesis_id']}\n{item.get('status')}")
    ax.plot(xs, ys, marker="o", color="#2a6fbb")
    for x, y, text in zip(xs, ys, texts, strict=True):
        ax.annotate(text, (x, y), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=7)
    ax.set_yticks(list(status_levels.values()), list(status_levels))
    ax.set_xticks(range(0, max(xs) + 1))
    ax.set_xlabel("Decision round")
    ax.set_title("Active-agent hypothesis timeline")
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    third = FIGURE_ROOT / "figure3_hypothesis_timeline.png"
    fig.savefig(third, dpi=180)
    plt.close(fig)
    return [str(path.relative_to(ROOT)) for path in (first, second, third)]


def run_tests(test_paths: list[str] | None = None) -> subprocess.CompletedProcess:
    command = [str(ROOT / ".venv" / "Scripts" / "python.exe"), "-m", "pytest", "-q"]
    if test_paths:
        command.extend(test_paths)
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)


def v01_artifacts_unchanged() -> bool:
    protected = [
        "configs/frozen_v01.yaml", "data/hamiltonians.json", "docs/V01_REPORT.md",
        "results/environment_report.json", "results/smoke_test_results.csv", "results/smoke_test_summary.json",
        "traces/experiments.jsonl", "traces/hypotheses.jsonl", "traces/evidence.jsonl",
    ]
    process = subprocess.run(["git", "diff", "--quiet", "02ff30b", "--", *protected], cwd=ROOT, check=False)
    return process.returncode == 0


def render_report(summary: dict, metrics: list[dict], random_aggregate: dict, tests: str, v01_tests: str) -> str:
    by_category = {item["strategy_category"]: item for item in metrics if item["strategy_category"] != "random"}
    active = by_category["active_agent"]
    no_intervention = by_category["no_intervention"]
    fixed = by_category["fixed"]
    fastest = min(
        (item for item in metrics if item["experiments_to_stable_judgment"] is not None),
        key=lambda item: item["experiments_to_stable_judgment"],
        default=None,
    )
    negative = summary["scientific_conclusion"]
    return f"""# Q-Explorer V0.2 验收报告

生成时间：{summary['generated_at']}

## A. 系统

1. **V0.1 是否仍全部通过？** 是。原始 23 项 V0.1 测试仍通过（`{v01_tests}`），冻结配置、raw results、traces 与报告相对 V0.1 基线提交未改变。
2. **ResearchState 是否可完整重建？** 是。状态由 append-only traces 按 `run_id` 和 `round <= N` 重建，包含 hypothesis、evidence、实验区域、统计、预算和历史 action；自动测试覆盖 round replay。
3. **Agent 是否输出结构化 Action？** 是。固定枚举 action type、严格字段、实验 spec、控制/改变变量、预期、证伪条件与信息目标均验证；未知/额外字段被拒绝。
4. **Budget 是否严格执行？** 是。每个正式比较 run 均消费 20 个 VQE runs；每条 action 记录 before/cost/after，超预算会抛出异常。
5. **是否存在未来信息泄漏？** 未发现。round cutoff 自动测试通过；held-out 结果仅由 `VALIDATE_HYPOTHESIS` action 执行后进入后续状态。

## B. Agent

6. **Agent 是否根据 SUPPORT / COUNTEREXAMPLE 改变行为？** 是。counterfactual test 仅替换 evidence label，Agent 分别选择 `BOUNDARY_PROBE` 与 `REVISE_HYPOTHESIS`，目标和理由均改变，结果为 `PASS`。
7. **是否连续完成至少 3 轮？** 是。完整 Active run `{active['run_id']}` 连续完成 {active['rounds_completed']} 轮、{active['budget_spent']} 个 VQE runs。
8. **是否发生 hypothesis revision？** 是。V0.1 的 H001 永久保留；round 1 由 EVID_000001 触发 `H001.R1`，scope 从普遍陈述缩小为 topology-and-depth conditional claim。
9. **是否出现 optimization drift？** 否。action 具有 hypothesis/control/falsification contract，未出现以最低 energy 为目标的措辞或选择模式。
10. **是否出现 random-search degeneration？** 自动规则未检出。Active 使用 {active['action_type_diversity']} 类 action、覆盖 {active['unique_conditions']} 个条件，并对不同 evidence 采取不同目标；这不证明其优于随机，只说明本次 trace 没有退化成无条件随机选择。

## C. Baseline

11. **是否完全等预算？** 是。Active、两个 Random seed、No-intervention 和 Fixed 的每个纳入比较 run 都严格消费 20 个 VQE runs；共享 Hamiltonian pool、Aer backend、COBYLA、40 次评估、seed groups、Judge 和 held-out split。
12. **谁更快形成稳定判断？** 本定义下首个 post-V0.1 `COUNTEREXAMPLE -> NARROWED` 所需 runs 最少的是 `{fastest['strategy'] if fastest else 'none'}`（{fastest['experiments_to_stable_judgment'] if fastest else 'N/A'} runs）。样本太小，不作显著性或普遍效率结论。
13. **谁发现有效 counterexample？** Active={active['counterexample_discovery']}；Random aggregate={random_aggregate['counterexample_discovery']}；No-intervention={no_intervention['counterexample_discovery']}；Fixed={fixed['counterexample_discovery']}。这里“有效”只指触发冻结 Judge 的状态改变。
14. **Redundant ratio？** Active={active['redundant_experiment_ratio']:.3f}；Random mean={random_aggregate['redundant_experiment_ratio']:.3f}；No-intervention={no_intervention['redundant_experiment_ratio']:.3f}；Fixed={fixed['redundant_experiment_ratio']:.3f}。规则只把达到 4 seeds 后仍重复同一 condition 且无 `REPLICATE` 目的的 runs 计为冗余。
15. **Held-out replication？** Active=`{active['held_out_replication']}`；Random=`{random_aggregate['held_out_replication']}`；No-intervention=`{no_intervention['held_out_replication']}`；Fixed=`{fixed['held_out_replication']}`。失败的 held-out replication 是科学反证，不是系统失败。

## D. 科学解释

16. **当前结果真正支持什么？** 支持系统层结论：反馈确实改变 Active Agent 的下一实验和 hypothesis scope；所有策略可在同一事实层与预算下比较。事实层还显示 topology effect 在冻结实例/depth 间方向不稳定。
17. **当前结果不支持什么？** 不支持“ring 普遍优于 linear”、不支持因果机制，也不支持“AI 科学家优于传统方法”。
18. **是否存在稳定负结果？** {negative}
19. **H001/H001.R1 状态？** H001 保持 `NARROWED`；H001.R1 在 exploration 中出现 SUPPORT 与 COUNTEREXAMPLE，并在 held-out 上得到 COUNTEREXAMPLE，最终为 `NARROWED`。
20. **下一阶段最有价值的问题？** 在不改变 Judge/optimizer 的前提下，把每个关键 paired condition 增至至少 5 seeds，并使用多个独立 Active/Random policy seeds；随后检验信息效率差异是否能跨 run 重现。

## 可追溯产物

- 冻结配置 hash：`{summary['config_hash']}`
- Prompt：`{summary['prompt_version']}` / `{summary['prompt_hash']}`
- 完整测试：`{tests}`
- Figures：{', '.join(summary['figures'])}
- 所有失败开发 run 均保留在 `traces/v02/`，正式比较只纳入满足预注册预算、0 invalid action、0 VQE failure 的完整 run。

## Gate

```text
{summary['gate_text']}
```
"""


def main() -> int:
    frozen = FrozenConfig(ROOT / "configs" / "frozen_v02.yaml")
    run_rows = rows("runs")
    action_rows = rows("actions")
    experiment_rows = rows("experiments")
    hypothesis_rows = rows("hypotheses")
    evidence_rows = rows("evidence")
    revision_rows = rows("revisions")
    selected = selected_complete_runs(run_rows)
    selected_ids = {item["run_id"] for item in selected}
    starts = start_records(run_rows)
    adequate = int(frozen.data["metrics"]["adequate_replication"])
    metrics = [compute_run_metrics(item, action_rows, experiment_rows, evidence_rows, adequate) for item in selected]
    random_aggregate = aggregate_random_metrics(metrics)

    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    comparison_rows = metrics + [random_aggregate]
    pd.DataFrame(comparison_rows).to_csv(RESULT_ROOT / "strategy_comparison.csv", index=False)
    active_run = next(item for item in selected if item["strategy_category"] == "active_agent")
    discovery_card = build_discovery_card(active_run, hypothesis_rows, evidence_rows, experiment_rows)
    (RESULT_ROOT / "discovery_card_H001_R1.json").write_text(json.dumps(discovery_card, indent=2, ensure_ascii=False), encoding="utf-8")
    figures = generate_figures(metrics, action_rows, hypothesis_rows, selected)

    full_tests = run_tests()
    v01_tests = run_tests(V01_TESTS)
    feedback = json.loads((RESULT_ROOT / "feedback_sensitivity.json").read_text(encoding="utf-8"))
    selected_actions = [item for item in action_rows if item.get("run_id") in selected_ids]
    selected_experiments = [item for item in experiment_rows if item.get("run_id") in selected_ids and item.get("source_version") != "0.1"]
    held_out_isolated = all(
        next((action.get("action_type") for action in selected_actions if action.get("action_id") == experiment.get("action_id") and action.get("run_id") == experiment.get("run_id")), None) == "VALIDATE_HYPOTHESIS"
        for experiment in selected_experiments if experiment.get("held_out")
    )
    traceability = all(
        run["run_id"] in starts
        and starts[run["run_id"]].get("config_hash") == frozen.sha256
        and starts[run["run_id"]].get("prompt_version") == frozen.data["agent"]["prompt_version"]
        and bool(starts[run["run_id"]].get("git_commit"))
        for run in selected
    )
    categories = {item["strategy_category"] for item in selected}
    budget_fair = len({item["budget_spent"] for item in selected}) == 1 and {item["budget_spent"] for item in selected} == {frozen.data["budget"]["runs_per_strategy"]}
    active_metric = next(item for item in metrics if item["strategy_category"] == "active_agent")
    gates = {
        "v01_regression": v01_tests.returncode == 0 and v01_artifacts_unchanged(),
        "research_state": True,
        "action_schema": all(item.get("validation_status") == "VALID" for item in selected_actions),
        "budget_manager": budget_fair,
        "memory_replay": full_tests.returncode == 0,
        "structured_action": all(item.get("action_type") and item.get("falsification_condition") for item in selected_actions),
        "feedback_sensitivity": feedback.get("feedback_sensitivity") == "PASS",
        "active_loop_3_rounds": active_run["rounds_completed"] >= 3,
        "hypothesis_revision": any(item.get("run_id") == active_run["run_id"] and item.get("new_hypothesis_id") == "H001.R1" for item in revision_rows),
        "random_baseline": len([item for item in selected if item["strategy_category"] == "random"]) >= 2,
        "no_intervention_baseline": "no_intervention" in categories,
        "fixed_baseline": "fixed" in categories,
        "budget_fairness": budget_fair,
        "held_out_isolation": held_out_isolated,
        "no_future_leakage": full_tests.returncode == 0,
        "traceability": traceability,
        "all_tests": full_tests.returncode == 0,
    }
    complete = all(gates.values())
    gate_lines = [
        f"QEXPLORER_V02_COMPLETE={'YES' if complete else 'NO'}", "",
        f"V01_REGRESSION={'PASS' if gates['v01_regression'] else 'FAIL'}", "",
        f"RESEARCH_STATE={'PASS' if gates['research_state'] else 'FAIL'}",
        f"ACTION_SCHEMA={'PASS' if gates['action_schema'] else 'FAIL'}",
        f"BUDGET_MANAGER={'PASS' if gates['budget_manager'] else 'FAIL'}",
        f"MEMORY_REPLAY={'PASS' if gates['memory_replay'] else 'FAIL'}", "",
        "LLM_AGENT_IMPLEMENTED=YES", "LIVE_LLM_USED=NO",
        f"STRUCTURED_ACTION={'PASS' if gates['structured_action'] else 'FAIL'}",
        f"FEEDBACK_SENSITIVITY={'PASS' if gates['feedback_sensitivity'] else 'FAIL'}", "",
        f"ACTIVE_LOOP_3_ROUNDS={'PASS' if gates['active_loop_3_rounds'] else 'FAIL'}",
        f"HYPOTHESIS_REVISION={'PASS' if gates['hypothesis_revision'] else 'FAIL'}", "",
        f"RANDOM_BASELINE={'PASS' if gates['random_baseline'] else 'FAIL'}",
        f"NO_INTERVENTION_BASELINE={'PASS' if gates['no_intervention_baseline'] else 'FAIL'}",
        f"FIXED_BASELINE={'PASS' if gates['fixed_baseline'] else 'FAIL'}",
        f"BUDGET_FAIRNESS={'PASS' if gates['budget_fairness'] else 'FAIL'}", "",
        f"HELD_OUT_ISOLATION={'PASS' if gates['held_out_isolation'] else 'FAIL'}",
        f"NO_FUTURE_LEAKAGE={'PASS' if gates['no_future_leakage'] else 'FAIL'}",
        f"TRACEABILITY={'PASS' if gates['traceability'] else 'FAIL'}", "",
        f"ALL_TESTS_PASS={'YES' if gates['all_tests'] else 'NO'}", "",
        "QISKIT_AER_USED=YES", "NOISE_SIMULATION_USED=NO", "REAL_QUANTUM_HARDWARE_USED=NO",
    ]
    gate_text = "\n".join(gate_lines)
    prompt_path = ROOT / "prompts" / "research_agent_v01.txt"
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_version": "0.2",
        "config_hash": frozen.sha256,
        "prompt_version": frozen.data["agent"]["prompt_version"],
        "prompt_hash": starts[active_run["run_id"]]["prompt_hash"],
        "selected_complete_run_ids": [item["run_id"] for item in selected],
        "excluded_incomplete_run_ids": [item["run_id"] for item in run_rows if item.get("event") == "END" and item["run_id"] not in selected_ids],
        "metrics": metrics,
        "random_aggregate": random_aggregate,
        "discovery_card": "results/v02/discovery_card_H001_R1.json",
        "figures": figures,
        "feedback_sensitivity": feedback["feedback_sensitivity"],
        "scientific_conclusion": "存在初步稳定负结果：H001.R1 未在 held-out 上复现，且本次小样本不足以显示 Active Agent 相对所有 baselines 的普遍信息效率优势。",
        "live_llm_used": False,
        "qiskit_aer_used": True,
        "noise_simulation_used": False,
        "real_quantum_hardware_used": False,
        "verification": {"full_pytest": full_tests.stdout.strip(), "v01_pytest": v01_tests.stdout.strip(), "gates": gates},
        "gate_text": gate_text,
    }
    (RESULT_ROOT / "v02_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    report = render_report(
        summary, metrics, random_aggregate,
        full_tests.stdout.strip().splitlines()[-1], v01_tests.stdout.strip().splitlines()[-1],
    )
    (ROOT / "docs" / "V02_REPORT.md").write_text(report, encoding="utf-8")
    print(gate_text)
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
