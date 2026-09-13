# 模型规模 × TDD 表现 × 最佳 Harness 形态：存在模型无关的通用规律吗（L4）

> **日期**：2026-09-12 · **方法**：gale-research L4（R1 广度 10 路 → R2 一手深挖 9 源 → R3 终裁 → R4 缺口递归 5 条）
> **场景**：E0 决策（强制 TDD 门禁去留）的最后一个变量——**我们的模型（DeepSeek V4 flash / 未来 qwen3.6-flash）不是实验文献里的模型**。用户猜想：应存在模型无关的通用规律。
> **猜想判定**：✅ **成立**。检索收敛出五条相互印证、跨模型系稳定的规律（§4），并据此**修正了前一份社区动向报告的初步结论**（§6.4）。
> **硬性排除**：star/融资叙事、无方法 SEO 文、把"SOTA 榜单"当能力证据
> **读取范围声明**：一手·全文 = 完整读取；一手·摘要 = 官方 abstract 全文（正文未读，数字以摘要为准）；摘要转引 = 检索引擎节选。§4 每条规律均有 ≥2 个相互独立的来源；未全文读取的部分如上，不影响任何单条规律的支撑链。

---

## 1. 术语对照表

| 中文 | 英文 | 区分项 |
|---|---|---|
| 逆缩放 | inverse scaling (of harness benefit) | **harness 收益与模型能力负相关**——与直觉"强模型更能利用工具"相反 |
| 规则诅咒 | curse of instructions | 同时遵守 N 条规则的成功率 ≈ p₁×…×pₙ，**指数衰减** |
| 上下文腐蚀 | context rot | 输入越长表现越差，**与检索质量无关**（纯长度效应） |
| model-harness fit | 模型-脚手架拟合 | 弱模型围绕自身风格进化出的 harness 被专家轨迹模仿训练后会**错配**（7 任务全退 4–30 分） |
| 任务契约 vs 步骤清单 | task contract vs step checklist | 契约=目标/边界/验收证据（容量无关）；清单=替模型做规划（容量依赖，**应随模型变强逐步删除**） |
| 结构外置 | externalized determinism | 把约束放进 hook/状态机/确定性代码，而不是放进 prompt |
| 能力层 | capability tier（F/M/W） | Goal-Autopilot 的 Frontier/Mid/Weak 标签体系 |

**须区分**：①"给弱模型更多结构"与"给弱模型更多提示词"是**相反**的操作，证据支持前者反对后者 ②"harness 收益大"≠"任意 harness 都行"——为强模型调的 harness 可能反噬弱模型 ③换模型归因错误：**harness 漂移被误记为模型变笨**（本调研第四规律）。

## 2. 候选对比总表

### 2.1 五条通用规律（本报告主体，每格可证伪）

| 规律 | 核心表述 | 独立来源（≥3 系） |
|---|---|---|
| **L1 逆缩放** | harness 收益与模型能力负相关：越弱的模型，好 harness 的边际收益越大 | HarnessX（Qwen3.5-9B +44%，全组合均值 +14.5%）；AI4AI strong-to-weak（0.49→0.91，**弱目标模型受益最大**）；tlDR（弱模型从 skills 大进、**强模型反退**）；Co-Evolving（自动 harness 进化"使小模型以极小成本接近前沿"）；TDAD（图上下文对 30B 有效、流程指令无效）|
| **L2 规则预算乘法** | 每加一条同时生效的规则，全体遵从率按乘积衰减；context 越长衰减越大——**规则本身是税，弱模型税重** | Curse of Instructions（5 系模型指数衰减，ManyIFEval）；Chroma Context Rot（**18 模型无一幸免**，简单任务也退化）；Du et al.（长度纯效应，与检索无关）；Taskade 脚手架税（精简 prompt 反超 10–15% 评分省 41–66% token）；IFScale |
| **L3 结构放对地方** | 弱模型需要的是**外置于 prompt 的确定性结构**（hooks/门禁/状态机/严格格式），不是**写进 prompt 的流程指令**（后者挤占其上下文） | AI4AI 机理分析（收益来自"把不稳定推理**卸载进确定性代码**+严格格式强制"，**不是**让模型想更多）；Goal-Autopilot（gated FSM+硬地板：**伪造成功结构性不可能**，编造率 0.95% vs Reflexion 8.1%/StateFlow 25.1%）；TDAD（同结论的反面：流程型 prompt 反而+3.9pp 回归）；阿里云实践（弱模型→硬编码 workflow） |
| **L4 验证可替代性** | 任务的**可机械验证性**与模型能力是替代项：验证越强，能用的模型越弱；反之弱模型配弱验证=灾难 | freddysblog（"任务越可验证，能安全使用的模型越弱"）；Meta JiT（变异验证×生成测试=检出 4×）；cortex-x/gitlocus（mutation 兜底 LLM 编辑）；**arXiv 2602**（deepseek-v3.2 写测试率 89.2% **且自发测试主要是 print 观测**——弱模型自写测试证明力最弱，外部验证需求最大）|
| **L5 harness 漂移主效应** | 模型不变、仅换 harness 版本：解决率 23–39% 摆动、token ~2×——**"变笨了"多半是 harness 回归** | Don't Blame the LLM（35 个 Qwen Code 版本受控纵向，50 题 SWE-bench Verified，首个此类研究；"More Code ≠ Better Agents"）；Scaffold Effect（同 harness 故障指纹跨模型复现：Goose=REASON、OpenHands=VERIFY/MAX_TURNS、OpenCode=idle-loop——**harness 偏差系于 harness 本身，与模型无关**；token/任务差 40×） |

