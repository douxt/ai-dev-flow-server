# tiered-research 深度调节机制调研报告

> 2026-09-08 · 方法：3 轮递进调研（广度 6 路并行 → 官方源深挖核实 → 终裁+对抗复查）
> 场景：为纯文本 SKILL.md 形态的 tiered-research 设计可调调研量级，填补"3 轮不够、storm 太重"的空档。
> 硬性排除：需完整编排框架、无法以 prompt 文本落地的方案；非 LLM 语境的学术综述方法论。

## 1. 术语对照表（中英）

| 中文 | 英文 | 说明 |
|---|---|---|
| 广度 × 深度解耦 | breadth × depth decoupling | 并行宽度与递归轮数独立配置；总量 ≈ breadth^depth |
| 努力分档 | reasoning effort / effort tiers | low/medium/high 式离散档位 |
| 量级缩放规则 | scale effort to query complexity | 在 prompt 内嵌"什么复杂度的任务配多少资源"的显式表 |
| 自适应停止 | adaptive stopping / early stopping | 以收益信号（置信、覆盖、语义收敛）决定停止，非固定轮数 |
| 缺口驱动递归 | gap-driven recursion / follow-up directions | 下一轮输入=上一轮"未证问题+新方向"，而非重复调研主题 |
| 知识缺口闭合判据 | knowledge-gap closure | "loop until all critical gaps are closed"（EDR） |

易混淆：轮数（rounds，本 skill 现有量纲）≠ 深度（depth，业界指递归层级）≠ 努力档（effort，模型思考预算）。三者正交，混用一个"轮"字是本问题的根源。

## 2. 候选对比总表（每格有官方出处才打勾）

| 候选 | 官方源 | 机制形态 | 纯 prompt 可落地 | 关键实证 |
|---|---|---|---|---|
| LangChain open_deep_research | ✓ GitHub+configuration.py | 三段数字：并发研究单元 5 / 监督反思轮 6 / 单步工具调用 10 + 每角色 max_tokens | ✗（Pydantic 配置） | 默认档 100 题评测 ≈$46~187、58M~200M tokens |
| GPT Researcher Deep Research | ✓ docs.gptr.dev | breadth(4)×depth(2)×concurrency(4)+total_words(2000~2500)，env/yaml 双通道 | ✗（代码） | 官方定价口径：单跑 ≈5 分钟/$0.4；docs 明言"depth 3-4 → 时间显著增加" |
| dzhng/deep-research | ✓ GitHub README | 仅 2 个用户输入：breadth 3~10（默认4）、depth 1~5（默认2）；递归输入=learnings+directions | ◐（<500 LoC，逻辑极简，最接近可文本化） | 19.6k★，定位"最简实现" |
| Anthropic 多智能体研究系统 | ✓ 工程博客 | prompt 内嵌缩放规则：简单事实 1 agent/3-10 次调用；对比 2-4 子代理/各10-15；复杂 >10 子代理 | ✓（规则本体就是 prompt 文本） | token 消耗解释 80% 性能方差；多代理比单代理高 90.2%；无 guardrail 时出现"50 子代理滥发/重复搜索"失败模式 |
| OpenAI Deep Research API | ✓ developers.openai.com | reasoning effort 枚举 + search_context_size(low/med/high) + 模型档位（o3 vs o4-mini "lightweight"） | ✗（API 参数） | 深度=多杠杆组合而非单一"轮数"枚举 |
| STORM/Co-STORM | ✓ arXiv 2402.14207 | 视角数 P 直接乘进成本（问题生成 S×P 次 LLM 调用） | ✗（独立管线；本机 storm-research 已实现） | ≈5 视角为实用默认 |
| 学术自适应停止（BrowseConf/semantic early-stopping/EDR） | ◐ 摘要级证据，未全文核实 | 置信触发追加 / 草稿语义收敛停机 / 缺口闭合循环 | ◐（判据需机械化为可数标准） | BrowseConf 提示 LLM 自报置信可靠性有限 |

## 3. 排除清单及原因

