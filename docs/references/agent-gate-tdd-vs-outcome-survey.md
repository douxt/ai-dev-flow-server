# AI Agent 流水线「过程门禁 vs 结果门禁」调研报告（L4）

> **日期**：2026-09-12
> **方法**：gale-research L4（R1 广度 10 路 → R2 深挖 12 源一手 → R3 终裁对抗复查 → R4 缺口递归 5 条全部闭合）
> **场景**：DevFlow 平台的 `stage-gate-block.sh` 用 PreToolUse `exit 2` 强制「写实现文件前必须先有 `TDD: RED` commit」。现有 ADR-009 承认阶段状态不回归（多 ticket 自然流转），导致该门禁在首个 ticket 后失效（UMES3 交接单 P0-1）。本调研为「保留 / 改造 / 替换」决策提供社区与实证依据。
> **硬性排除**：①纯人类 TDD 研究（非 agent loop）②无一手出处的厂商软文 ③无法机械化的"团队文化"类建议
> **读取范围声明**：已完整读取的抓取源见 §7 标注「一手·全文」；`anthropics/claude-code#45427` 的实现代码段（约 900 行 TypeScript/diff）与 `obra/superpowers` README 原文未逐行读取，该两项结论分别标注为「一手·部分」与「二手」。**另：Böckeler 原文（martinfowler.com）因本机域名策略拦截未能直读**，其数字经搜索引擎摘要与三份独立二手转述交叉核对，标注为「二手核对一手」。未读部分不影响本报告结论的**方向**，但影响其**量级**——见 §4.4。

---

## 1. 术语对照表

| 中文 | 英文 | 说明 / 易混淆项 |
|---|---|---|
| 过程门禁 | process gate | 约束「怎么做」（先写测试再写实现）。**分两类**：阶段推进门禁（advance gate，产物齐才准进下一阶段）与**前置条件门禁**（precondition gate，写 X 前必须先有 Y）——DevFlow 的 P0-1 属后者 |
| 结果门禁 | outcome gate / fitness signal | 约束「做出来什么样」（测试能不能拦住 bug），不关心生成顺序 |
| 过程戏法 | process theater | Böckeler 派批评：让 agent 在自循环里跑红绿重构，"no measured payoff" |
| 变异测试 | mutation testing | 改一个实现算子，测试若仍通过则变异体**存活** = 该行为没被约束 |
| 等价变异体 | equivalent mutant | 语法变了行为没变，杀不掉，会拉低分数——**生产环境最大噪声源** |
| 差分变异 | diff-scoped / `--in-diff` mutation | 只变异本次改动行，成本随改动大小而非代码库大小 |
| 覆盖率增量 | coverage delta | **≠ 变异**：删测试会让覆盖率掉，削断言不会（同行执行、覆盖率不变） |
| 故障注入 | fault injection | 向被测代码注入已知故障，看门禁能否抓到；与变异同族，粒度更粗 |
| 规格驱动开发 | SDD (spec-driven development) | 成熟度三级：spec-first / spec-anchored / spec-as-source |
| 奖励黑客 | reward hacking / specification gaming | agent 优化字面指标而非意图；门禁设计的一等威胁 |
| 持久状态机 | durable per-task state machine | 状态存磁盘/DB 而非会话上下文；分 task 级与 step 级 |
| 未验证断言 | unproven vs configured | monkeyleash 的 `status` 用词：区分「钩子被配置了」与「钩子被证明跑过」 |

**须区分**：覆盖率 ≠ 变异得分；test-first 顺序 ≠ 测试质量；结果门禁 ≠ 自动放行（结果门禁同样可以是阻断式）。

---

## 2. 候选对比总表

### 2.1 实证证据（核心决策依据）

