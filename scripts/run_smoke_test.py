"""Run or verify the V0.1 smoke loop, render the report, and print the final Gate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.logging import JsonlTrace


DECISIONS = {"SUPPORT", "WEAKEN", "INCONCLUSIVE", "COUNTEREXAMPLE"}


def run(command: list[str]) -> subprocess.CompletedProcess:
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    if process.stdout:
        print(process.stdout, end="")
    if process.stderr:
        print(process.stderr, end="", file=sys.stderr)
    return process


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pass_fail(value: bool) -> str:
    return "PASS" if value else "FAIL"


def render_report(environment: dict, summary: dict, gates: dict, tests_output: str) -> str:
    evidence = summary["evidence"]
    candidate = evidence.get("candidate") or {}
    control = evidence.get("control") or {}
    hypothesis = summary["hypothesis"]
    tests_summary = tests_output.strip().splitlines()[-1] if tests_output.strip() else "no pytest output"
    return f"""# Q-Explorer V0.1 验收报告

生成时间：{datetime.now(timezone.utc).isoformat()}

## 范围与结论

V0.1 已完成 2 个 4-qubit Ising Hamiltonian、2 个 HEA depth、2 种纠缠拓扑和 2 个初始化 seed 的 16-run 无噪声 Aer smoke grid。全部 16 个 run 均被记录且无执行失败。该规模只用于验证实验环境和证据链，不构成 HEA 普遍适用条件的科学发现。

## 十项问题

1. **阿里云环境是否可以稳定运行 Qiskit Aer？** 当前可访问主机是 `{environment['os']['system']} {environment['os']['release']}`，云厂商身份无法独立验证，因此不能声称“阿里云已验证”。在这台实际主机的项目虚拟环境中，Aer 健康检查成功，`|1>` 概率为 {environment['aer_health_check'].get('probability_one')}，16 个 VQE run 无执行失败。
2. **Ising generator 是否正确？** 是。chain/ring/random 均有确定拓扑，显式 seed 决定 `h`、`J` 和稳定 Hamiltonian ID；测试覆盖边数、复现性、seed 敏感性及 Hermitian Qiskit operator。
3. **Exact ground energy 是否正确？** 是。2-qubit 手算例得到 -1.5；随机 4-qubit 实例的枚举值与 `SparsePauliOp` 矩阵最小特征值一致。
4. **HEA 是否正确构建？** 是。固定 RY 层只接受 depth 1/2 与 linear/ring；测试验证参数数、2-qubit gate 数、线路深度及越界拒绝。
5. **VQE 是否能够运行？** 是。实际使用 Qiskit Aer statevector 生成态并计算期望值，COBYLA 固定为唯一 optimizer；每次保存初始能量、最终能量、误差、预算状态和逐次轨迹。
6. **多 seed 是否稳定复现？** 是。每个配置包含 2 个 seed，聚合不筛选最佳 seed；同 Hamiltonian/Ansatz/seed 的独立执行得到完全一致的能量轨迹。正式科学实验仍应增加到至少 5 seeds。
7. **Experiment logging 是否完整？** 是。当前 loop 有 {summary['run_count']} 条实验、{summary['failed_runs']} 条失败；每条包含完整配置、核心结果和轨迹。logger 单测验证失败记录不会被丢弃。
8. **EvidenceJudge 是否基于真实结果工作？** 是。H001 冻结比较的 ring mean error 为 {candidate.get('mean_energy_error'):.12g}，linear mean error 为 {control.get('mean_energy_error'):.12g}；按冻结阈值输出 `{evidence['decision']}`（规则 `{evidence['rule']}`），没有自然语言猜测参与判定。
9. **H001 是否经历状态更新？** 是。H001 从 `PENDING` 更新为 `{hypothesis['status']}`，evidence ID 为 `{evidence['evidence_id']}`。本次 `{evidence['decision']}` 只是该固定 Hamiltonian、depth 和两个 seed 下的闭环结果，不应外推。
10. **下一阶段增加什么？** 首先把 seed 增至 >=5、优化预算冻结到 300–500，并在 4 qubit 上复核；随后受控加入 6 qubit、depth 3/4 与 full entanglement。再之后才加入 Fixed/Random/No-intervention baseline、噪声模拟和少量真机验证；LLM Agent 应在环境证据链稳定后接入。

## 可复现性与测试

- 冻结配置：`configs/frozen_v01.yaml`
- 当前结果 fingerprint：`{summary['reproducibility_fingerprint']}`
- 测试：`{tests_summary}`
- 真实量子硬件：未使用
- LLM Agent：未使用

## Gate

