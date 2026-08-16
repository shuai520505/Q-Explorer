# Q-Explorer V0.3-C Targeted Replication Report

生成时间：2026-08-13T11:53:57.079354+00:00

本报告是 V0.3-B 的独立 replication 记录；未修改 `docs/V03_REPORT.md` 或任何 V0.3 原始结果。

## Reproducibility

1. **冻结了哪些配置？** 科学 config、8-task suite、三个目标 task、DeepSeek live config、prompt、Judge、VQE、每 run 16-run budget、existing seeds 301–303、new seeds 304–315；protocol hash `e2e1337cfe6e544d339a0a37c972e96a06c65bfc474f8ad7f6b14054209bab57`，预注册 commit `3cbbdf8`。
2. **Prompt hash 一致？** PASS。实际正式 prompt 是 `prompts/research_agent_v03_deepseek_v01.txt`，hash `530641052769c78fd36905fe2ecdffe6b44280657964b0493fbbcf6c1e0ac4af`；提示中写的旧文件名不是 V0.3-B 正式 trace 所用 prompt。
3. **Model 一致？** PASS：`deepseek-v4-flash`，OpenAI-compatible DeepSeek，`thinking_mode=false`，temperature=0.1。
4. **Evidence Judge 一致？** PASS，Judge section hash `55b89131cea4d7f6e1d63f87188379c003456e9fd83056cdd7f79b1e41123746`。
5. **Task 一致？** PASS：只运行原 `TASK_F01`、`TASK_G01`、`TASK_D01`，task suite hash 未变。
6. **Budget 一致？** PASS：每 run 分配 16；36 个新增 runs 分配 576，实际 552。3 个 invalid runs 提前停止，没有补预算。

## Boundary

7. **最终 validated？** `8/15`，rate=0.533。
8. **95% CI？** Wilson `[0.301, 0.752]`。
9. **成功是否伴随 adaptive boundary probe？** 是，8/8 validated runs 同时包含 BOUNDARY_PROBE、至少两个 exploration depths、evidence label 变化和 held-out validation；但 hypothesis revisions=0，因此不能声称完成了“revision”步骤。
10. **其他策略？** V0.3-B 冻结结果中 Rule-Based、Random、No-intervention、Fixed 在该 task 均为 0；Rule-Based 是 deterministic，未机械重复。
11. **原 2/3 是否复现？** `YES`，累计变为 8/15；point estimate 下降到 0.533，但仍得到稳定非零 capability。结论仅限当前冻结 Boundary task。

## Scope Revision

12. **最终 validated？** `6/15`，rate=0.400。
13. **95% CI？** Wilson `[0.198, 0.643]`。
14. **Revision 是否由 counterexample 触发？** 严格 trace provenance 下，valid revisions=0，invalid revisions=18。18 条 revision 的文本引用先前反例，但 `triggering_evidence_ids` 没有指向 COUNTEREXAMPLE label，因此不能算合法闭环证据。
15. **Scope creep？** 0 次 detector hit；没有 unsupported expansion，但 provenance 缺陷仍使 scope-revision 能力为 `INCONCLUSIVE`。
16. **原 1/3 是否复现？** validated-rate 的非零信号复现为 6/15；但不能把它升级为“稳定合法 scope revision”，因为严格 trigger linkage 未通过。

## Competing Explanations

17. **最终 validated？** `12/15`，rate=0.800，Wilson 95% CI `[0.548, 0.930]`。
18. **Rule-Based？** 原正式 deterministic run 为 1/1 validated；没有制造 15 个完全相同副本。
19. **最常见失败原因？** MULTI_VARIABLE_CHANGE=15/15，COUNTEREXAMPLE_IGNORED=15/15，INVALID_ACTION=3/15。虽然 12/15 validated，严格单变量控制的行为质量仍有问题。
20. **Rule-Based 优势稳定？** `NO/INCONCLUSIVE`：原 LLM 1/3 扩展为 12/15，早期高失败率没有复现。Rule-Based 数值仍为 1.0，但只有一个 deterministic trajectory，不能据此宣称稳定总体优势。

## Meta-hypothesis

21. **M001 当前状态？** `SUPPORTED_WITH_TASK_DEPENDENCE`。Boundary/Scope 对 static baselines 的非零差异与 simple-task 的无差异共同支持 task dependence。
22. **M001.R1？** 提出候选修订，但不是发现：

> Within the frozen Q-Explorer task suite, feedback-driven active policies add the clearest value in boundary localization and evidence-bounded scope revision; simple tasks need no intervention, and the replication does not establish a stable LLM disadvantage on predefined competing explanations.

23. **哪类任务适合 LLM？** 当前证据最清楚的是 boundary localization；scope task 有 validated capability，但 revision provenance 尚未通过。
24. **哪类任务适合 Rule-Based？** 需要强制、可审计的单变量 control 时透明规则仍更可靠；本轮不能证明其 validated rate 稳定高于 LLM，但 LLM 的 multi-variable diagnostic 支持保留这一工程偏好。
25. **哪类任务 No-intervention 足够？** 沿用 V0.3-B：Simple Falsification、Replication Needed、Local Counterexample、Stable Negative；本阶段没有重跑这些 task。

## Costs and retention

- Existing V0.3-B runs：9；new V0.3-C runs：36；merged unique：45，严格 15/task。
- New recorded token usage（lower bound）：`{'completion_tokens': 90530, 'prompt_cache_hit_tokens': 230912, 'prompt_cache_miss_tokens': 519364, 'prompt_tokens': 750276, 'total_tokens': 840806}`；API cost unavailable，未估算伪值。
- Invalid runs retained：5；replacement runs=0；provider transient errors=0。
- 新增 VQE：552/576，未使用部分来自 invalid early stop。

## Gate

```text
QEXPLORER_V03C_COMPLETE=YES

V01_REGRESSION=PASS
V02_REGRESSION=PASS
V03_REGRESSION=PASS

TARGET_TASKS_FROZEN=YES
PROMPT_HASH_MATCH=PASS
MODEL_CONFIG_MATCH=PASS
JUDGE_CONFIG_MATCH=PASS
BUDGET_CONFIG_MATCH=PASS

BOUNDARY_TOTAL_LLM_RUNS=15
BOUNDARY_VALIDATED=8/15
BOUNDARY_SIGNAL_REPLICATED=YES

SCOPE_TOTAL_LLM_RUNS=15
SCOPE_VALIDATED=6/15
SCOPE_SIGNAL_REPLICATED=YES

COMPETING_TOTAL_LLM_RUNS=15
COMPETING_VALIDATED=12/15
COMPETING_FAILURE_MODE_REPLICATED=NO

INVALID_RUNS_RETAINED=YES
NO_REPLACEMENT_RUNS=PASS
NO_EXTRA_BUDGET=PASS

CONFIDENCE_INTERVALS=AVAILABLE
FAILURE_MODE_ANALYSIS=PASS

M001_STATUS=SUPPORTED_WITH_TASK_DEPENDENCE
M001_REVISION_PROPOSED=YES

ALL_TESTS_PASS=YES

LIVE_LLM_USED=YES
MODEL=deepseek-v4-flash
THINKING_MODE=false

QISKIT_AER_USED=YES
NOISE_SIMULATION_USED=NO
REAL_QUANTUM_HARDWARE_USED=NO

SECRET_SCAN_HITS=0
```