- **直接加轮数语义（R4=再来一遍 R3）**：无任何被调研系统采用——所有系统的额外轮/层都有不同输入（缺口、子主题、视角）。纯叠加=伪深度，排除。
- **引入配置框架（仿 configuration.py 做 YAML）**：违背单文件 skill 形态，排除。
- **多视角扩展（加 P 维度）**：这是 storm-research-lite 的既定定位（6~44 搜+10~25 LLM+矛盾图谱+同行评审，本地 SKILL.md 已核实），tiered 侵入即破坏三技能分层，排除。
- **"模型自评够不够"式置信停止**：BrowseConf 证据显示自报置信不可靠 + Anthropic 实证 agent 会失控螺旋，须改用可数判据，排除原始形态。

## 4. 关键技术判断

**分化点**：tiered-research 无运行时配置层，一切旋钮必须以"prompt 内可数的数字"存在。因此最优组合已被行业收敛：
**Anthropic 式内嵌缩放表（档位→资源配额）+ dzhng 式缺口递归（额外轮的新输入契约）+ 机械收益闸门（可数收敛判据）**。

采购前必测项（对本 skill 即落地后首跑验证）：
1. L4 档实测搜索+抓取次数是否落在预设 ≤40/≤25 封顶内（防失控）；
2. R4 是否真以显式 gap 清单为输入（防重复搜索——Anthropic 记录的头号失败模式）；
3. 闸门触发时报告是否如实写"止于第 N 轮+原因"（防硬凑）。

## 5. 推荐结论

**短期（本次改动，推荐）**：参数表"轮数"升级为 L1~L4 档位表（向下兼容："2 轮/3 轮"旧说法自动映射）：

| 档 | 旧对应 | R1 并行 | R2 深挖上限 | 额外动作 | 预算封顶（搜索/抓取） |
|---|---|---|---|---|---|
| L1 速览 | —（新增） | 3~4 | — | 仅三件套，不落完整报告 | ~8 / 0 |
| L2 标准 | 默认 2 轮 | 4~8 | 6~8 | — | ~15 / 10 |
| L3 深度 | 3 轮 | 4~8 | 6~8 | R3 终裁 top2~3 | ~22 / 15 |
| L4 扩展 | 4~5 轮（新） | 6~10 | 10~12 | R3 后强制列"未证缺口清单"，R4 逐缺口深挖（≤5 个，输入=缺口非主题）；可选 R5（封顶） | ~40 / 25 |

全档统一两条纪律：
- **收益闸门**：每轮结束统计"本轮新增或推翻的可证伪事实数"，<2 则即使档位未到也停止，报告注明收敛点（出处计数以报告引用行为准）。
- **边界交接**：用户要求超出 L4 → 提示 storm-research-lite（多视角路线），由用户确认切换，不自作主张加码。

**中期**：首跑 L4 后按实测校准预算封顶与 gap 数上限；若重复搜索仍出现，在 R4 契约中加"每条 gap 必须附来源轮次行"。

**长期**：维持三技能分层不变——tiered（轮×量级）、deep-research（fan-out 并行）、storm（视角×矛盾），description 互引路由词。

## 6. 来源列表

- https://github.com/langchain-ai/open_deep_research
- https://github.com/langchain-ai/open_deep_research/blob/main/src/open_deep_research/configuration.py
- https://docs.gptr.dev/docs/gpt-researcher/gptr/deep_research
- https://github.com/dzhng/deep-research
- https://www.anthropic.com/engineering/multi-agent-research-system
- https://arxiv.org/abs/2402.14207
- https://arxiv.org/abs/2510.23458 （BrowseConf，摘要级）
- https://arxiv.org/abs/2506.18959 （Agentic Deep Research 定义，摘要级）
- https://arxiv.org/abs/2606.27009 （Semantic Early-Stopping，摘要级）
- https://openai.com/index/introducing-deep-research/ 及 developers.openai.com deep-research/reasoning 指南
- 本地：~/dev/storm-research/skills/storm-research-lite/SKILL.md（成本基线核实）