### 2.2 按能力档位的最佳 harness 形态（L1–L3 的工程推论）

| 档位 | 证据锚点 | 最佳 harness 形态 | 该避免的 |
|---|---|---|---|
| 前沿（F） | OpenAI harness 工程（Codex 团队）："** centrally enforce boundaries, locally allow autonomy**"；tender 模型反被重流程拖累（tlDR sec-334） | 轻 prompt 契约 + 强**外置**验收（CI/变异/证据门禁）+ 授权自治 | 细粒度步骤清单、过程戏法 |
| 中档（M，≈V4 Pro / qwen-plus） | arXiv 2602：Pro 类模型自发测试率高但测试多为观测；RigorBench：工具强制不改过程指标但规划型 harness 相关结果+30% | 契约 + 粗粒度门禁（RED 前置、验收证据），流程指令开始做减法 | 全栈流程强制 |
| 弱/小（W，≈V4 Flash / qwen-flash） | TDAD："small models need context, not procedure"；HarnessX 9B +44%；DCAS（为某脚手架微调的模型换脚手架即崩） | **确定性门禁全外置到 hook/commit 层** + prompt 只留 invariant（核心 prompt <500 token）+ 给**仓库结构上下文**（图/ impacted tests）而非流程步骤 + **harness 要为弱模型单独调**，勿复用强模型调好的那套 | 长 system prompt（其规则预算先烧完）、照搬强模型 harness |

### 2.3 DeepSeek/Qwen 具体档的动静（场景直连）

| 证据 | 内容 |
|---|---|
| V4 家族实测 | Flash ≈83–85% 的 Pro 质量、成本 1/5–1/8；**harness 间质量基本持平**（Claude Code/OpenCode/Pi 同一 Flash 质量相近），差别在 token 用量（Claude Code ~70 tool calls/task）与成本（成功任务 $0.20 vs $0.07） |
| 无视觉断点 | nateherk 百小时：V4 系在 DeepSeek Harness 下**看不到屏幕**，视觉验证必须外置换成人/工具——L4（验证可替代性）在我们仓的具体体现 |
| Qwen3-Coder-Next | 80B-MoE 激活 3B 专攻 agentic（300 轮稳定），官方明示小模型多轮工具链是设计瓶颈；Qwen3.8-27B "默认过度输出"（simonwillison） |
| 指令遵从鸿沟跨系 | #32163/#32290/HN 109 分 stop-hook 无视帖/"200 行规则全无视"——**prompt 层规则被无视是全系模型通病，弱系更甚**：与 L2 一致 |

### 2.4 工具/框架候选（存在性均已核实一手仓库或论文页）

tdd-guard（钩子态机，可配验证模型档位；作者自报：**即便有钩子，agent 天然跳过 refactor 或只做表面重构**）、probity（同作者后继，runner 无关，跨 Claude/Codex/Copilot）、Goal-Autopilot（学术：gated FSM 硬地板）、FlowAgent（遵从性与灵活性兼得）、HarnessCompass（自动 harness 进化的评测罗盘）、RE-Bench（harness 消融实验学）。

## 3. 排除清单及原因

