# Q-Explorer V0.3 报告

生成时间：2026-08-13T08:42:38.372968+00:00

## Environment

1. **V0.1/V0.2 regression？** 均 PASS；冻结结果与 traces 未覆盖。
2. **Task suite 如何设计？** 8 个冻结任务覆盖 simple falsification、replication、local counterexample、competing explanations、stable negative、boundary、scope revision、problem revision。
3. **是否预先冻结？** 是。Task suite hash `50c73a2e94a9be6b36ce093251257859d4c9fc37f45858745da4fb805d618713`；live config hash `75f807134a729a5d34b69164d37bad015744ef1144a928d84fae7d5cd3f42783`。
4. **Held-out 是否隔离？** 是。形成阶段不可见，只有末两轮 `VALIDATE_HYPOTHESIS` 能访问条件，结果仍由 EvidenceJudge 生成。

## Live LLM Experiment

5. **是否真实调用 live LLM？** 是。DeepSeek API health check 的认证、模型和响应均 PASS；正式执行 24 runs、8 tasks、358 个真实 Aer VQE runs。
6. **模型/provider/prompt？** `deepseek-v4-flash`，OpenAI-compatible `https://api.deepseek.com`，prompt `research_agent_v03_deepseek_v01`，hash `530641052769c78fd36905fe2ecdffe6b44280657964b0493fbbcf6c1e0ac4af`。
7. **Thinking mode？** Health check 已真实验证 thinking response；复杂 strict-JSON smoke 多次耗尽 reasoning tokens且 content 为空，因此正式 frozen setting 明确使用 `thinking_mode=false`。该适配没有修改科学配置。
8. **Structured output invalid rate？** 2/181=1.10%；repair-attempt record rate=7.73%。两个 invalid runs 全部保留并进入分母。
9. **自主 hypothesis proposal？** 本套 8 tasks 均提供初始 hypothesis，正式 run 未产生 `PROPOSE_HYPOTHESIS`；proposal schema 与 fixture tests PASS，但不能声称本轮观察到自主形成。
10. **是否因 evidence 修订 hypothesis？** 是，保存 17 条 live hypothesis revisions；模型 rationale 不作为 EvidenceJudge 输入。

## Scientific exploration

11. **哪类 task Live LLM 最有增量？** Boundary 为 0.67（其他策略均 0），Scope Revision 为 0.33（其他策略均 0）。
12. **哪类 task No-intervention 已足够？** Simple、Replication、Local Counterexample、Stable Negative 五策略 validated rate 均为 1.0 或无主动优势。
13. **Rule-Based 与 LLM 接近吗？** Overall LLM=0.792、Rule-Based=0.750；差仅 0.042，不能据此宣布 LLM 普遍更优。
14. **Competing explanations？** LLM=0.333，Rule-Based=1.0。两次 LLM run 因 invalid Action 提前停止，是稳定性负结果。
15. **Failure modes？** `COUNTEREXAMPLE_IGNORED`, `EXCESSIVE_REPLICATION`, `FAILED_TO_DISCRIMINATE`, `INVALID_ACTION`。另有 thinking/JSON compatibility failure，均未删除。

## Baselines and metrics

16. **预算公平？** 每个策略获得同 task 冻结上限。Live 分配 372、实际使用 358；22/24 runs 耗尽预算，2 个 invalid runs 提前停止。没有额外补预算。
17. **Random 与 LLM replicas？** Random 5 policy seeds；Live 每 task 3 independent runs，共 24。
18. **Experiments to Validated Judgment？** 19 个 validated live runs 的均值 15.368；因 held-out 固定在尾部，成功值主要为完整 12/16 budget，不能解释为早停效率优势。
19. **Validated Judgment Rate？** LLM=0.792、Rule-Based=0.750、Random=0.500、No-intervention=0.500、Fixed=0.500。
20. **其他冻结指标？** Live discriminative ratio=0.858，redundant ratio=0.082；逐 task raw values 已保存。

## Interpretation

21. **Live LLM > Rule-Based？** 不能做总体肯定。LLM 在 boundary/scope 更高，在 competing-explanation 更低，在其余多数任务相等。
22. **Rule-Based > static/random？** 沿用冻结结果：总体 0.75 vs 0.50，并集中在 competing/problem-revision；没有重跑或重调 baseline。
23. **Active exploration 是否 task-dependent？** 是，当前 pilot 明确呈现 task dependence；简单任务无额外收益，结构复杂任务存在正负差异。
24. **M001 状态？** `PARTIALLY_SUPPORTED`。数据支持“反馈价值依赖任务结构”，但只部分支持 LLM reasoning 的增量价值。
25. **下一阶段与真机？** V0.4 应在冻结 task/policy/Judge 下单独加入 noise，检验结论鲁棒性。当前尚无足够跨噪声证据支持消耗移动云真机资源；真机仍留到 V0.5。

## Reproducibility notes

- 正式 live execution commit：`eff123b9b2c164b744a5185c1ee50fd465ac7904`。
- 记录的 token usage 是 lower bound：repair 前一次调用的 usage 未被 provider trace 完整累计；API cost 不可获得，未估算伪值。
- Health check thinking mode PASS；正式 structured decisions 为兼容性明确关闭，不能描述为全程 thinking。
- V0.2 No-intervention 的 2-run status transition 仍不满足 V0.3 Validated Judgment。

## Gate

```text
QEXPLORER_V03_COMPLETE=YES

V01_REGRESSION=PASS
V02_REGRESSION=PASS
V03_NONLIVE_REGRESSION=PASS

DEEPSEEK_API_AUTH=PASS
DEEPSEEK_MODEL_AVAILABLE=PASS
DEEPSEEK_THINKING_MODE=PASS

LIVE_LLM_USED=YES
LIVE_LLM_CALLS_SUCCESS=PASS
LIVE_LLM_STRUCTURED_OUTPUT=PASS
LIVE_LLM_FEEDBACK_SENSITIVITY=PASS

LIVE_LLM_MULTITASK=PASS
LIVE_LLM_BUDGET_FAIRNESS=PASS
LIVE_LLM_HELD_OUT_ISOLATION=PASS
LIVE_LLM_NO_ORACLE_LEAKAGE=PASS

LIVE_LLM_VALIDATED_RATE=0.791667
RULE_BASED_VALIDATED_RATE=0.750000
RANDOM_VALIDATED_RATE=0.500000
NO_INTERVENTION_VALIDATED_RATE=0.500000
FIXED_VALIDATED_RATE=0.500000

M001_STATUS=PARTIALLY_SUPPORTED

ALL_TESTS_PASS=YES

QISKIT_AER_USED=YES
NOISE_SIMULATION_USED=NO
REAL_QUANTUM_HARDWARE_USED=NO
```
