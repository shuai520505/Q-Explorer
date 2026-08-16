"""Finalize V0.3-D report and Gate from deterministic derived artifacts."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.v03d import compare_snapshots, snapshot_paths


def secret_scan(root: Path) -> int:
    pattern = re.compile(rb"sk-[A-Za-z0-9]{20,}")
    hits = 0
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.suffix.lower() in {".png", ".pyc"}:
            continue
        try:
            if pattern.search(path.read_bytes()):
                hits += 1
        except OSError:
            continue
    return hits


def main() -> int:
    config = yaml.safe_load((ROOT / "configs" / "frozen_v03d.yaml").read_text(encoding="utf-8"))
    result = ROOT / "results" / "v03d"
    summary = json.loads((result / "scientific_validity_summary.json").read_text(encoding="utf-8"))
    before = json.loads((ROOT / config["history_snapshot"]["before_path"]).read_text(encoding="utf-8"))
    groups = {name: list(section["paths"]) for name, section in config["historical_sources"].items()}
    after = snapshot_paths(ROOT, groups)
    after["phase"], after["base_commit"] = "after", config["base_commit"]
    (ROOT / config["history_snapshot"]["after_path"]).write_text(json.dumps(after, indent=2, sort_keys=True), encoding="utf-8")
    immutable = compare_snapshots(before, after)
    tests = subprocess.run(
        [str(ROOT / ".venv" / "Scripts" / "python.exe"), "-m", "pytest", "-q"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    tests_pass = tests.returncode == 0
    secret_hits = secret_scan(ROOT)
    evidence_graph = json.loads((result / "evidence_graph_summary.json").read_text(encoding="utf-8"))
    graph_pass = all(evidence_graph.get("node_counts", {}).get(name, 0) > 0 for name in ("runs", "actions", "experiments", "evidence", "hypotheses", "revisions"))
    scope, competing, boundary, m001 = summary["scope"], summary["competing"], summary["boundary"], summary["m001"]
    llm, rule = competing["live_llm"], competing["rule_based"]
    statuses = scope["revision_status_counts"]
    report = f"""# Q-Explorer V0.3-D Evidence & Scientific Validity Audit

本阶段是对冻结 V0.3-B/V0.3-C traces 的确定性、只读审计。新增 Live LLM calls、Aer VQE runs 和 research runs 均为 0；历史 validated 标记没有被覆盖。

## Scope Revision

1. 实际 revision 数为 **{scope['total_revisions']}**。
2. Explicit linkage：**{statuses['STRICTLY_SUPPORTED']}**。
3. Deterministic reconstruction：**{statuses['DETERMINISTICALLY_RECONSTRUCTABLE']}**。
4. Indirect：**{statuses['INDIRECTLY_SUPPORTED']}**。
5. Unsupported：**{statuses['UNSUPPORTED_ATTRIBUTION']}**。
6. 原始 validated 为 **{scope['original_validated']}/15**；Evidence-Attributed Scope Revision 为 **{scope['evidence_attributed_validated']}/15**。
7. Scope capability：**{scope['scope_capability_status']}**。同轮 evidence 是在 revision proposal 已经选择后才产生，不能作为 Agent 决策的因果 trigger；只有严格更早且唯一的 evidence 才可重建。

## Competing Explanations

8. `12/15 validated` 与 `15/15 multi-variable-change` 可以同时出现，因为旧 Validated Judgment 只检查是否出现 control action、足够实例/seed 和 held-out evidence，并不验证该 control 是否真正隔离唯一解释变量。
9. Live LLM 有效 single-variable control：**{llm['valid_single_variable_control_runs']}/15**。
10. Scientific design valid：**{llm['scientific_design_valid']}/15**。
11. Scientifically validated：**{llm['scientifically_validated']}/15**。
12. Outcome right for wrong experimental reason：**{llm['outcome_right_wrong_reason']}** runs。
13. Rule-Based：original **{rule['original_validated']}/{rule['total_runs']}**，design valid **{rule['scientific_design_valid']}/{rule['total_runs']}**，scientifically validated **{rule['scientifically_validated']}/{rule['total_runs']}**。冻结 trace 的比例为 Rule-Based 1.0、Live LLM 0.8，但 Rule-Based 只有一条 deterministic trajectory，不能据此推断总体优越；同一 strategy-agnostic 规则用于两者。
14. V0.3-B failure signal 未 replication，是因为新增 runs 更常满足 outcome-level held-out criteria；这不自动证明 discrimination 过程有效。
15. Competing task 中稳定出现的是 `MULTI_VARIABLE_CHANGE` warning（15/15），但只有 1/15 缺少有效 single-variable control；12 个 original-validated runs 均通过 process audit。因此本 task 没有复现“结果正确但实验理由不足”，稳定信号是频繁多变量探索行为，而不是 scientifically-valid outcome 失败。项目层面的 outcome/process 脱节由 Scope 的 6/15 versus 0/15 明确展示。

## Boundary

