# 「按模型分档、轻重可调」的 Harness 架构：现成件盘点与自建最佳实践（L4）

> **日期**：2026-09-13 · **方法**：gale-research L4（R1 广度 10 路 → R2 一手深挖 → R3 终裁 → R4 缺口递归），实际 13 搜索 / 5 抓取
> **场景**：用户大局命题——"我要一套**灵活、可调整、针对不同模型、兼容大小模型、轻重可调**的 harness（比如 DevFlow 这套完整开发流程）。有没有现成的？自建的最佳实践是什么？" 本份是系列第六份 = **集成设计面**（前五份回答了"管什么/管多严/怎么测/换代怎么办"，本份回答"把'严松可调'做成什么机器"）。
> **核心答案预览**：**完整现成件不存在**（四份术语合流检索确认无此产品）；但**五个零件可直接抄**；自建蓝图有清晰的六层工业先例。
> **硬性排除**：无公开仓库/文档的口头宣称、企业白皮书式套壳营销
> **读取范围声明**：一手·全文 = 完整读取；一手·部分 = 关键节已读（claude-gates 的 README 为 npm 镜像全文抓取后分节提取，HarnessX 为 GitHub README 全文，Chock 为 pypi 页全文——其页仅一个 alpha 版本记录，属"一手但内容稀薄"如实标）。

---

## 1. 术语对照表

| 中文 | 英文 | 区分项 |
|---|---|---|
| 门禁轻重 | enforcement tier：DENY / WARN / Silence | claude-gates 的三态语义——**不是开关二值**，是"拦/劝/沉默"三档 |
| 策略编译 | policy compilation / governance-as-code | 写一次规则 → 编译成各 harness 原生强制面（PreToolUse hook、git hook、CI、AGENTS.md）+ **覆盖率报告** |
| 能力分档 | capability tier（F/M/W） | Goal-Autopilot/AgentRunner 的按模型档位路由 |
| 动态脚手架 | dynamic scaffolding | 已入模式目录：脚手架按运行时状态/能力条件启用，而非静态全量 |
| 门禁晋升 | eval-gated promotion（advisory→enforced） | cortex-x：60 次绿色台账+零误杀才升格强制，降级需显式 env+台账（单向棘轮） |
| 评估即治理 | eval-to-guardrail lifecycle | CI 评估的 rubric 与运行时护栏**同源单真相**——offline 测试标准与 online 执法不漂移 |
| 开关腐坏 | flag rot / toggle debt | 可调 = 债：死开关、无演练的 kill switch、无人认领的 toggle |
| 来源可查 | provenance display（"每条值从哪来"） | claude-gates `status` / monkeyleash `(source:)` 列——**configured vs proven** 的开关版 |

## 2. 候选对比总表

### 2.1 现成件盘点（"有没有"——逐一给成色）