| 候选 | 排除原因 |
|---|---|
| LinkedIn 原则帖（"弱模型更需门禁"） | **方向与学术源一致但无方法**——只用作 L3 的旁证，不单独支撑任何结论 |
| Kevin Z Claude Code Bible / zbrain / mindstudio 等综述页 | 二手综合无原始数据 |
| 榜单分数（SWE-bench 等）直接推"该模型能不能吃 TDD" | 榜单测的是模型×harness 组合成绩（L5 正是此问题的学术化），不能反推单变量 |
| 中文泛化文（harness 六层架构/十二模块等教程） | 概念梳理无对照；**保留其中两处一手实践**：阿里云硬编码 workflow 自述、deusyu 逆缩放数据汇总（其转引的 #57/#39/#78 与英文源对得上） |
| 已证伪的检索：「TDD 门禁 × 模型尺寸」的直接对照实验 | **不存在**（G1）——社区和我们一样缺这份数据；现有推断全部经 L1–L4 中转 |
| arXiv 2502.14255（长 prompt 反而更好） | 领域微调任务的反例，明示边界后保留于 §5-G3 |

## 4. 关键技术判断

### 4.1 分化点：**"强制结构"不是错，放错层才是**

全部五条规律可压缩成一句：

> **约束应该放进模型碰不到的确定性代码（hook/commit/CI/状态机），上下文预算应该用来给模型"关于仓库的事实"而不是"关于流程的指令"；验收用可机械执行的证据，顺序用粗粒度门禁。**

这化解了本调研线内看似矛盾的三方：Superpowers 卸载潮（错在把流程塞进 prompt 且量级超大）≠ 门禁无用（Goal-Autopilot 外置门禁把编造率从 25% 打到 0.95%）≠ 弱模型需要自由（恰恰相反——它们需要**外置**结构，否则规则预算先烧完）。

### 4.2 用 L2 算一笔我们自己环境的账（可复算）

当前流程注入给模型的**同屏规则负荷**：`.claude/CLAUDE.md` 正文（~185 行，含阶段机/路由表/多条 MUST）+ marker 段（89 行）+ 角色段 + 租户根 CLAUDE.md（UMES3 194 行）+ hooks 拦截消息（每次违规再叠一条）。设单条遵从率 p：p=0.99 时五条关键规则全体生效=95%；p=0.90 时=**59%**；弱系模型 p 更低且被长 context rot 再压一层（L2×Chroma）——**这就是"门禁明明在、宣称却没人执行"的定量机理**，也是 P0-1 之外第二道"门禁与宣称不符"的来源。结论：**CLAUDE.md 瘦身（FEEDBACK-006）不是体验优化，是门禁有效性的前置条件。**

### 4.3 采购/实验前必测项（对 E1 协议的具体修改）

1. **两臂要拆成三个变量**：原 A/B（有门禁/无门禁）混淆了 ①hook 层 RED 前置检查 ②prompt 层 TDD 流程指令 ③宣称文案。按 L3，①可能该留、②大概率该删、③肯定该改——**E1 至少三臂**：现状 / 去 prompt 指令留 hook 门禁 / 全去（换 g0 必过）。
2. **模型档各跑一轮**：V4 flash（现役）+ V4 pro 各一组——按 L1 预期"去 prompt 指令"在 flash 上**增益**、pro 上中性；这个差异本身就是假设检验。
3. **门禁遵从审计先行**：跑实验前先用 `hook-block-audit.py` 统计现状被无视/崩溃率——L2 预测规则越多遵从越差，基线要先量出来。
4. **harness 版本锁定**：实验期间冻结 CC 版本与模板（L5：23–39% 摆动足以淹没我们要测的效应）。

## 5. 缺口裁决表（L4，R3 产出 → R4 逐条动作）

| # | 缺口 | 产生于 | R4 动作 | 裁决 |
|---|---|---|---|---|
| G1 | 有无"TDD 门禁 × 模型尺寸"的直接对照实验 | R2 | 定向检索 tdd-guard/deepseek-harness/mattpocock issues | **未闭合（如实）**：不存在。最近似：arXiv 2602 的模型间自发测试倾向差（3 系）+ TDAD（单系 30B）。**E1 三臂×双档若做成即该交叉的首个数据点** |
| G2 | 逆缩放是否独立复现 | R2 | 核对来源系别 | **仍存疑（半闭合）**：HarnessX 与 Co-Evolving 疑同团队（小米系），AI4AI（独立）与 tlDR（实践）同向——**方向可信，量级单一来源** |
| G3 | "更多指令更好"反例 | R2 | 核 2502.14255 适用域 | **已闭合**：领域内微调评估任务，与 agent 多步执行场景不同构；agent 场景的长指令税另有直接实测（Red Hat 大小 prompt 对照） |
| G4 | 删约束的**量化阈值**（模型强到什么程度删什么） | R3 | 检索能力档切换规则 | **未闭合（存在性确认）**：无人给公式。社区给的是**协议**不是数字：**契约永存、清单渐删、删除触发=验收证据确认契约仍满足**（"build infrastructure that can be progressively deleted"）。E0/E1 的落点即此协议 |
| G5 | DeepSeek V4 的**视觉缺失**对 harness 设计的定量影响 | R2 | 核对 nateherk/DataCamp | **部分闭合**：定性确认（无屏幕验证→需外接断言层）；定量无人测。对我们=**结果门禁必须全程序化，g0 权重上调**（与 L4 一致） |