| 候选 | 类型 | 方法论 | 关键结论 | 出处 |
|---|---|---|---|---|
| **agentic-dev-team 三臂对照** | 一手实验 | 18 任务 × 3 尺寸 × 3 臂（build-pipeline / test-first / test-after），192 cells，模型固定 sonnet-4-6，隐藏验收测试 | **正确性不分**（全 100%）；**覆盖率/变异不分**（大任务上也仅差 ≤1.6pp / ≤0.013）；**review 缺陷密度：test-first 最差（108），test-after 91，build-pipeline 67**；成本 test-after 三尺寸全最低 | 见 §7 |
| **Böckeler / martinfowler** | 一手实验 | 5 批 × 3 尺寸，Sonnet 4.6 生成 + Opus 4.8 盲判 | "no clearly discernable difference"；非 TDD 解**多次被判设计更好**；token 2.96–8.50×；**TDD 指令阻止 upfront design** | 见 §7 |
| **arXiv 2602.07900** | 一手论文 | SWE-bench Verified × 6 模型 × 500 任务，**提示词控制变量**（诱导/抑制写测试） | 写测试是"模型特有过程风格"，与成功率仅**轻微正相关**（GPT-5.2 写 0.6% 达 71.8%；Opus-4.5 写 83% 达 74.4%；逐模型 resolved 组写测试率一致略高 5–8pp，见 §4.4(c)）；干预后 **83.2% 任务结局不变**；抑制写测试省 32.9–49% input token，仅掉 1.8–2.6%（p 不显著） | 见 §7 · 一手·全文 |
| **TDAD（硕士论文）** | 一手论文 | SWE-bench Verified 100 例，Qwen3-Coder 30B | **TDD 提示词单独使回归率 6.08% → 9.94%（更差）**，分辨率持平 31%；GraphRAG 上下文才降到 1.82%；结论"小模型需要上下文而非流程" | 见 §7 · 一手·全文 |
| **TDFlow（EACL 2026）** | 一手论文 | 子代理测试解析框架 | 给人写测试时 88.8%（Lite）/ 94.3%（Verified）；**瓶颈是"产出好的复现测试"而非"修复"** | 见 §7 |
| **Meta JiT testing** | 工业报告 | PR 时按 diff 生成测试 + 变异引擎验证 | 相比基线生成测试 **bug 检出 4×**（22,000+ 测试，41 issue，8 确认） | 见 §7 |
| **dora Agentic QA POC** | 一手报告 | Rust 项目，三层 QA（PR<15min / nightly<4h / pre-release） | `cargo-mutants` 被称为"**the single most valuable AI-code-specific gate**"；核心失败模式=**同会话写的测试会镜像实现（tautological）**；mutation 37.2%→43.4% | 见 §7 · 一手·全文 |
| **monkeyleash 自述** | 一手（n=1） | 单人项目，148 条 friction log | "**六道门禁在四十多次改动中被静默跳过**"——与我们的 P0-1 **同构**；设计：PreToolUse（outpost，可被宿主关）+ pre-commit（authority，结构性）双layers | 见 §7 · 一手·全文 |

### 2.2 门禁机制候选（若走结果门禁）

| 机制 | 判定性质 | 成熟度 | 关键约束 |
|---|---|---|---|
| **diff-scoped mutation**（`cargo-mutants --in-diff` / `stryker --since` / mutmut 覆盖面引导） | 结构性、可阻断 | 已采纳（gitlocus ADR 0015） | 成本随改动大小；**超时必须记 inconclusive 绝不算 pass**；不记全局分数（会被 farm） |
| 全量 mutation 门禁 | 结构性 | 成熟但慢 | **不可上 PR 路径**（Dora +30min/PR；Zenseact 工业研究建议 commit 级 + 选择性工具；Facebook 仅 ~50% 开发者会处理报出的变异体） |
| g0 式故障注入（DevFlow 已有） | 结构性 | 已落地 | 与 mutation 同族、粒度更粗、无需新工具链——**是 P1-3 提的"结果导向替代"的现实候选** |
| 覆盖率 / diff-coverage | 结构性 | 成熟 | **不足以替代**：削断言时覆盖率无信号（gitlocus 实证） |
| LLM 对抗审查 | 概率性 | 成熟 | 本机 dora 报告认为"不同模型读你的 diff"能抓作者模型的盲点 |

