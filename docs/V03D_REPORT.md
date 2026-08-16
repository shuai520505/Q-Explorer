# Q-Explorer V0.3-D Evidence & Scientific Validity Audit

本阶段是对冻结 V0.3-B/V0.3-C traces 的确定性、只读审计。新增 Live LLM calls、Aer VQE runs 和 research runs 均为 0；历史 validated 标记没有被覆盖。

## Scope Revision

1. 实际 revision 数为 **18**。
2. Explicit linkage：**0**。
3. Deterministic reconstruction：**0**。
4. Indirect：**18**。
5. Unsupported：**0**。
6. 原始 validated 为 **6/15**；Evidence-Attributed Scope Revision 为 **0/15**。
7. Scope capability：**INCONCLUSIVE**。同轮 evidence 是在 revision proposal 已经选择后才产生，不能作为 Agent 决策的因果 trigger；只有严格更早且唯一的 evidence 才可重建。

## Competing Explanations

8. `12/15 validated` 与 `15/15 multi-variable-change` 可以同时出现，因为旧 Validated Judgment 只检查是否出现 control action、足够实例/seed 和 held-out evidence，并不验证该 control 是否真正隔离唯一解释变量。
9. Live LLM 有效 single-variable control：**14/15**。
10. Scientific design valid：**12/15**。
11. Scientifically validated：**12/15**。
12. Outcome right for wrong experimental reason：**0** runs。
13. Rule-Based：original **1/1**，design valid **1/1**，scientifically validated **1/1**。冻结 trace 的比例为 Rule-Based 1.0、Live LLM 0.8，但 Rule-Based 只有一条 deterministic trajectory，不能据此推断总体优越；同一 strategy-agnostic 规则用于两者。
14. V0.3-B failure signal 未 replication，是因为新增 runs 更常满足 outcome-level held-out criteria；这不自动证明 discrimination 过程有效。
15. Competing task 中稳定出现的是 `MULTI_VARIABLE_CHANGE` warning（15/15），但只有 1/15 缺少有效 single-variable control；12 个 original-validated runs 均通过 process audit。因此本 task 没有复现“结果正确但实验理由不足”，稳定信号是频繁多变量探索行为，而不是 scientifically-valid outcome 失败。项目层面的 outcome/process 脱节由 Scope 的 6/15 versus 0/15 明确展示。

## Boundary

16. 原始 **8/15** 中完整 evidence chain 为 **8/8**：`PASS`。
17. 成功 runs 都有 adaptive probe；未 validated runs 中也有 7 个包含 probe，因此这是完整性证据，而非单独的因果效果估计。
18. Boundary 可作为 V0.4 Noise 候选主任务：**YES**；进入下一阶段前仍应冻结双层 validity criteria。

## Meta

19. M001 performance-level：**SUPPORTED_WITH_TASK_DEPENDENCE**。
20. M001 scientific-process：**PARTIALLY_SUPPORTED**。
21. M001.R1 recommended：**YES**。
22. Validated Judgment 未来应升级为双层评价：Layer 1 outcome validity（held-out/replication），Layer 2 scientific-process validity（attribution/control/discrimination/traceability）。
23. `PROBLEM_DEFINITION_REVISION=YES`：AI Scientist 猜对 outcome 不等于完成科学发现。
24. 下一阶段最合理的是先把双层 criteria 预注册到未来 protocol，再对 evidence-chain 最完整的 Boundary task 做 Noise；本次没有执行 Noise 或真机。

## Candidate M001.R1

> LLM-based active scientific exploration shows task-dependent incremental value, with the clearest replicated evidence currently appearing in adaptive boundary localization. Performance on hypothesis scope revision and competing-explanation tasks must additionally be evaluated for evidence attribution and experimental-control validity, because successful held-out outcomes do not by themselves guarantee scientifically valid reasoning.

## Historical immutability

- `V03_HISTORY_IMMUTABLE=PASS`
- `V03C_HISTORY_IMMUTABLE=PASS`
- Tests：`PASS`（92 passed in 4.65s）。
- Secret scan hits：`0`。
