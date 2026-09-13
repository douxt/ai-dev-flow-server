# 「强制 TDD 门禁」社区实践动向调研（L4）——E0 决策的资讯面输入

> **日期**：2026-09-12 · **方法**：gale-research L4（R1 广度 10 路 → R2 深挖 → R3 终裁 → R4 缺口递归），实际动作 14 搜索 / 8 抓取（预算内）
> **核心假设（用户提出，可证伪）**：Claude Code × DeepSeek/Qwen 用户基数巨大，我们的场景（agent 流水线要不要强制 TDD）非常常见——**若实验室结论真的大到不适用于我们，社区不可能没有动静**。
> **假设判定**：✅ **成立且超额兑现**——社区不仅"有动静"，而且动静本身就是这场辩论（Superpowers 卸载潮、Böckeler 帖的 HN/LinkedIn 攻防）。同时发现**动静是单向的**（§4.1），这是全报告最强的信号。
> **硬性排除**：无实践记录的纯观点文、star 数论证、明显 SEO/AI 生成的推广文（DeepClaude dev.to 一文即属此类，已排除出证据链，见 §3）
> **读取范围声明**：一手·全文 = 完整读取（Tornhill 全文、#750 全文、#1803/HN/摘要部分读取——已读部分逐节标注）；Reddit/HN 正文经检索摘要转引的标注「摘要转引」。所有关键结论至少两条独立来源。

---

## 1. 术语对照表

| 中文 | 英文 | 区分项 |
|---|---|---|
| 环内 TDD | TDD inside the agent loop | agent 自循环里跑细粒度红绿重构——Böckeler 否定的是这个 |
| **环外 TDD** | TDD outside the loop | **人定失败测试、agent 只管让它变绿**——Holub 等实践者主张、社区公认有效的这个 |
| 红绿记账法 | double-entry bookkeeping (Tornhill) | 一切改动必须由一个失败测试驱动；防 agent 删测试/改断言凑绿 |
| 卸载潮 | uninstall wave | "why I removed superpowers"、"still using?"、"absolute garbage" 帖群 |
| 门禁沉降 | enforcement layer shift | 从 PreToolUse（可被绕过/忽略）沉到 git pre-commit（结构性） |
| 门退回滚 | gate-then-revert | Cashu：上 PR 级变异门禁 → 撤下 → 改定时+窄域本地检查 |
| 绿色≠可信 | green tests ≠ trustworthy | "both runs reached ten passing tests" 而信任度不同——弱模型时代的核心问题 |

**须区分**：①"强制 TDD 顺序"≠"有测试"②"环内细粒度循环"≠"失败测试前置"③"mutation 门禁失败（PR 级全量）"≠"结果门禁失败（窄域注入）"——本轮社区证据的解读分歧全部源于这三组混淆。

## 2. 候选动静总表（实践面，逐条可证伪）

### 2.1 强制过程侧的动静（卸载与自认）

| 证据 | 出处 | 强度 |
|---|---|---|
| **Superpowers 维护者 obra 自认**：adversarial review 在 5.0 上线后"got a lot of hate from end users about the additional performance hit and token spend"→ 被迫撤下 | #1803 维护者评论（一手全文） | 🔴 利益相关方的反向自认，最强级 |
| obra 同帖承认 subagent-driven-development 被强制后"用更多 token、交付更差结果"的用户反馈，并在 dev 分支**恢复 executing-plans 选项** | #750（一手全文） | 🔴 同上 |
| 用户实测：跳过 Brainstorm 的 spec-review 环节 = **同任务省 50% 用量** | #750 lucas-grunevald | 一手 |
| Codex 用户：装 Superpowers 时"6 小时烧掉周额度 80%；删掉后 6 小时用了 3%" | r/OpenaiCodex（摘要转引） | 一手 |
| 「not a fan」帖 105+ 赞；「absolute garbage」帖；「why I removed superpowers」帖成簇 | r/ClaudeCode（摘要转引） | 群体趋势 |
| 官方应对：#832 全部 14 skills 砍 69% 行数"无损失"；v6 release notes 自报**约 2× 快、~50% 省 token** | superpowers repo | 维护者侧 |
| **RigorBench**（学术）：**"tool-enforced frameworks fail to improve baseline process metrics"**；过程纪律与结果正确性的相关**在任务层不显著** | arXiv 2606.22678 摘要（一手） | 与四份实验证据同向 |

### 2.2 反向动静缺失（本报告的裁决性发现）

