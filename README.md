# Q-Explorer

**面向 VQE Ansatz 失效条件的 AI 主动科学探索环境**

Q-Explorer 将“观察实验—提出假设—选择对照—获得证据—修订判断”实现为可运行、可回放、可审计的科研闭环。项目以 4–6 qubit Ising Hamiltonian 和 Hardware-Efficient Ansatz（HEA）为研究载体，重点研究反馈驱动的科研策略何时有价值，而不是寻找一个看起来最优的量子线路。

> 当前公开版本：V0.5 Gate 0｜119 项测试通过｜Qiskit Aer 已使用｜Live LLM 已使用｜合成噪声已使用｜真实量子硬件科研实验尚未执行

![不同噪声等级下的科学有效 Boundary 比例](results/v04/figures/figure1_scientific_boundary_rate.png)

## 研究问题

项目围绕两个相互关联的问题展开：

1. 在固定 VQE 流程与实验预算下，HEA 的线路深度、纠缠拓扑与 Ising Hamiltonian 结构之间，是否存在可重复的适用条件、失效模式或转变区域？
2. 在同等实验预算下，读取科学证据并据此改变实验策略的 Research Agent，在哪类研究任务上比固定、随机或预先规划的策略更有信息价值？

系统始终将数值事实判断与科研决策分开：

```text
Ising Hamiltonian
  -> Exact Ground Truth
  -> Hardware-Efficient Ansatz
  -> Qiskit Aer VQE
  -> Multi-seed statistics
  -> transparent Evidence Judge          [事实层]
  -> ResearchState / Observation
  -> Research Agent structured Action    [决策层]
  -> next experiment / revision
```

LLM 不能修改 Evidence Judge、实验预算、held-out 划分或冻结阈值，也不能用自然语言覆盖数值证据。失败 run、invalid action 和反例均保留在 trace 中。

## 已完成阶段

| 阶段 | 核心内容 | 已验证结果 |
|---|---|---|
| V0.1 | Ising、精确求解、HEA、Aer VQE、多 seed、结构化日志 | 16/16 个真实 Aer VQE run 成功，最小证据闭环成立 |
| V0.2 | ResearchState、Action schema、预算、记忆回放、三类 baseline | Agent 的下一行动会随 SUPPORT / COUNTEREXAMPLE 改变；等预算比较完成 |
| V0.3 | 8 类 Research Task、Live LLM、Rule-Based、Random、No-intervention、Fixed | 24 个 Live LLM research run；总体 validated rate 仅作初步任务依赖证据 |
| V0.3-C | Boundary、Scope Revision、Competing Explanations 定向复现 | 每个关键任务累计 15 个 Live LLM run；负结果和 invalid run 未替换 |
| V0.3-D | 科学有效性审计 | 区分 outcome validity 与 scientific-process validity；Scope 能力降为 INCONCLUSIVE |
| V0.4 | Boundary 合成 NISQ 风格噪声鲁棒性 | N1/N2/N3 均分类为 SHIFTED；未声称对应任何真实设备 |
| V0.5 Gate 0 | 中国移动云五岳平台接入与候选可行性审计 | 完成离线接入设计；0 个真机任务，0 个真机 VQE run |

## 关键实验结果

### 多任务主动探索（V0.3）

冻结任务集包含 Simple Falsification、Replication Needed、Local Counterexample、Competing Explanations、Stable Negative、Boundary、Scope Revision 和 Problem Revision 八类任务。

| 策略 | Validated Judgment Rate |
|---|---:|
| Live LLM | 0.7917 |
| Rule-Based Active | 0.7500 |
| Random | 0.5000 |
| No-intervention | 0.5000 |
| Fixed | 0.5000 |

这组小样本结果不支持“LLM 普遍优于 baseline”。V0.3-C 的定向复现显示：Boundary 为 8/15、Scope Revision 为 6/15、Competing Explanations 为 12/15。V0.3-D 进一步发现，Scope 的 18 次 revision 均只有间接证据关联，因此 evidence-attributed validated rate 为 0/15，Scope Revision 科学能力保持 `INCONCLUSIVE`。这说明最终结果正确并不自动意味着科研过程有效。