### 2.3 平台/框架（设计参考，非证据）

| 项目 | 与我们的关系 |
|---|---|
| monkeyleash | 同构问题（门禁静默跳过）+ 双 layer 设计（outpost/authority）+ "configured vs proven" 状态区分 |
| cortex-x | mutation 阈值治理范式：measure-first（`break: null` 观察 2 周）→ `baseline - 2pp` → 季度单向上调；**fail-OPEN**（信号缺失不阻断）|
| gitlocus | diff-scoped 变异 + 不记全局分 + 诚实记录盲区（两步走绕过）|
| Superpowers | 强制派最大声量代表，**但无独立大规模证据**（详见 §5-G1）|
| Hermes/toolGate RFC | 记录了 PreToolUse 的五个失效模式（子代理绕过/静默失败/模型自改/Bash heredoc 绕过/CLAUDE.md 非遵从），**RFC 状态 closed+stale，未落地** |

---

## 3. 排除清单及原因

| 候选 | 排除原因 |
|---|---|
| Superpowers 的 star 数论证（95K–275K 各源不一） | 影响力非证据；且有源证实"3 天 26 万星"系伪造。**工具本身不排除**（见 §5-G1），排除的是以 star 数作证据 |
| SDD 工具选型对比（Spec Kit / Kiro / BMAD / Tessl） | 与"门禁该管过程还是结果"弱相关；仅保留结论：刚性阶段门禁被批为"**waterfall in markdown**"、小改动 4–5× 税、greenfield 偏向弱于 brownfield |
| 纯人类 TDD 文献 | 预置硬性排除 |
| 中文二手转述（jianshu/51cto/segmentfault） | 仅作线索，不作证据；其转述的 Böckeler 数据已用英文一手核对，数字一致 |
| Cursor/OpenAI marketplace 上的 skill 分发页 | 滞后于上游，不可作版本依据 |
| 厂商产品页（claude-gates npm 等） | 仅作"该品类存在"的存在性证据 |

---

## 4. 关键技术判断

### 4.1 分化点（一票决定选型的字段）

**分化点 A：门禁测的是「生成顺序」还是「测试的杀灭能力」。**
这是全部证据汇聚的唯一分水岭。四份独立来源（Böckeler / agentic-dev-team / arXiv 2602 / TDAD）在不同模型、不同基准、不同方法论下得到同向结论：**约束顺序不改变结果质量**；而 dora、gitlocus、Meta、cortex-x 的实践则一致表明：**约束"测试能不能拦住 bug"才改变结果**。Böckeler 给出了机理——TDD 指令**阻止 upfront design**，设计退化为"第一个测试锁定的形状"；agentic-dev-team 的 review 面板独立印证这一点（test-first 在 complexity 维度失分最多）。

**分化点 B：粒度。** 同一份 mutation 机制，per-PR 全量 vs diff-scoped 是两个完全不同的东西——前者被 Dora（+30min/PR）、Zenseact（工业研究）、Facebook（噪声使人放弃处理）一致否决；后者是 gitlocus 已采纳的工程决策。**"要不要上 mutation 门禁"这个提法本身是错的，正确提法是"diff-scoped 还是 nightly"。**

**分化点 C：resolution rate 是误导性指标。** TDAD 论证：一个"修好一个问题、引入三个回归"的补丁在 resolution 口径下是正收益。它提议 `net = resolution − α·regression`（α>1，反映回归的非对称代价），并引用 METR：**维护者复核 296 个 SWE-bench 通过补丁，约一半不会被合并**，回归与代码质量是主要拒绝理由。**这对我们的直接含义：UMES3 的"stage 到达率"同样不能当质量代理。**