| 检索 | 结果 |
|---|---|
| "移除 TDD 门禁后回归/事故增加"的第一人称实践报告 | **检索不存在**（三轮改写查询）。唯一"没有验证就出事"的事故群（Replit 删库等）根因全是**无权限围栏/无验证层**，无一例归因于"撤掉了 test-first 顺序要求" |
| 对 Böckeler 的"没复现/翻案"攻击 | **无人主张复现失败**；反驳全部走"她测的不是我们用法的 TDD"路线（Holub："Not in my experience"——他做的是**环外** TDD：人写测试、AI 过测试） |

**含义**：动静的不对称本身就是数据——**拆过程门禁拆出事的人不存在，被过程门禁烧到的人在卸载**。

### 2.3 结果门禁侧的动静（B 路线的真实下场）

| 证据 | 内容 | 对我们的含义 |
|---|---|---|
| **Cashu**（开源 ecash） | 定时 Stryker（#733）→ **PR 门禁（#754）→ 撤销门禁（#773）**。死因：继承性 survivor、基线过期、10–90 分钟无反馈的 PR 运行拖垮流程。保留形态：**定时跑 + 窄域本地检查** | PR 级**全量**变异门禁在小项目也失败；但死的是"全量+同步+无机器人反馈"，**不是"结果信号"本身** |
| **OpenHands** | 选 on-demand 报告（全库或仅变更），**明确不上 CI 门禁** | 同上收敛点 |
| mutating.tech 7 月月报 | PIT 活动 12 个 PR：7 合并 5 被关闭（重复覆盖/越抽象层/过度指定）——"Agents proposed; maintainers decided" | 变异反馈进 agent 循环需要人裁，不是裸自动 |
| 知乎百万行项目实践 | "Agent 贴着自己的代码写测试，永远能通过，毫无验证价值"；结论要"测试先行且**人验证测试**" | 与 arXiv 2602/环外 TDD 完全互证 |
| CodeMiner42 | "a quality gate that lies to you is worse than no gate at all" | 门禁宣称与实效一致原则（我们 P0-1 的同族教训） |

### 2.4 强制层位置的动静（直接影响 DEFECT-015 修法）

| 证据 | 内容 |
|---|---|
| **HN "Claude 4.7 is ignoring stop hooks"**：109 分 90 帖——带 MANDATORY 全大写文案的 stop hook 被模型反复无视 | 模型层自觉不可靠的社区实锤（约束力归属之争，UMES3 §三 的社区版） |
| **#34692**（子代理不触发 Pre/PostToolUse hooks）**closed as `not_planned`**；后续 #43612/#40580/#33049 持续报同一缺口；文档声称已修而行为报告相反 | 我们 P2-1 的官方定论：**outpost 层有结构性洞**，权威层必须下沉 git hooks——恰好是我们 v3.6 pre-push/pre-commit 角色门所在的层 |

### 2.5 DeepSeek/Qwen 侧的动静（回答"实验是否不适用我们"）

| 证据 | 内容 |
|---|---|
| nateherk 百小时实测（DeepSeek Harness vs Claude Code） | "DeepSeek 快，Claude Code 可信"；**DataCamp 同题对比：两边都以'十项测试通过'收场而产出信任度不同** |
| r/LocalLLaMA harness showdown | 同用 DeepSeek V4 Flash，**质量跨 harness 基本一致**（harness 不重要、模型重要）；Claude Code ~70 tool calls vs OpenCode ~22 |
| arXiv 2602（已有） | deepseek-v3.2-reasoner = 高写测试组（89.2%），抑制其写测试几乎无损 |
| V2EX Qwen 帖群 | 能跑、便宜，弱在长上下文与多轮工具调用；**无一人报告"给 Qwen 加强制 TDD 后变好"** |

**小结**：我们最担心的"实验条件不同构"在弱模型侧**方向相反**——弱模型的自写测试更不可信（绿色≠可信更严重），**结果门禁对 DeepSeek 类模型比对 Sonnet 更重要，不是更不重要**。

## 3. 排除清单及原因

| 候选 | 排除原因 |
|---|---|
| DeepClaude dev.to 长文（"Claude Code + DeepSeek loop"，含测试覆盖率对比表） | 结构含推广尾帖（moonshift 广告评论）、无可复现方法、疑似 AI 生成——**SEO 文不作证据** |
| Julian Goldie / dutchstartup 等视频转述 | 二手转述无原始数据 |
| YouTube "TDD is OP"类 | 观点非记录 |
| Superpowers star 数/市场热度叙事 | star≠效果（前两份报告已判） |
| 「已证伪」检索：「removed TDD gate → regressions spiked」第一人称报告 | **搜不到=不存在**，如实记录为缺失（这构成 §2.2 的不对称发现本身） |