| 候选 | 形态 | 成色（一手核实） | 对 DevFlow 的可抄度 |
|---|---|---|---|
| **claude-gates**（npm @devrik-tools） | CC 专用可安装门禁集：**50 门禁 × 11 家族**，每条 `[on]/[off]` 默认档；DENY/WARN/Silence 三态；**按 gate/家族/all 逐个 enable/disable，`--project`/`--global` 两级**；`status` 显示当前目录生效值及**来源**；`init` 再跑只 merge 不覆盖（翻转需逐条确认）；每条消息带 `[configKey]` 可查；**零运行时依赖（Node 内置）每门禁自包含** | v1.2.1，2026-08 新建，周下载 1639，MIT | 🔴 **交互面直接抄**（轻重可调 + 来源显示 + 合并保护三件套是我们要的 UX）；门禁内容本身与我们重叠度低 |
| **Chock**（pypi） | "agent-neutral policy-engineering framework"：**声明一次策略 → 编译成各 agent 实际支持的最强控制 + 覆盖率报告**（PreToolUse hook/git hook/CI 门/托管 AGENTS.md 块）；有 GH Marketplace Action | **仅 v0.0.1a0 一个 alpha（2026-08-15）**，Apache-2.0 | 🔴 **概念直接抄，代码不可依赖**——"编译面矩阵 + 覆盖率报告"正是 install.sh 该变成的东西 |
| **HarnessX**（小米 Darwin-Agent，GitHub MIT 454★，arXiv 2606.14249） | harness foundry：**`agent = model.agentic(harness)` 的干净分离**——`ModelConfig`（provider 路由/fallback/**per-role 模型指派**）+ `HarnessConfig`（9 维行为管线：tools/memory/processors/trace/sandbox）；任意行为=Processor，`\|` 算子组合；YAML 配置入口；Adapt=自动搜索最优 harness 配置；Evolve=轨迹回流训练 | 研究代码：贡献者 5 人、主开发提交仅 14+5 commits；无生产案例记录 | 🟡 **架构蓝图抄**（ModelConfig/HarnessConfig 分离 = 我们 config.yaml 该长成的形状）；依赖不可 |
| **CC 原生配置层**（官方 docs 一手） | 五层优先级：managed→CLI→**local→project→user**；`model` 可按层 pin（**project settings 即"模型档案"**）；`env` 块限定作用域；`disableAllHooks` 按 scope；`availableModels` 限团队可选；`fallbackModel` 链 | 生产级；**但有坑**：#32422 user 级 hooks 整体覆盖 project 级（正是我们 merge-settings.py 治过的病）；shell `ANTHROPIC_MODEL` 压过一切层 | 🔴 **底座直接用**——DevFlow 的"档位开关"就该落在 settings 分层 + 我们的 merge 协议上，不另造配置系统 |
| **网关/路由层**（LiteLLM model groups / Portkey conditional / Higress 智能路由 / RouteLLM） | per-role 别名路由（planner/executor/judge 各配一档模型，**fallback 只在档内不跨档**）、conditional-on-metadata、auto-router（复杂度分级+Thompson） | 生产级、开源可自托管（LiteLLM 有供应链事故前科——Inworld 那篇警示） | 🟡 对 DevFlow=可选层：我们管 CC 的 ANTHROPIC_MODEL 指向即可，无需自建网关 |
| **门禁晋升范式**（cortex-x / gainam / LaunchDarkly guardrail metrics） | advisory→enforced 的**证据晋升规则** + "CI 评估与运行时护栏同一 rubric 单源" + flag 附带指标 | 范式级（非安装包） | 🔴 轻重升降级的**规则**直接抄 |
| 无关/证伪项 | "one unified cross-model harness toggle product" | **检索不存在**（synthesis 判词："No source uses all four terms together"） | —— |

**盘点结论**：**没有现成完整件**。市场格局 = claude-gates 给了交互面答案、Chock 给了编译器答案、HarnessX 给了分离架构答案、CC 给了承载层答案——**四块都是零件，装机工程（对账到租户模型档位）没人做**。这与我们"DevFlow 即平台"的定位恰好互补：我们缺的不是想法，是把已有零件焊成编译器的活。

### 2.2 自建蓝图：六层架构（每层有出处）

```
[声明层] rules manifest —— 每条规则一个对象，写一次
   字段：id / tier 默认(on|warn|off) / 类别(policy|compensation) /
        assumption(补偿哪代模型哪个弱点，policy 类填 null) /
        targets(hook|git-hook|CI|CLAUDE.md 段) / capability_scope{W,M,F}
        │
[编译层] install.sh --update = 策略编译器（Chock 概念）
   按 manifest 生成/merge 各 target 面 + 输出覆盖率报告：
   "本租户 47 条规则，其中 41 条已在最强可用面执法，3 条仅软层，
    3 条被 local 覆盖，来源逐条可查"
        │
[分档层] config.yaml 模型档位 → 三套激活集
   W 档：外置门禁全开、prompt 过程指令最少（L1/L3 律）
   M 档：中间；F 档：契约+结果门禁，过程门禁降 warn
   （Goal-Autopilot 的 F/M/W、AgentRunner 动态分层的静态简化版）
        │
[运行时开关层] claude-gates 三件套：逐门禁 enable/disable(project/global)
   + status 来源显示 + re-init 只 merge 不覆盖 + [configKey] 前缀可查
   kill switch = 现有 emergency-bypass，但加演练（见反模式）
        │
[晋升/降级层] eval-gated ratchet（cortex-x 规则移植版）：
   新规则先 warn 档跑 N 个绿色票面 + 零误杀 → 方可升 DENY；
   降级需显式记录；换代时按 assumption 字段跑 ablation（接上一份报告）
        │
[版本层] model pin(带日期名) + 升级窗口 SOP + 换代回归套件(E1 固定子集)
```

### 2.3 与 DevFlow 现状的映射差（自建工作量清单）

| 六层 | 我们已有 | 缺口 |
|---|---|---|
| 声明层 | 规则散落四处（gate-checklists/hooks/CLAUDE.md/AGENTS.md），**无统一 manifest** | 🔴 新建（核心工作）|
| 编译层 | install.sh 已是土编译器（模板→租户）+ merge-settings.py 治过合并 | 🟡 加"覆盖率报告"输出 |
| 分档层 | config.yaml 只有 `model:`/`language:` | 🟡 加 capability_tier 字段 + 三激活集 |
| 运行时开关 | **v3.6 角色门 + OWNER_SESSION + trace.jsonl 已是晋升层雏形**；bypass 文件已有 | 🟡 加逐门禁粒度 + status 来源显示 |
| 晋升层 | green-gate 已有；cortex-x 式台账在 trace.jsonl 里**数据已存在** | 🟡 写晋升规则并接台账 |
| 版本层 | CHANGELOG/RETIRED/v3.x pin 模板齐 | 🔴 换代回归套件（接 E1 固定子集，上份报告已立项）|

## 3. 排除清单及原因

| 候选 | 排除 |
|---|---|
| 企业 agent 管控平台（OpenHands Control Plane 商业版、AIFlowy 等国内平台） | 重量级 SaaS/企业栈，与"个人多租户模板仓库"形态不匹配；仅取其"控制面=策略+观测+编排"分层概念 |
| LangGraph/CrewAI 等编排框架 | 是"写 agent 的框架"不是"管 agent 行为的 harness 配置面"（Harrison Chase 三件套辨析：framework≠runtime≠harness） |
| UiPath/Bedrock/Salesforce 的 HITL 升级面板 | 客服/自动化域，阈值设计可借但形态不匹配 |
| TA-SAE 挣扎检测（sparai） | 内部激活信号需模型权重访问，API 模型不可用——留作远期观察 |
| 已证伪检索：`"per-model harness preset profiles for coding agents" 产品` | **不存在**——claudectx 只切整套配置、无"按能力档切规则轻重"的现成件（=自建空位确认） |

## 4. 关键技术判断

### 4.1 分化点：**"轻重可调"的核心不是开关数量，是每条规则携带的元数据**

反面教材是 flag rot（DoorDash 要用多 agent 系统才清得动开关债）与"规则预算"（L2：可调规则本身占遵从率预算）。claude-gates 的解法值得注意：**默认档 + 家族制**——50 条规则但用户日常只需动家族级开关，`status` 回答"现在什么在管我"。
推论：自建的 manifest 里 **`assumption` 与 `类别` 两个字段是全系统的枢纽**——它们同时服务：换代消融（上份报告）、晋升台账（哪条规则该升该降）、规则预算审计（policy 类不可动、compensation 类按档自动收放）。一个 manifest 消灭现在"CLAUDE.md 写一遍、hook 写一遍、checklist 写一遍、三处各自漂移"的病根（= DEFECT-019 的总病根）。

### 4.2 "兼容大小模型"的承载 = 激活集，不是双套流程

分档不是维护两个 DevFlow。同一 manifest、三张激活集（W/M/F 各一条规则→tier 映射），切换=改 config.yaml 一行。W 档加的不是"更多规则"而是**更多外置执法、更少 prompt 内文**（L1/L3 律：给结构不给指令）——所以 W 档的 CLAUDE.md 反而应比 F 档**更短**（这与 FEEDBACK-006 瘦身方向天然一致：瘦掉的量转成 DENY 门禁，两档各取所需）。

### 4.3 采购/自建前必测项

1. **CC 分层合并语义验证**：#32422（user 覆盖 project）在现役版本是否仍现——**决定我们的 per-tenant 开关放哪层**；若现，merge-settings.py 需扩展合并 hooks 而不只 permissions。
2. **覆盖率报告的正确性自证**：编译器声称"已执法"的每条要能被探针反证（configured ≠ proven，monkeyleash 纪律）——复用 selftest_hooks 机制扩成"47 条中 N 条已证实在最强面"。
3. **一次 kill-switch 演练**入 bats/冒烟：bypass 存在→全家放行→删除→恢复，全程 trace 留痕（没演练过的开关不算存在）。
4. 分档激活集的**首次实验验证就是 E1**：三臂 ≈ F/W/中间形态各激活集，实验与架构建设同一笔投资。

### 4.4 反模式清单（全部有实证出处）

- **裸开关海洋**：逐规则独立布尔 × 数十条 = 没人再敢动 → 家族制+默认档（claude-gates/Fowler）
- **无演练 kill switch**：emergency-bypass 类全局旁路长期不测，出事时失效（getunleash/flagsmith："before you ship, not after"）
- **无寿命开关**：临时豁免不带到期日（DoorDash flag-cleanup 规模教训；cortex-x allowlist 的 `expires_iso` 是对症设计）
- **fallback 跨档**：便宜模型挂了自动升贵模型 = 预算爆炸（LiteLLM 文档明言 fallback 只在档内）
- **shell env 幽灵覆盖**：`ANTHROPIC_MODEL` 导出压过所有 settings 层且无痕（多独立报告同一坑）——我们的 dispatch/reconciler `unset OWNER_SESSION` 是同族纪律，扩展为安装期检查"shell 里有没有幽灵 ANTHROPIC_* 变量"

## 5. 缺口裁决表（L4）

| # | 缺口 | 动作 | 裁决 |
|---|---|---|---|
| G1 | 完整现成件是否存在（四合一：manifest+编译+分档+开关） | R1 综合 + R3 定向 | **已闭合（负面）**："no source uses all four terms together"；各层各有一件，装机工程空白 |
| G2 | HarnessX/Chock/claude-gates 生产采用证据 | R2 仓库数据 | **部分闭合**：HarnessX 无生产案例记录（研究件）、Chock 单 alpha、claude-gates 有下载量无案例——**三者皆不可作为依赖，只可作为规格参考** |
| G3 | CC user-overrides-project hooks bug 在现役版本状态 | 检索 | **未闭合**：#32422 开放状态未核实到修复记录；**列为必测项 #1**，本地 5 分钟可验（写两层 hooks 试一次） |
| G4 | "按能力档自动生成激活集"有无人做过 | R3 | **未闭合（存在性=无）**：最接近是 AgentRunner 的运行时动态分层（企业栈内）与 HarnessX Adapt（研究代码）——静态三档激活集确认是空位 |
| G5 | 开关治理成熟度工具（到期日/来源显示/演练） | R2 散布证据 | **已闭合**：零件各有出处（Fowler 分类学、cortex-x expires、claude-gates status、DrdDash cleanup），无统一件——并入自建清单 |

## 6. 推荐结论

**总判断：不引入任何现成件作为依赖；把 DevFlow 自身从"模板分发器"升级为"策略编译器"。市场已把四块零件的证明各自做完，装机工程是空位，且只有模板仓库方（我们）有动机做。**

**分步（全部向后兼容，无大爆炸）：**
1. **短期 = manifest 先行**（约一天）：新建 `.devflow/rules.manifest`——把现有规则（hooks 拦截项、gate-checklists 硬规则、CLAUDE.md MUST、git hooks）**逐条搬进对象表**，字段照 §2.2（tier/类别/assumption/targets）。纯文档化动作，不动任何执行面；顺带生成"覆盖率报告"首版（大概率当场暴露新的三处漂移——这正是它的价值）。
2. **短期 = CC 分层验证 + status 子命令**（必测项 #1/#2 落地）：`devflow gates status` 抄 claude-gates 交互面（当前目录生效值+来源），数据源即 manifest + 租户 settings 实态。
3. **中期 = 三档激活集 + config.yaml `capability_tier`**：与 E1 同批验证（实验臂=激活集切换，架构与实验共用一套机器）；E0 若选 C，E1 的产出同时是 manifest 首版三档参数的校准数据。
4. **中期 = 晋升规则入 green-gate/constitution**：warn→DENY 晋升台账读 trace.jsonl（数据已在），降级需 journal（cortex-x 纪律移植）。
5. **长期（观察不预付）**：运行时挣扎信号自动升降档（AgentRunner 方向）、AEGIS 式自动搜索配置（HarnessX 方向）——等静态三档跑过两个换代周期再评估。

**对用户命题的正面回答**："轻重可调、大小兼容的 harness"——**现成件没有，但每一层都有人验证过其中一块；自建的本质动作只有一个：把散在四个文件里的规则收敛成一份携带元数据的清单，然后让 install 成为它的编译器。** manifest 是全系列的汇合点：E1 实验测它、换代消融读它、门禁晋升按它、CLAUDE.md 瘦身由它生成——**五份调研的建议最后都收敛到同一张表上。**

## 7. 来源列表

**一手·全文/部分**
- claude-gates（50 门禁/11 家族/DENY-WARN-Silence/enable-disable/status 来源/merge 保护，npm 镜像 README）— https://www.npmjs.com/package/@devrik-tools/claude-gates ｜repo — https://github.com/DevRik99/claude-gates
- HarnessX（ModelConfig/HarnessConfig 分离、`|` 组合、Adapt/Evolve、仓库元数据）— https://github.com/Darwin-Agent/HarnessX ｜论文 — https://arxiv.org/abs/2606.14249 ｜VentureBeat 报道（逆缩放数字）— https://venturebeat.com/orchestration/xiaomis-harnessx-rewrites-its-own-ai-scaffolding-mid-task-and-smaller-models-gain-the-most
- Chock（governance-as-code 编译器 + 覆盖率报告；单 alpha 版事实）— https://pypi.org/project/chock/ ｜GH Action — https://github.com/marketplace/actions/chock-governance-check
- Gain《Eval-to-Guardrail Lifecycle》（CI 评估与运行时护栏单源）— https://gainam.com/insights/agent-evals-in-production
- CC 官方：settings 分层 — https://code.claude.com/docs/en/settings ｜model-config（pin 链/availableModels/fallbackModel）— https://code.claude.com/docs/en/model-config ｜hooks（disableAllHooks）— https://code.claude.com/docs/en/hooks ｜#32422 user 覆盖 project bug — https://github.com/anthropics/claude-code/issues/32422
- Layered Configuration in Claude Code（shell ANTHROPIC_MODEL 压层坑 + env 块 best practice）— https://serverlessdna.com/strands/ai-assisted-development/layered-configuration-claude-code
- LiteLLM 路由/fallback/预算文档（档内 fallback 原则）— https://docs.litellm.ai/docs/routing ｜Portkey conditional routing — https://docs.portkey.ai/docs/product/ai-gateway/conditional-routing ｜Higress 智能路由（中文生态分层）— https://higress.ai/
- cortex-x mutation 标准（advisory→enforced 晋升三条件、allowlist expires_iso、单向棘轮；前轮已全文读）— https://raw.githubusercontent.com/Rejnyx/cortex-x/refs/heads/main/standards/mutation-testing.md
- AgentRunner 动态分层（governability>autonomy，88.9%/−46.8% 延迟）— https://arxiv.org/abs/2605.10223 ｜Goal-Autopilot F/M/W 能力档（前轮已读摘要）— https://arxiv.org/abs/2606.11688
- TeamBench capability-conditional uplift / VisualClaw +15.8 vs +4.0（分档科学化的两例）— https://arxiv.org/html/2605.07073v1 ｜ https://arxiv.org/html/2606.16295v1
- 开关治理族：Fowler Feature Toggles — https://martinfowler.com/articles/feature-toggles.html ｜Unleash kill-switch — https://www.getunleash.io/blog/how-can-feature-flags-act-as-kill-switches-to-prevent-ai-generated-code-outages ｜Flagsmith "built in before you ship" — https://www.flagsmith.com/blog/what-is-a-kill-switch-in-software-development ｜DoorDash flag 清理多 agent — https://careersatdoordash.com/blog/automating-feature-flag-cleanup-at-scale-with-a-multi-agent-llm-system/ ｜"Agents Need Feature Flags" 六型论 — https://www.youtube.com/watch?v=zU4EagB311U ｜Langfuse prompt CI/CD（版本/标签/门/canary/回滚）— https://langfuse.com/resources/engineering/prompt-cicd
- dynamic-scaffolding 模式条目（agentpatterns 目录族）— https://www.agentpatternscatalog.org/landing/patterns/dynamic-scaffolding/ ｜zeljkoavramovic/agentic-design-patterns — https://github.com/zeljkoavramovic/agentic-design-patterns
- Strands Agent Control（运行时策略不改 agent 代码）— https://strandsagents.com/blog/strands-agents-with-agent-control/ ｜Armosec per-agent guardrails — https://www.armosec.io/blog/per-agent-guardrails/
- AgentScope（"模型能力演进匹配"官方卖点，中文）— https://github.com/agentscope-ai/agentscope/blob/main/README_zh.md ｜配置驱动 agent 综述 — https://medium.com/@balajibal/configuration-driven-agents-the-fastest-way-to-build-enterprise-ai-systems-01356f805fb1
