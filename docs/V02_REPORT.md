# Q-Explorer V0.2 验收报告

生成时间：2026-08-12T14:44:54.814042+00:00

## A. 系统

1. **V0.1 是否仍全部通过？** 是。原始 23 项 V0.1 测试仍通过（`23 passed in 2.44s`），冻结配置、raw results、traces 与报告相对 V0.1 基线提交未改变。
2. **ResearchState 是否可完整重建？** 是。状态由 append-only traces 按 `run_id` 和 `round <= N` 重建，包含 hypothesis、evidence、实验区域、统计、预算和历史 action；自动测试覆盖 round replay。
3. **Agent 是否输出结构化 Action？** 是。固定枚举 action type、严格字段、实验 spec、控制/改变变量、预期、证伪条件与信息目标均验证；未知/额外字段被拒绝。
4. **Budget 是否严格执行？** 是。每个正式比较 run 均消费 20 个 VQE runs；每条 action 记录 before/cost/after，超预算会抛出异常。
5. **是否存在未来信息泄漏？** 未发现。round cutoff 自动测试通过；held-out 结果仅由 `VALIDATE_HYPOTHESIS` action 执行后进入后续状态。

## B. Agent

6. **Agent 是否根据 SUPPORT / COUNTEREXAMPLE 改变行为？** 是。counterfactual test 仅替换 evidence label，Agent 分别选择 `BOUNDARY_PROBE` 与 `REVISE_HYPOTHESIS`，目标和理由均改变，结果为 `PASS`。
7. **是否连续完成至少 3 轮？** 是。完整 Active run `RUN_20260812_006` 连续完成 10 轮、20 个 VQE runs。
8. **是否发生 hypothesis revision？** 是。V0.1 的 H001 永久保留；round 1 由 EVID_000001 触发 `H001.R1`，scope 从普遍陈述缩小为 topology-and-depth conditional claim。
9. **是否出现 optimization drift？** 否。action 具有 hypothesis/control/falsification contract，未出现以最低 energy 为目标的措辞或选择模式。
10. **是否出现 random-search degeneration？** 自动规则未检出。Active 使用 5 类 action、覆盖 10 个条件，并对不同 evidence 采取不同目标；这不证明其优于随机，只说明本次 trace 没有退化成无条件随机选择。

## C. Baseline

11. **是否完全等预算？** 是。Active、两个 Random seed、No-intervention 和 Fixed 的每个纳入比较 run 都严格消费 20 个 VQE runs；共享 Hamiltonian pool、Aer backend、COBYLA、40 次评估、seed groups、Judge 和 held-out split。
12. **谁更快形成稳定判断？** 本定义下首个 post-V0.1 `COUNTEREXAMPLE -> NARROWED` 所需 runs 最少的是 `no_intervention`（2 runs）。样本太小，不作显著性或普遍效率结论。
13. **谁发现有效 counterexample？** Active=True；Random aggregate=True；No-intervention=True；Fixed=True。这里“有效”只指触发冻结 Judge 的状态改变。
14. **Redundant ratio？** Active=0.000；Random mean=0.000；No-intervention=0.000；Fixed=0.300。规则只把达到 4 seeds 后仍重复同一 condition 且无 `REPLICATE` 目的的 runs 计为冗余。
15. **Held-out replication？** Active=`COUNTEREXAMPLE`；Random=`CONSISTENT_COUNTEREXAMPLE`；No-intervention=`COUNTEREXAMPLE`；Fixed=`COUNTEREXAMPLE`。失败的 held-out replication 是科学反证，不是系统失败。

## D. 科学解释

16. **当前结果真正支持什么？** 支持系统层结论：反馈确实改变 Active Agent 的下一实验和 hypothesis scope；所有策略可在同一事实层与预算下比较。事实层还显示 topology effect 在冻结实例/depth 间方向不稳定。
17. **当前结果不支持什么？** 不支持“ring 普遍优于 linear”、不支持因果机制，也不支持“AI 科学家优于传统方法”。
18. **是否存在稳定负结果？** 存在初步稳定负结果：H001.R1 未在 held-out 上复现，且本次小样本不足以显示 Active Agent 相对所有 baselines 的普遍信息效率优势。
19. **H001/H001.R1 状态？** H001 保持 `NARROWED`；H001.R1 在 exploration 中出现 SUPPORT 与 COUNTEREXAMPLE，并在 held-out 上得到 COUNTEREXAMPLE，最终为 `NARROWED`。
20. **下一阶段最有价值的问题？** 在不改变 Judge/optimizer 的前提下，把每个关键 paired condition 增至至少 5 seeds，并使用多个独立 Active/Random policy seeds；随后检验信息效率差异是否能跨 run 重现。

## 可追溯产物

- 冻结配置 hash：`603366fc6ee4743563aa251461a0351dbb0713368eb0cf73ca6aebc44b8b612f`
- Prompt：`research_agent_v01` / `16228c07350f9c5cf4800ae0d61be00c92925a3ffc6c7bfba27382e59217cdb1`
- 完整测试：`45 passed in 2.78s`
- Figures：results\v02\figures\figure1_runs_to_judgment.png, results\v02\figures\figure2_experiment_space_coverage.png, results\v02\figures\figure3_hypothesis_timeline.png
- 所有失败开发 run 均保留在 `traces/v02/`，正式比较只纳入满足预注册预算、0 invalid action、0 VQE failure 的完整 run。

## Gate

```text
QEXPLORER_V02_COMPLETE=YES

V01_REGRESSION=PASS

RESEARCH_STATE=PASS
ACTION_SCHEMA=PASS
BUDGET_MANAGER=PASS
MEMORY_REPLAY=PASS

LLM_AGENT_IMPLEMENTED=YES
LIVE_LLM_USED=NO
STRUCTURED_ACTION=PASS
FEEDBACK_SENSITIVITY=PASS

ACTIVE_LOOP_3_ROUNDS=PASS
HYPOTHESIS_REVISION=PASS

RANDOM_BASELINE=PASS
NO_INTERVENTION_BASELINE=PASS
FIXED_BASELINE=PASS
BUDGET_FAIRNESS=PASS

HELD_OUT_ISOLATION=PASS
NO_FUTURE_LEAKAGE=PASS
TRACEABILITY=PASS

ALL_TESTS_PASS=YES

QISKIT_AER_USED=YES
NOISE_SIMULATION_USED=NO
REAL_QUANTUM_HARDWARE_USED=NO
```