### Boundary 噪声鲁棒性（V0.4）

V0.4 使用预注册的 Qiskit Aer density-matrix 合成噪声压力测试：

| Level | 1q depolarizing | 2q depolarizing | readout | Original validated | Scientifically validated | 状态 |
|---|---:|---:|---:|---:|---:|---|
| N0 | 0 | 0 | 0 | 8/15 | 7/15 | PRESERVED |
| N1 | 0.0005 | 0.005 | 0.005 | 14/15 | 14/15 | SHIFTED |
| N2 | 0.001 | 0.01 | 0.01 | 10/15 | 8/15 | SHIFTED |
| N3 | 0.002 | 0.02 | 0.02 | 11/15 | 9/15 | SHIFTED |

在冻结的 4-qubit Boundary task 中，探索集方向保持 `RING_WORSE`，held-out 方向保持 `RING_BETTER`；主要 transition region 在 `[1,2]` 与 `[2,3]` 间变化。该结果仅表明合成噪声条件下的方向保持与位置敏感性，不代表真实硬件机制，也不证明噪声改善了 Agent 或 VQE。

### 真机准备状态（V0.5 Gate 0）

项目已经读取两个冻结的 hardware-validation candidates，完成测量分解、通用拓扑转译压力测试、Hardware-A 固定参数验证草案和 Hardware-B 成本估算。由于当前没有配置移动云量子凭证，账号设备、连接图、校准和提交权限均未被臆测：

- `REAL_HARDWARE_ACCESS_CONFIRMED=NO`
- `FORMAL_HARDWARE_RESEARCH_JOBS=0`
- `FORMAL_HARDWARE_VQE_RUNS=0`
- `V05A_RECOMMENDED=NO`（需先完成凭证化设备发现和经人工确认的 smoke job）

## Agent 与大模型

项目实现了统一的 Research Agent 接口，但并非所有 Agent 都依赖大模型：

- `FixtureResearchAgent`：测试夹具，无大模型；
- `RuleBasedResearchAgent`：透明规则式主动策略，无大模型；
- `RandomExplorer`、`NoInterventionExplorer`、`FixedExplorer`：baseline，无大模型；
- `LLMResearchAgent`：通过 OpenAI-compatible provider adapter 调用模型，正式 V0.3/V0.4 实验使用 DeepSeek `deepseek-v4-flash`，`thinking_mode=false`。

LLM 只负责选择下一项科研行动和提出/修订假设；VQE、统计量、Evidence Judge 和 validated criteria 均由确定性代码完成。

## 仓库结构

```text
q-explorer/
├── configs/          # V0.1–V0.4 冻结配置与 V0.5 Gate 0 审计配置
├── data/             # 可复现 Hamiltonian 实例
├── docs/             # 各阶段完整科研报告
├── prompts/          # 版本化 Research Agent prompts
├── results/          # 聚合结果、审计表、图和机器可读 summary
├── scripts/          # 实验、审计、分析和复现入口
├── src/
│   ├── hamiltonian/  # Ising 生成与 Qiskit operator
│   ├── exact_solver/ # 经典精确基准
│   ├── ansatz/       # Hardware-Efficient Ansatz
│   ├── backend/      # Aer noiseless / synthetic-noise backend
│   ├── vqe/          # VQE runner 与优化轨迹
│   ├── evidence/     # 统计聚合与透明 Evidence Judge
│   ├── research/     # State、Memory、Agent、Budget、provider adapter
│   ├── v03*/         # 多任务、复现与科学有效性审计
│   ├── v04/          # BoundarySignature、Estimator 与噪声分类
│   └── v05_gate0/    # 真机审计接口和执行 guard
├── tests/            # 119 项回归、隔离、安全和科研有效性测试
├── traces/           # append-only action/experiment/evidence/revision traces
├── .env.example      # 仅变量名，不含 secret
├── pyproject.toml
└── requirements.txt
```