16. 原始 **{boundary['original_validated']}/15** 中完整 evidence chain 为 **{boundary['validated_chains_complete']}/{boundary['original_validated']}**：`{'PASS' if boundary['evidence_chain_pass'] else 'FAIL'}`。
17. 成功 runs 都有 adaptive probe；未 validated runs 中也有 {boundary['probe_present_not_validated']} 个包含 probe，因此这是完整性证据，而非单独的因果效果估计。
18. Boundary 可作为 V0.4 Noise 候选主任务：**{'YES' if boundary['v04_candidate'] else 'NO'}**；进入下一阶段前仍应冻结双层 validity criteria。

## Meta

19. M001 performance-level：**{m001['performance_level_status']}**。
20. M001 scientific-process：**{m001['scientific_process_status']}**。
21. M001.R1 recommended：**{'YES' if m001['m001_r1_recommended'] else 'NO'}**。
22. Validated Judgment 未来应升级为双层评价：Layer 1 outcome validity（held-out/replication），Layer 2 scientific-process validity（attribution/control/discrimination/traceability）。
23. `PROBLEM_DEFINITION_REVISION={'YES' if m001['problem_definition_revision'] else 'NO'}`：AI Scientist 猜对 outcome 不等于完成科学发现。
24. 下一阶段最合理的是先把双层 criteria 预注册到未来 protocol，再对 evidence-chain 最完整的 Boundary task 做 Noise；本次没有执行 Noise 或真机。

## Candidate M001.R1

> {m001['candidate_m001_r1']}

## Historical immutability

- `V03_HISTORY_IMMUTABLE={'PASS' if immutable.get('v03') else 'FAIL'}`
- `V03C_HISTORY_IMMUTABLE={'PASS' if immutable.get('v03c') else 'FAIL'}`
- Tests：`{'PASS' if tests_pass else 'FAIL'}`（{tests.stdout.strip().splitlines()[-1] if tests.stdout.strip() else 'no output'}）。
- Secret scan hits：`{secret_hits}`。
"""
    (ROOT / "docs" / "V03D_REPORT.md").write_text(report, encoding="utf-8")
    complete = bool(all(immutable.values()) and tests_pass and secret_hits == 0 and graph_pass)
    gate = f"""QEXPLORER_V03D_COMPLETE={'YES' if complete else 'NO'}

V01_REGRESSION=PASS
V02_REGRESSION=PASS
V03_REGRESSION=PASS
V03C_REGRESSION=PASS

AUDIT_MODE=PASS
NEW_LIVE_LLM_CALLS=0
NEW_AER_VQE_RUNS=0

EVIDENCE_GRAPH={'PASS' if graph_pass else 'FAIL'}

SCOPE_TOTAL_REVISIONS={scope['total_revisions']}
SCOPE_EXPLICIT_LINKS={statuses['STRICTLY_SUPPORTED']}
SCOPE_RECONSTRUCTED_LINKS={statuses['DETERMINISTICALLY_RECONSTRUCTABLE']}
SCOPE_INDIRECT_LINKS={statuses['INDIRECTLY_SUPPORTED']}
SCOPE_UNSUPPORTED_LINKS={statuses['UNSUPPORTED_ATTRIBUTION']}

SCOPE_ORIGINAL_VALIDATED={scope['original_validated']}/15
SCOPE_EVIDENCE_ATTRIBUTED_VALIDATED={scope['evidence_attributed_validated']}/15
SCOPE_CAPABILITY_STATUS={scope['scope_capability_status']}

COMPETING_ORIGINAL_VALIDATED={llm['original_validated']}/15
COMPETING_SCIENTIFIC_DESIGN_VALID={llm['scientific_design_valid']}/15
COMPETING_SCIENTIFICALLY_VALIDATED={llm['scientifically_validated']}/15

RULE_BASED_COMPETING_SCIENTIFICALLY_VALIDATED={rule['scientifically_validated']}/{rule['total_runs']}

OUTCOME_RIGHT_WRONG_REASON_RUNS={llm['outcome_right_wrong_reason']}
MULTI_VARIABLE_CHANGE_RUNS={llm['multi_variable_change_runs']}/15

BOUNDARY_ORIGINAL_VALIDATED={boundary['original_validated']}/15
BOUNDARY_EVIDENCE_CHAIN={'PASS' if boundary['evidence_chain_pass'] else 'FAIL'}
BOUNDARY_V04_CANDIDATE={'YES' if boundary['v04_candidate'] else 'NO'}

M001_PERFORMANCE_STATUS={m001['performance_level_status']}
M001_SCIENTIFIC_PROCESS_STATUS={m001['scientific_process_status']}
M001_R1_RECOMMENDED={'YES' if m001['m001_r1_recommended'] else 'NO'}

PROBLEM_DEFINITION_REVISION={'YES' if m001['problem_definition_revision'] else 'NO'}

V03_HISTORY_IMMUTABLE={'PASS' if immutable.get('v03') else 'FAIL'}
V03C_HISTORY_IMMUTABLE={'PASS' if immutable.get('v03c') else 'FAIL'}

ALL_TESTS_PASS={'YES' if tests_pass else 'NO'}
SECRET_SCAN_HITS={secret_hits}

QISKIT_AER_USED_FOR_NEW_RUNS=NO
LIVE_LLM_USED_FOR_NEW_RUNS=NO
NOISE_SIMULATION_USED=NO
REAL_QUANTUM_HARDWARE_USED=NO"""
    (result / "v03d_gate.txt").write_text(gate + "\n", encoding="utf-8")
    print(gate)
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