### 4.2 采购/落地前必测项（换成我们自己的验证条件）

| # | 必测项 | 理由 |
|---|---|---|
| 1 | 强制 TDD 在 **DeepSeek V4 flash** 上的表现 | 全部外部证据都在 Anthropic/OpenAI 模型上取得；arXiv 2602 恰好实测了 deepseek-v3.2-reasoner：**它是"高写测试"型（89.2%）**，说明该类模型天然倾向写测试，**强制门禁对它的边际价值最低、开销最高**（抑制写测试可省 32.9% input token，成功率仅掉 1.8%）|
| 2 | 现有套件在 mutation 下的**基线分数**与单次运行耗时 | cortex-x 范式要求先 measure 再设阈；无基线就设 80% 会直接红 |
| 3 | Python 侧工具选型：**mutmut（~7–8 变异体/秒，覆盖引导，复制到 `./mutants/` 不动工作树）vs cosmic-ray（~0.08/秒，全量重跑，原地改源）** | **90× 性能差**；cosmic-ray 原地改源会在中断时留脏树——**与本机 file-guard/bash-firewall 沙箱直接冲突**。mutmut v3+ 仅变异函数内代码，且**仅 Unix/WSL**（本机 WSL，可行） |
| 4 | g0-inject.sh 能否升格为门禁（而非预检项） | 无需引入新工具链；已有实现是最大优势 |
| 5 | 遗留代码库（UMES3 场景）中 diff-scoped 变异是否误伤 | gitlocus 的论证：`--in-diff` 只变异改动行，不惩罚未改的历史欠债——**这正是它能落地在既有代码库的原因**；但需实测确认我们的 changeset 划分正确 |

### 4.3 建议勿改坏的部分（外部证据支持保留）

- **确定性 hook 层本身**：`exit 2` 是 Claude Code 唯一可靠阻断；advisory 警告 = 不存在（与社区共识、我们的既有认知一致）。
- **GREEN 窗口反作弊（禁改测试文件）**：与 gitlocus 的"门禁必须抵抗它所门禁之物"同构，属正确方向。
- **g0 故障注入**：与 dora 的"mutation 是最有价值的 AI-code 门禁"、Meta 的 4× 检出同源，**是平台最该保留并强化的资产**。
- **不记全局 mutation 分数**：gitlocus 明确"a score would be a number to farm"，与我们的门禁防博弈取向一致。

---

### 4.4 证据强度自评（本报告的三处自我限制）

**(a) 「耗时费 token」的量级证据是分裂的，不可只引最极端格。**

| 来源 | test-first 相对成本 | 可读性 |
|---|---|---|
| Böckeler | **2.96×–8.50×** | 小任务 8.50× / 中 2.96× / 大 4.89×，n=2–6/格 |
| agentic-dev-team | **1.08×–1.55×** | 仅 medium 显著（p=0.031），small/large 统计上**不显著** |
| arXiv 2602（诱导写测试） | +5.5% API calls / **+19.8% output tokens** | 低写测试模型上 |

三者相差 2–6 倍。方向（强制 test-first 更贵）一致，**量级无共识**。引用时若只取 Böckeler 的 8.50×，等于取了同一实验中最极端的格子。

**(b) 「效果不好」必须拆维度，不能笼统。**

| 维度 | 结论 |
|---|---|
| 正确性 / 分辨率 | **无差异**（三份独立证据一致） |
| 测试质量（覆盖率 / 变异分） | **无差异**（agentic-dev-team 大任务上 ≤1.6pp / ≤0.013） |
| 代码结构（review 面板） | **test-first 最差**（加权 108 vs test-after 91 vs pipeline 67）→ 负收益 |
| 回归率 | **TDAD：上升**（6.08% → 9.94%）→ 负收益，但单模型 30B / 100 例 |

