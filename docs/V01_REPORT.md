# Q-Explorer V0.1 验收报告

生成时间：2026-08-12T12:13:17.220491+00:00

## 范围与结论

V0.1 已完成 2 个 4-qubit Ising Hamiltonian、2 个 HEA depth、2 种纠缠拓扑和 2 个初始化 seed 的 16-run 无噪声 Aer smoke grid。全部 16 个 run 均被记录且无执行失败。该规模只用于验证实验环境和证据链，不构成 HEA 普遍适用条件的科学发现。

## 十项问题

1. **阿里云环境是否可以稳定运行 Qiskit Aer？** 当前可访问主机是 `Windows 10`，云厂商身份无法独立验证，因此不能声称“阿里云已验证”。在这台实际主机的项目虚拟环境中，Aer 健康检查成功，`|1>` 概率为 1.0，16 个 VQE run 无执行失败。
2. **Ising generator 是否正确？** 是。chain/ring/random 均有确定拓扑，显式 seed 决定 `h`、`J` 和稳定 Hamiltonian ID；测试覆盖边数、复现性、seed 敏感性及 Hermitian Qiskit operator。
3. **Exact ground energy 是否正确？** 是。2-qubit 手算例得到 -1.5；随机 4-qubit 实例的枚举值与 `SparsePauliOp` 矩阵最小特征值一致。
4. **HEA 是否正确构建？** 是。固定 RY 层只接受 depth 1/2 与 linear/ring；测试验证参数数、2-qubit gate 数、线路深度及越界拒绝。
5. **VQE 是否能够运行？** 是。实际使用 Qiskit Aer statevector 生成态并计算期望值，COBYLA 固定为唯一 optimizer；每次保存初始能量、最终能量、误差、预算状态和逐次轨迹。
6. **多 seed 是否稳定复现？** 是。每个配置包含 2 个 seed，聚合不筛选最佳 seed；同 Hamiltonian/Ansatz/seed 的独立执行得到完全一致的能量轨迹。正式科学实验仍应增加到至少 5 seeds。
7. **Experiment logging 是否完整？** 是。当前 loop 有 16 条实验、0 条失败；每条包含完整配置、核心结果和轨迹。logger 单测验证失败记录不会被丢弃。
8. **EvidenceJudge 是否基于真实结果工作？** 是。H001 冻结比较的 ring mean error 为 1.43095721221，linear mean error 为 0.00325141949652；按冻结阈值输出 `COUNTEREXAMPLE`（规则 `relative_worsening_threshold`），没有自然语言猜测参与判定。
9. **H001 是否经历状态更新？** 是。H001 从 `PENDING` 更新为 `NARROWED`，evidence ID 为 `EVID_000001`。本次 `COUNTEREXAMPLE` 只是该固定 Hamiltonian、depth 和两个 seed 下的闭环结果，不应外推。
10. **下一阶段增加什么？** 首先把 seed 增至 >=5、优化预算冻结到 300–500，并在 4 qubit 上复核；随后受控加入 6 qubit、depth 3/4 与 full entanglement。再之后才加入 Fixed/Random/No-intervention baseline、噪声模拟和少量真机验证；LLM Agent 应在环境证据链稳定后接入。

## 可复现性与测试

- 冻结配置：`configs/frozen_v01.yaml`
- 当前结果 fingerprint：`9f12bcc4795769cf17f1ebc97795dc9ba833792d38b2e6195a7a6f4826676f6b`
- 测试：`23 passed in 1.81s`
- 真实量子硬件：未使用
- LLM Agent：未使用

## Gate

```text
QEXPLORER_V01_COMPLETE=YES
ENVIRONMENT=PASS
ISING_GENERATOR=PASS
EXACT_SOLVER=PASS
HEA=PASS
VQE=PASS
MULTI_SEED=PASS
LOGGING=PASS
EVIDENCE_JUDGE=PASS
HYPOTHESIS_UPDATE=PASS
ALL_TESTS_PASS=YES
REAL_QUANTUM_HARDWARE_USED=NO
LLM_AGENT_USED=NO
```