## 6. 推荐结论

### 6.1 你的猜想的正式裁决

**通用规律存在，且就是 L1–L5 五条**；"具体用什么模型"只改变各条的**系数**，不改变**方向和结构**：

```
弱模型  → 外置门禁价值最高 + prompt 规则预算最紧 + 自发测试证明力最弱
              ↓
   推论：门禁下沉 hook/commit 层，prompt 只留契约，验收靠程序化结果信号
              ↓
强模型  → 同一套形态成立，只是"去 prompt 流程"的收益变小、自治额度可加
```

我们的模型系（DeepSeek/Qwen flash 档）在这张图上的位置：**过程门禁（外置）价值比前沿模型更高，而流程指令（prompt）价值比前沿模型更低**——恰好是"DevFlow 该瘦 CLAUDE.md、该把门禁挂 git 层"的两个独立方向。

### 6.2 三档位的 DevFlow 落法（分场景推荐）

- **短平快**：E1 三臂化（§4.3）+ 基线遵从审计；CLAUDE.md/append 瘦身升格为**门禁有效性的前置项**（从 FEEDBACK-006 的"体验"改判为"机制"）。
- **中期**：门禁权威层从 PreToolUse 下沉 git hooks/commit（L3 + 社区 outpost 三洞实锤）；g0 升必过并保持异步窄域（承上一份报告的 Cashu 教训）。
- **长期**：harness 版本化 + 每次模板/钩子变更跑固定 50 题子集回归（L5 的 Agentic QA 主张，正是我们 bats 体系的扩展方向，接 DEFECT-011 漂移观察）。

### 6.3 诚实边界

1. 全部规律的最强数据来自**非 coding-agent 域**（ALFWorld 具身规划、ToM 问答）搬到 coding 的迁移——同构性中等，方向可信量级存疑（G2 同）。
2. L1 与部分实践报告存在"弱模型根本用不动厚 harness"的反向抱怨（DCAS 显示的是脚手架依赖而非收益）——两者统一于 L3：**外置结构帮弱模型，内化指令压弱模型**；但这条统一式本身缺直接实验。
3. 依旧没有我们仓自己的数据——E1 的必要性不降反升，只是**问题定义被本调研改好了**。

### 6.4 对 E0 初步答案的修正（重要，替代社区动向报告 §6 的"一句话总评"）

社区动向报告当时判"纯 A 判死、方向已定"。叠加模型规模证据后修正为：

> **判死的是"把细粒度 TDD 流程当 prompt 指令强灌"**（Superpowers 模式，L2/L3 双杀）；
> **没有被判死、反而被增援的是"粗粒度 RED 前置作为外置确定性门禁"**（L1 预测它对 flash 档价值最大，L3 的 Goal-Autopilot 数据证明外置硬地板能把可信度问题一个量级地压掉）；
> **被一致判死的是没有任何验收证据层的裸跑**（L4 + 全部事故样本）。
>
> 故 E0 的最优解仍是 **C（实验）**，但实验假设从"要不要 TDD 门禁"更新为：
> **H1′：三臂中"去 prompt 指令、留 hook 门禁"是 cost-benefit 最优臂**（预期 flash 上成本显著降、杀灭力不降）——这是五条通用规律合起来给出的、可被我们本机证伪的具体预测。

## 7. 来源列表