准确表述为「**无收益，部分维度负收益**」，而非「效果差」。且 Böckeler 原文自陈"数据集太小，无法定论"。

**(c) arXiv 2602 的「测试写书与成功率弱相关」措辞需精确化。**
其 Table 1 逐模型数据显示：**每个模型 resolved 组的写测试率都一致地略高于 unresolved 组**（deepseek-v3.2-reasoner 92.3% vs 84.5%；claude-opus-4.5 84.4% vs 78.9%），差幅 5–8pp。论文正文表述为 "broadly similar"，本报告 §2.1 沿用为"弱相关"。严格说应为**轻微的、全模型一致的正相关**——它不足以支持"写测试有用"，但也不支持"完全无关"。

**(d) 最重要的限制：没有任何一条证据产生于我们的条件下。**
全部实验为 greenfield、单模型、小样本；且**形态不同构**——Böckeler 测的是"让 agent 在自循环里跑完整红绿重构"，本平台的门禁只强制"写实现前必须有 RED commit"，约束窄得多。落到"我们的模型（DeepSeek V4 flash）+ 我们的门禁形态"，只能本机对照实验（即 §5 的 Q1）。

---

## 5. 缺口裁决表（L4）

| # | 缺口 | 产生于 | 闭合动作 | 结论 |
|---|---|---|---|---|
| G1 | Superpowers（强制派最大声量）是否有支撑其主张的证据？ | R1/R2 | 定向检索其 eval、Tessl 外部评估、社区批评 | **未闭合（负面）**：自有 eval 五 agent 通过率 71–84%，**但无 vanilla 对照组**（只测"遵守度"不测"改善度"）；Tessl 外部小样本 `verification-before-completion` 1.22× 而 `brainstorming` 仅 1.05×；启动 ~22K token（≈11% 上下文）；**删掉 TDD skill 中一段说明文字，test-first 行为从 8/10 掉到 5/10**（效应脆弱）；有用户报告装上后模型出错更多。**判定：强制派的代表工具无独立大规模证据支撑其核心主张** |
| G2 | arXiv 2602（测试无用）与 TDAD（test-first 更多回归）方向冲突，如何调和？ | R2 | 检索第三、四方证据 | **已闭合**：分歧源于被测的"测试种类"不同——①任务内自写、用完即弃的测试（2602：对 resolution 无益，主要是 `print` 观测）②test-first 流程提示（TDAD：回归率升）③**提交进仓库的持久 AI 测试**（Yoshimoto 2,232 commits：断言密度更高、复杂度更低、覆盖率与人类相当）④差分/baseline-aware 门禁（Phoenix：零 pass-to-pass 回归，**但前提是套件本身能抓语义错误**，弱套件上约 20% 通过测试的补丁语义仍错）。**含义：要约束的不是"写不写测试"，而是"提交的测试是否有杀灭力"** |
| G3 | DeepSeek 系模型（UMES3/cut-optimizer 实际驱动）的测试行为 | R1 | 定向检索 arXiv 2602 的模型级数据 | **已闭合**：deepseek-v3.2-reasoner 在 6 模型中属**高写测试组（89.2%）**；抑制其写测试 → 75.2% 任务翻转、input token −32.9%、API 调用 −24.5%，而 resolution 仅 60.0%→58.2%（**p=0.435 不显著**）。**该类模型天然倾向写测试，强制门禁边际收益最低** |
| G4 | Python + 遗留库上 mutation 的落地成本 | R2 | 定向检索 mutmut/cosmic-ray 实测对比 | **已闭合**：mutmut ~7–8 变异体/秒 vs cosmic-ray ~0.08/秒（**90×**）；mutmut 复制项目到 `./mutants/` 不动工作树、cosmic-ray 原地改源（中断留脏树，与 sandbox hook 冲突）；业界共识=**全量 nightly、diff-scoped 上 PR**；阈值不设 100%，**只卡 diff 内新存活变异体** |
| G5 | CC hook 层是否有既有的"按任务重置阶段状态"实现？ | R2 | 定向检索 CC hook 状态机实现 | **已闭合（无现成件，但有范式）**：Claude Code 无原生机制；社区做法有二——① `SubagentStart` 钩子在 agent 启动前把 worktree 重置到 main SHA（anthropics/claude-code#51545）② 任务/工作树**双状态机 + 事件日志**（`.worktrees/events.jsonl`，崩溃后从磁盘重建，原则"session memory is volatile; disk state is persistent"）。**直接对应我们的 P0-1 修法：阶段状态应 worktree 本地化 + 事件留痕，而非 git 跟踪的全局单值** |