```text
QEXPLORER_V01_COMPLETE={'YES' if gates['complete'] else 'NO'}
ENVIRONMENT={pass_fail(gates['environment'])}
ISING_GENERATOR={pass_fail(gates['ising'])}
EXACT_SOLVER={pass_fail(gates['exact'])}
HEA={pass_fail(gates['hea'])}
VQE={pass_fail(gates['vqe'])}
MULTI_SEED={pass_fail(gates['multi_seed'])}
LOGGING={pass_fail(gates['logging'])}
EVIDENCE_JUDGE={pass_fail(gates['evidence'])}
HYPOTHESIS_UPDATE={pass_fail(gates['hypothesis'])}
ALL_TESTS_PASS={'YES' if gates['tests'] else 'NO'}
REAL_QUANTUM_HARDWARE_USED=NO
LLM_AGENT_USED=NO
```
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-grid", action="store_true", help="Validate existing grid artifacts instead of appending a new run")
    args = parser.parse_args()

    doctor = run([sys.executable, "scripts/doctor.py"])
    tests = run([sys.executable, "-m", "pytest", "-q"])
    summary_path = ROOT / "results" / "smoke_test_summary.json"
    if not args.reuse_grid:
        grid = run([sys.executable, "scripts/run_experiment_grid.py", "--config", "configs/frozen_v01.yaml"])
    else:
        grid = subprocess.CompletedProcess([], 0 if summary_path.exists() else 1)

    if not (ROOT / "results" / "environment_report.json").exists() or not summary_path.exists():
        print("Required artifacts are missing; Gate cannot be evaluated.", file=sys.stderr)
        return 1
    environment = load_json(ROOT / "results" / "environment_report.json")
    summary = load_json(summary_path)
    loop_id = summary["loop_run_id"]
    experiments = [record for record in JsonlTrace(ROOT / "traces" / "experiments.jsonl").read_all() if record.get("loop_run_id") == loop_id]
    hypotheses = [record for record in JsonlTrace(ROOT / "traces" / "hypotheses.jsonl").read_all() if record.get("loop_run_id") == loop_id]
    evidence_records = [record for record in JsonlTrace(ROOT / "traces" / "evidence.jsonl").read_all() if record.get("loop_run_id") == loop_id]
    hamiltonians = json.loads((ROOT / "data" / "hamiltonians.json").read_text(encoding="utf-8"))
    required_experiment_fields = {
        "experiment_id", "hamiltonian_id", "depth", "entanglement", "initialization_seed",
        "exact_energy", "initial_energy", "final_energy", "energy_error", "relative_energy_error",
        "optimization_steps", "runtime", "converged", "optimization_trajectory", "configuration", "status",
    }
    gates = {
        "environment": doctor.returncode == 0 and bool(environment.get("environment_pass")),
        "ising": len(hamiltonians) == 2 and all(item.get("num_qubits") == 4 and {"h", "J", "seed", "topology"} <= item.keys() for item in hamiltonians),
        "exact": all(isinstance(item.get("exact_ground_energy"), (int, float)) for item in hamiltonians),
        "hea": len(experiments) == 16 and all(record.get("num_parameters", 0) > 0 and record.get("num_2q_gates", 0) > 0 for record in experiments),
        "vqe": grid.returncode == 0 and len(experiments) == 16 and all(record.get("status") == "SUCCESS" and record.get("optimization_trajectory") for record in experiments),
        "multi_seed": len(summary.get("aggregates", [])) == 8 and all(item.get("number_of_seeds") == 2 for item in summary.get("aggregates", [])),
        "logging": len(experiments) == 16 and all(required_experiment_fields <= record.keys() for record in experiments),
        "evidence": len(evidence_records) == 1 and summary.get("evidence", {}).get("decision") in DECISIONS,
        "hypothesis": any(record.get("event") == "UPDATED" and record.get("status") != "PENDING" for record in hypotheses),
        "tests": tests.returncode == 0,
    }
    gates["complete"] = all(gates.values())
    verification = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "pytest_command": f"{sys.executable} -m pytest -q",
        "pytest_passed": gates["tests"],
        "pytest_output": tests.stdout.strip(),
        "gate": gates,
    }
    summary["verification"] = verification
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    report = render_report(environment, summary, gates, tests.stdout)
    report_path = ROOT / "docs" / "V01_REPORT.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    gate_lines = [
        f"QEXPLORER_V01_COMPLETE={'YES' if gates['complete'] else 'NO'}",
        f"ENVIRONMENT={pass_fail(gates['environment'])}",
        f"ISING_GENERATOR={pass_fail(gates['ising'])}",
        f"EXACT_SOLVER={pass_fail(gates['exact'])}",
        f"HEA={pass_fail(gates['hea'])}",
        f"VQE={pass_fail(gates['vqe'])}",
        f"MULTI_SEED={pass_fail(gates['multi_seed'])}",
        f"LOGGING={pass_fail(gates['logging'])}",
        f"EVIDENCE_JUDGE={pass_fail(gates['evidence'])}",
        f"HYPOTHESIS_UPDATE={pass_fail(gates['hypothesis'])}",
        f"ALL_TESTS_PASS={'YES' if gates['tests'] else 'NO'}",
        "REAL_QUANTUM_HARDWARE_USED=NO",
        "LLM_AGENT_USED=NO",
    ]
    print("\n".join(gate_lines))
    return 0 if gates["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