**一手·摘要/全文**
- Don't Blame the LLM: How Agent Harness Evolution Shapes Coding Agent Quality (arXiv 2607.03691, Queen's Univ) — https://arxiv.org/abs/2607.03691 （结论节已全文读）
- The Scaffold Effect in Coding Agents (arXiv 2607.22585, Sentient) — https://arxiv.org/abs/2607.22585
- AI4AI at Test-Time: Strong-to-Weak Capability Transfer via Scaffolding (arXiv 2608.12307) — https://arxiv.org/abs/2608.12307
- Co-Evolving Harnesses and Models (arXiv 2609.09134) — https://arxiv.org/abs/2609.09134
- Goal-Autopilot: Verifiable Anti-Fabrication Firewall (arXiv 2606.11688) — https://arxiv.org/abs/2606.11688
- Curse of Instructions / ManyIFEval (Harada et al., OpenReview) — https://openreview.net/forum?id=R6q67CDBCH ｜执行摘要 — https://maxpool.dev/research-papers/curse_of_instructions_report.html
- Chroma Context Rot（18 模型）— https://www.trychroma.com/research/context-rot
- Du et al., Context Length Alone Hurts (EMNLP 2025 Findings) — https://arxiv.org/abs/2510.05381
- RigorBench (arXiv 2606.22678) — https://arxiv.org/abs/2606.22678
- TDAD (arXiv 2603.17973) — https://arxiv.org/html/2603.17973v1
- Stop Comparing LLM Agents Without Disclosing the Harness (arXiv 2605.23950) — https://arxiv.org/abs/2605.23950
- SWE-Effi（scaffold×model 交互）— https://arxiv.org/html/2509.09853v2
- arXiv 2602.07900（各模型自发写测试倾向表）— https://ar5iv.labs.arxiv.org/html/2602.07900
- FlowAgent — https://arxiv.org/html/2502.14345v1 ｜IFScale — https://arxiv.org/html/2507.11538v1
- nizos/tdd-guard（refactor 跳过自报）— https://github.com/nizos/tdd-guard ｜ https://nizar.se/tdd-guard-for-claude-code/
- nizos/probity — https://github.com/nizos/probity
- OpenAI Harness Engineering（Codex）— https://openai.com/index/harness-engineering/
- Anthropic Building Effective Agents / Effective Context Engineering — https://www.anthropic.com/engineering/building-effective-agents ｜ https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- mattpocock/skills #367（implement 跳过 /tdd）— https://github.com/mattpocock/skills/issues/367 ｜ superpowers #384 — https://github.com/obra/superpowers/issues/384
- 子代理 hook 洞簇 — https://github.com/anthropics/claude-code/issues/34692 ｜ #32163/#32290 ｜HN stop-hook https://news.ycombinator.com/item?id=47895029

**一手·部分 / 摘要转引**
- Xiaomi HarnessX（VentureBeat，作者报道含官方数据）— https://venturebeat.com/orchestration/xiaomis-harnessx-rewrites-its-own-ai-scaffolding-mid-task-and-smaller-models-gain-the-most
- 逆缩放中文汇总 — https://github.com/deusyu/harness-engineering/blob/main/references/articles.md ｜约束优先原则 — https://yeasy.gitbook.io/harness_engineering_guide
- 阿里云硬编码 workflow 自述 — https://developer.aliyun.com/article/1739344 ｜强模型步骤清单→任务契约 — https://www.cnblogs.com/ai-old-six/p/22650543
- Taskade 脚手架税 — https://www.taskade.com/blog/scaffolding-tax-explained ｜Red Hat 大小 prompt — https://developers.redhat.com/articles/2026-02-23/prompt-engineering-big-vs-small-prompts-ai-agents
- freddysblog 可验证性定律 — https://freddysblog.com/2026-08-23/which-model-should-you-use-for-which-task/
- "progressively deleted harness" — https://medium.com/@epappas/the-agent-harness-is-the-architecture-and-your-model-is-not-the-bottleneck-5ae5fd067bb2
- tlDR Sec #334（弱进强退）— https://tldrsec.com/p/tldr-sec-334 ｜DCAS 脚手架过拟合 — https://www.developersdigest.tech/blog/dcas-cli-scaffold-planning-transfer
- V4 家族实测簇：Kilo/Evolink/Tessl/GithubCopilot 帖/r/LocalLLaMA harness showdown — 检索节选（数字标摘要转引）
- nateherk 100 小时 — https://x.com/nateherk/article/2091669829883138512 ｜DataCamp 十项通过测试 — https://www.datacamp.com/blog/deepseek-harness-vs-claude-code
- Qwen3-Coder-Next 技术报告 — https://arxiv.org/html/2603.00729v1 ｜simonwillison Qwen3.8-27B — https://simonwillison.net/2026/Aug/16/qwen-38-27b/
- Addy Osmani Agentic Autonomy Levels（"只授予你付得起验证成本的自治度"）— https://addyosmani.com/blog/agentic-autonomy-levels/
- Meta JiT — https://www.infoq.com/news/2026/04/meta-jit-testing-ai-detection/