---

## 6. 推荐结论

### 6.1 总判断

**外部证据不支持"强制 test-first 门禁"作为质量门禁，支持把它降级为可选工作流，并把门禁预算转移到"测试杀灭力"这一结果信号上。**

一句话机理（Böckeler + agentic-dev-team 互证）：**强制顺序买不到质量，只买到 token 与结构损失**；而**测试能否拦住 bug 是覆盖率买不到的、且可机械判定的信号**。

### 6.2 分期建议

**短期（本平台，与 P0-1 修复合并处理）**
1. **P0-1 不必"给状态机加重置"**——若采纳中期方向，这条门禁将被替换；若暂缓，则按 G5 范式改为 **worktree 本地 + 事件日志**，而非继续用 git 跟踪的全局单调值。
2. **先把 g0-inject 从"预检项"升为"必过门禁"**，再谈 `/tdd` 是否必经。顺序不能反：UMES3 的 F22 事故（Agent 跳过 /tdd → 4 个功能无 E2E 覆盖）正是裸降级的后果，而 g0 恰好是那次事故的解药（它不管流程、只管"测试能不能拦住故障"）。
3. **`/tdd` 转"按需 + 留痕"**：跳过需在 ticket 上写明理由（如遗留代码走 `/characterize`），把"跳过"从静默变成可审计。

**中期（验证后）**
4. **引入 diff-scoped mutation 作为新门禁，先 measure-only**（cortex-x 范式）：跑 2 周只报不拦 → 取基线 → 设 `基线 − 2pp` 的回归检测阈值 → 只单向上调。
5. **Python 侧选 mutmut**（性能 90×、不动工作树）；**绝不进 PR 路径做全量**。
6. **门禁口径改为双指标**：resolution/完成率 **与** 回归率并列报告（TDAD 提议 `net = resolution − α·regression`），避免"完成即成功"的错觉。

**长期**
7. 把"测试杀灭力"做成平台的**一等验收信号**（cortex-x 的第七种 acceptance criterion 范式），与 dora 的"不同模型对抗审查"组合成结果门禁层。
8. 定期用外部证据复核：本调研的断言时效性强（模型 3 个月一代），**"强制 TDD 无用"的结论绑定在特定模型强度上**——作者本人也承认"随模型变强，外部脚手架可能冗余"。

### 6.3 对 UMES3 交接单 P1-3 的回应

其引用的外部证据**转述准确、无夸大**，且本调研补充了三点它未覆盖的适用性限制：①实验**全部 greenfield**，而 UMES3 走 `/characterize` 遗留路径；②被测模型与我们的驱动模型不同，而 arXiv 2602 恰好实测了 DeepSeek 系——**结论对我们是加强的**（该类模型天然高写测试，强制边际价值最低）；③**它是这条门禁的起因**（F22），裸降级会重演该事故——**正确做法是"换门禁"而非"拆门禁"**。

---

## 7. 来源列表