## 快速开始

要求 Python 3.10+。建议使用独立虚拟环境。

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts\doctor.py
python -m pytest -q
```

### Linux / 阿里云

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts/doctor.py
python -m pytest -q
```

运行最小 V0.1 smoke test：

```powershell
python scripts\run_smoke_test.py
```

复用已有 grid，仅重新校验和生成报告：

```powershell
python scripts\run_smoke_test.py --reuse-grid
```

## Live LLM 配置

凭据只能通过环境变量提供。仓库、冻结配置、日志和报告均不得保存 API key。

```powershell
$env:LLM_PROVIDER = "openai_compatible"
$env:LLM_BASE_URL = "https://your-provider.example"
$env:LLM_API_KEY = "set-locally-only"
$env:LLM_MODEL = "your-model"
python scripts\check_live_llm.py
```

`.env.example` 只提供变量名称。正式实验脚本会产生 API 调用和新的实验记录；除非进行新的预注册研究，不要为了改变已有结论重复运行。

## 主要复现入口

```powershell
# 环境与全部回归
python scripts\doctor.py
python -m pytest -q

# V0.2 反馈敏感性
python scripts\run_feedback_sensitivity.py

# V0.3 冻结任务审计与非 Live 策略
python scripts\audit_v03_tasks.py
python scripts\run_v03_task_suite.py --strategy rule_based --task-suite configs\frozen_v03_tasks.yaml

# V0.3-D：只读科学有效性审计，不产生新实验
python scripts\run_v03d_audit.py

# V0.4：协议检查与合成噪声 smoke test
python scripts\prepare_v04_protocol.py
python scripts\run_v04_noise_smoke.py

# V0.5 Gate 0：AUDIT guard 下的离线能力审计
python scripts\run_v05_gate0_audit.py
```

完整正式 Live LLM / noisy runs 已保存为冻结历史产物。执行相关 runner 前请先阅读对应报告和配置，避免把复现检查误当成新的独立科研样本。

## 报告与证据

- [V0.1 环境与最小闭环](docs/V01_REPORT.md)
- [V0.2 主动反馈与 baseline](docs/V02_REPORT.md)
- [V0.3 Live LLM 多任务比较](docs/V03_REPORT.md)
- [V0.3-C 定向复现](docs/V03C_REPORT.md)
- [V0.3-D 科学有效性审计](docs/V03D_REPORT.md)
- [V0.4 Boundary 噪声鲁棒性](docs/V04_REPORT.md)
- [V0.5 Gate 0 真机能力与接入审计](docs/V05_GATE0_REPORT.md)

权威聚合结果位于各 `results/v*/...summary.json`；逐轮行动、实验、Evidence Judge 输出和 revision 保存在 `traces/`。原始失败与 invalid run 不会在聚合时删除或替换。

## 科研边界与诚信声明

当前证据支持的是冻结任务空间内的可复现、任务依赖结果，不支持以下外推：

- 不支持某种 HEA 纠缠拓扑在所有问题上普遍更优；
- 不支持 LLM Research Agent 普遍优于规则策略或静态计划；
- 不支持把相关性解释为量子噪声机制；
- 不支持把 Aer 合成噪声结果描述成真实设备结果；
- 不支持声称已经使用中国移动云量子真机。

项目坚持保留负结果、反例、invalid action 和预算内失败，并使用 held-out isolation、配置冻结、prompt hash、历史 hash 与双层科学有效性审计防止结果导向修改。

## 安全说明

- 不要提交 `.env`、API key、云平台 access key 或 secret key；
- 首次公开上传前请再次执行敏感信息扫描；
- 真机 adapter 默认运行在 `AUDIT` 模式，未经明确授权会阻止真实任务提交；
- V0.5 Gate 0 只生成协议草案，不包含真实硬件科研数据。