## 4. 关键技术判断

### 4.1 分化点：社区辩论真正的分界线不是"要不要测试"，而是**谁定测试、在哪定**

把全部社区动静按"环内细粒度 / 环外粗粒度 / 顺序强制 / 结果强制"重排后，**没有一条动静支持"在 agent 循环内强制细粒度红绿+顺序前置"，而有大量动静支持"失败测试前置但由人/上层定规格"**（Holub、Tornhill 的 double-entry、r/ClaudeCode 多数派"人审测试、agent 过测试"）。

**这直接改写了 E0 的选项地图**——我们那条"写实现前必须有 RED commit"的门禁恰好骑在分界线上：它是**粗粒度失败测试前置**（社区幸存派支持的形态），但被文档/宣称包装成了**细粒度 TDD 强制**（社区卸载的对象）。**门禁形态可能是对的，宣称错了。**

### 4.2 对 E0 三选项的社区初步裁决

| 选项 | 社区裁决 |
|---|---|
| **A 保留强制细粒度 TDD** | 🔴 无社区支持样本；唯一旗舰（Superpowers）因 token 反噬被迫三次瘦身，且无自有对照组 |
| **B 直接换结果门禁** | 🟡 方向被社区采纳（g0/mutation 阵营），但**PR 级全量形态已被 Cashu/OpenHands 实测否决**——必须窄域/diff 级 + 异步 + 机器人反馈，否则同样被撤 |
| **C 先实验** | 🟢 **社区情报把实验的问题改窄了**：不再是"要不要 TDD 门禁"（方向已定），而是"我们的粗粒度 RED 前置 + g0 组合是否成立、成本几何"（§6） |

### 4.3 强制层的教训（比 A/B/C 更普适）

outpost（PreToolUse/Stop hook）被社区实锤三种失效：**模型无视**（HN 109 分帖）、**子代理穿透**（#34692 not_planned）、**钩子可被改写**。凡要留任何门禁，权威判定必须落在 git hooks / CI 层——我们 v3.6 已把角色门放对了层，**但 stage-gate 全在 outpost 层**，DEFECT-015 无论修还是废，这条约束都要吸收进新门禁（g0 的必过判定应同时挂 pre-commit/AFK 管线，不只挂 PreToolUse）。

### 4.4 采购/实验前必测项（更新 E1 协议）

1. **E1 的 B 臂定义要改**：不是"关门禁裸奔"，而是"失败测试前置保留、细粒度循环宣称删除、g0 升必过"——测的是**宣称修正**的效果与成本（与社区幸存形态对齐），这才对得上决策问题。
2. g0 门禁上岗前跑 **seed recall + 假阳性率体检**（上份报告 §4.5），且**异步化**（Cashu 教训：同步 PR 级 = 被撤）。
3. 任何新门禁上线时**文档宣称必须与实效同层核对**（"lie 的门禁比没有更糟"——CodeMiner42 + 我们 P0-1 双证）。

## 5. 缺口裁决表（L4）

| # | 缺口 | 闭合状态 | 证据 |
|---|---|---|---|
| G1 | 有无"撤过程门禁→变差"的反向动静 | **已闭合（负结果=不对称证据）** | 三轮改写检索无第一人称报告；事故群根因均非顺序门禁 |
| G2 | Superpowers 官方对 token 反噬的处置 | **已闭合** | #1803 维护者自认撤功能、#750 恢复选项、#832 砍 69%、v6 自报 50% 省 |
| G3 | 结果门禁（mutation）实践的真实下场 | **已闭合** | Cashu #733→#754→#773 上而又撤，存活形态=定时+窄域；OpenHands 明确不上 CI 门禁 |
| G4 | 子代理 hook 洞官方定论 | **已闭合** | #34692 closed not_planned + #43612/#40580 续报；文档-行为不一致仍"未解决" |
| G5 | DeepSeek 系"强制 TDD 有害/无益"有无直接实测 | **部分闭合** | nateherk/DataCamp 显示"测试绿而不可信"主题普遍，但**无人做过 DeepSeek × TDD 门禁的对照实验**——社区同样缺这份数据，**E1 若做成即为该缺口的首个公开数据点** |