**一手·全文**
- agentic-dev-team 三臂对照报告 — https://raw.githubusercontent.com/bdfinst/agentic-dev-team/main/docs/experiments/01-final-results.md
- arXiv 2602.07900《Rethinking the Value of Agent-Generated Tests》— https://ar5iv.labs.arxiv.org/html/2602.07900
- gitlocus ADR 0015「Mutation testing is what resists gate gaming」— https://raw.githubusercontent.com/hey-vera/gitlocus/refs/heads/main/docs/adr/0015-mutation-testing-is-what-resists-gate-gaming.md
- cortex-x mutation-testing 标准 — https://raw.githubusercontent.com/Rejnyx/cortex-x/refs/heads/main/standards/mutation-testing.md
- monkeyleash README — https://github.com/wusuowei-tw/monkeyleash
- agentpatterns「Mutation Testing as a Quality Gate」— https://agentpatterns.ai/verification/mutation-testing-quality-gate/
- TDAD（硕士论文仓库）— https://github.com/pepealonso95/TDAD
- dora Agentic QA POC 报告 — https://raw.githubusercontent.com/ronaldgosso/dora/refs/heads/main/docs/qa-poc-report-2026-04-09.md
- Anthropic toolGate RFC #45427（状态 closed+stale）— https://github.com/anthropics/claude-code/issues/45427
- agent-governance-framework — https://github.com/Wiktor-Potapczyk/agent-governance-framework

**一手·部分 / 二手**
- TDFlow（EACL 2026）— https://aclanthology.org/2026.eacl-long.70/
- Superpowers 评估（developertoolkit.ai）— https://developertoolkit.ai/en/shared-workflows/skills-ecosystem/superpowers/
- Superpowers 资源评估（alexica00）— https://github.com/alexica00/claude-code-ultimate-guide/blob/main/docs/resource-evaluations/obra-superpowers-evaluation.md
- Superpowers 卸载潮（中文）— https://juejin.cn/post/7662691781214437412
- Yoshimoto 等（AI 测试 vs 人类测试，2,232 commits）— 转引自 https://www.devassure.io/blog/agent-generated-tests-barely-help/
- Phoenix baseline-aware 测试评估 — https://agentpatterns.ai/verification/baseline-aware-test-evaluation-issue-resolution/
- agentpatterns「Prescribing TDD Inside the Agent Loop (Process Theater)」— https://agentpatterns.ai/patterns/anti-patterns/tdd-inside-the-agent-loop/
- Martin Fowler — https://martinfowler.com/articles/exploring-gen-ai/tdd-in-the-agent-loop.html
- Meta JiT testing — https://www.infoq.com/news/2026/04/meta-jit-testing-ai-detection/
- Python mutation 工具对比（vera 项目实测）— https://github.com/aallan/vera/blob/4f016e2f2d1eefe2f31b0bebd05a69efbc04d01d/MUTATION.md
- Claude Code worktree 状态机与 SubagentStart 刷新 — https://github.com/anthropics/claude-code/issues/51545
- learn-claude-code s12 任务/工作树双状态机 — https://gitcode.com/yang520java/learn-claude-code/blob/main/docs/zh/s12-worktree-task-isolation.md
- TruePPM mutation 定时任务实践 — https://gitlab.com/trueppm/trueppm/-/work_items/1308
- agent-glovebox CI 变异分片与缓存 — https://github.com/AlexanderMattTurner/agent-glovebox/blob/caabef4d2222f0c57c1127d319f0428a3e3d348e/CLAUDE.md
- rjmurillo/ai-agents 确定性 hook 改造 — https://github.com/rjmurillo/ai-agents/issues/1726
- Deterministic AI Orchestration 八层强制栈 — https://securityboulevard.com/2026/02/deterministic-ai-orchestration-a-platform-architecture-for-autonomous-development/
- 中文：TPDD 高层测试闭环 — https://www.infoq.cn/article/dOWkTbkLXRmMJvsCddcy
- 中文：用结果反馈替代强制 TDD（Böckeler 译文）— https://blog.51cto.com/FunTester/14859062