## 6. 推荐结论（E0 的社区初步答案）

**社区资讯面可以得出初步结果，方向明确但精度有限：**

1. **纯 A（保留细粒度强制）无社区样本支持，可判死**。卸载潮 + 维护者自认 + RigorBench 三面合围。
2. **B 的"全量 mutation 上 PR"变体也被社区判死**（Cashu/OpenHands）；活下来的 B 形态 = 定时/窄域/异步的结果检查。
3. **社区最大公约数是一种"修正后的 C 偏 B"**：粗粒度失败测试前置**保留**（Tornhill double-entry / Holub 环外式——注意这与我们的现有门禁形态同构！）+ 细粒度 TDD 宣称**删除** + g0 类结果信号升格但**异步窄域化** + 强制层下沉 git hooks。
4. **给 E0 的建议**：C 仍是最优，但 **E1 实验协议按 §4.4 修正**——问题从"要不要这道门"收窄为"这道门改成社区幸存形态后，宣称/成本/杀灭力各变多少"。且 G5 提示：**这个实验做完，我们就是社区里第一个有 DeepSeek 系数据的人**——实验的外部价值也成立了。
5. 一句话总评：**你的"社区不可能没动静"假设不仅成立，动静本身就是答案——社区用卸载行为投票已经完成了 E0 的大部分，剩下一小步（粗粒度 RED 前置是否保留）才是实验要测的。**

## 7. 来源列表

**一手·全文**
- obra/superpowers #750（维护者自认+用户实测）— https://github.com/obra/superpowers/issues/750
- Adam Tornhill《Practices I Abandoned with Agents: An Ode to TDD》(2026-09-03) — https://adamtornhill.substack.com/p/practices-i-abandoned-with-agents
- RigorBench 摘要 — https://arxiv.org/abs/2606.22678

**一手·部分（长文本取关键节，其余按未读处理）**
- obra/superpowers #1803（adversarial review 撤下自认在 3.3k 字内已读）— https://github.com/obra/superpowers/issues/1803
- HN Böckeler 讨论帖（全 4 评论已读）— https://news.ycombinator.com/item?id=49262349
- mutating.tech 2026-07 月报（Cashu/OpenHands/PIT 活动段已读）— https://mutating.tech/blog/the-mutation-testing-digest-for-july-2026/
- Tell HN: Claude 4.7 ignoring stop hooks — https://news.ycombinator.com/item?id=47895029
- Claude Code #34692/#43612/#40580/#33049 子代理 hook 洞簇 — https://github.com/anthropics/claude-code/issues/34692

**摘要转引（Reddit/HN/知乎，正文经检索引擎节选）**
- r/ClaudeCode: Those doing TDD are you really / not a fan / absolute garbage / why I removed / TDD workflows what's actually working / TDD never worked for me
- r/OpenaiCodex: weekly usage limit burned；r/LocalLLaMA: harness showdown；r/AI_Agents: incident/verification 帖群
- nateherk 100 小时（X 文+视频）— https://x.com/nateherk/article/2091669829883138512 ；DataCamp 对比 — https://www.datacamp.com/blog/deepseek-harness-vs-claude-code
- Allen Holub 反驳帖 — https://x.com/allenholub/status/2087698126119330166 ；Marc Love — https://marclove.com/blog/2026-01-07-tdd-in-an-agentic-world/
- CodeMiner42 自验证 Rails — https://blog.codeminer42.com/how-far-can-ai-self-validate-rails-code/ ；VirtusLab CI lies — https://virtuslab.com/blog/ai/your-ci-lies-too/
- 知乎：百万行工程半年 Agent 踩坑 — https://zhuanlan.zhihu.com/p/2023459529610855161 ；AI 写代码快了 30% 交付反而慢了 — https://zhuanlan.zhihu.com/p/2042928107460497825
- V2EX Qwen3-Coder 帖群 — https://www.v2ex.com/t/1147506
- obra/superpowers #762/#190/#1648/#2017/#832、v6 release notes — https://github.com/obra/superpowers/issues/762 等
- martinfowler.com Böckeler 原文（数字经 §4.4(b) 复核链）— https://martinfowler.com/articles/exploring-gen-ai/tdd-in-the-agent-loop.html
- agentpatterns 过程戏法条目 — https://agentpatterns.ai/patterns/anti-patterns/tdd-inside-the-agent-loop/
