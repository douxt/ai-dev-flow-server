# AI Agent 流水线对照实验设计方法学调研（L4）

> **日期**：2026-09-12
> **方法**：gale-research L4（R1 广度 10 路 → R2 深挖 10 源一手 → R3 终裁 → R4 缺口递归 5 条全部闭合）
> **场景**：为 DevFlow 设计一次**本机可执行**的对照实验，检验「强制 RED commit 前置」门禁的效果与成本。这是 UMES3 反馈 P1-3 的前置条件——外部证据方向可信但强度不足以单方决策（详见 `agent-gate-tdd-vs-outcome-survey.md` §4.4）。
> **本机硬约束**（后续每轮据此筛除）：单机 WSL、**串行**、驱动模型 **DeepSeek V4 flash**（非 Anthropic）、**真实 ticket 数量有限**、无专职评测人力
> **硬性排除**：①需集群/专有数据的方案 ②无一手实验记录的营销型 benchmark ③纯人类 TDD 实验方法学（除非方法可直接搬）
> **读取范围声明**：§7 标注「一手·全文」者为完整读取；`mdredd` 仅读 README 前半（其隔离设计取自检索摘要，标「一手·部分」）。KTH 论文经 ar5iv 全文读取（52KB 版本，含 Appendix A 功效分析）。

---

## 1. 术语对照表

| 中文 | 英文 | 说明 / 易混淆项 |
|---|---|---|
| 单次通过率 | pass@1 | **名字像估计量，实践上多数只跑一次**——KTH 论文的核心批评对象 |
| **悲观界** | pass^k | k 次尝试**全部**成功的概率（一致性下界）。**非** pass@k 的补 |
| 乐观界 | pass@k | k 次中至少一次成功 |
| 组内相关 | ICC | 同一 task 的多次重复之间的相关性；方差分解的核心量 |
| **设计效应** | DEFF = 1+(m−1)·ICC | 聚类校正；有效样本量 = 原始 N / DEFF |
| 伪重复 | pseudoreplication | 把同一 task 的多次重复当独立样本——**评测报告中最常见的单一错误** |
| 配对设计 | paired / within-subject | 同一 task 跑两臂再做差；**降低方差的前提是"配对真的配上了"** |
| 簇稳健标准误 | cluster-robust SE | 题目家族相关时，朴素 SE 会捏造显著性 |
| **分层自助法** | hierarchical / BCa bootstrap | 先重采样 task、再重采样 task 内重复；小样本主检验 |
| 预注册 | pre-registration | 看数据前冻结假设/主指标/停止规则 |
| 封卷 / 承诺方案 | commitment scheme | 先哈希锁定测试卷，后揭示 |
| 出货集 / 保留集 | held-out / holdout / holdback | holdback = 到出分前连评测者也不可见（防记忆） |
| 信噪门槛 | seed recall / clean false-positive rate | **门禁自身**的两个度量，取代"通过率" |
| 提前窥视 | peeking / alpha spending | 未到计划 N 就看结果并决定停 |

**须区分**：①pass@k ≠ 平均成功率 ②**token 计费下降（缓存）≠ 行为效率提升** ③run-to-run 随机性 ≠ 任务难度方差 ④"测试通过率" ≠ "测试有杀灭力"

---

## 2. 候选对比总表

### 2.1 核心方法学文献

| 候选 | 关键量化结论 | 对我们的直接含义 |
|---|---|---|
| **On Randomness in Agentic Evals**（KTH，arXiv 2602.07150） | 60,000 轨迹 / 25.58B token / 6 配置 × **10 次独立重复**。**单次 pass@1 随"取哪一轮"波动 2.2–6.0pp；温度 0 下标准差仍 >1.5pp**；乐观-悲观界差达 **24.9pp**；轨迹在**前 1% token 内就开始分叉** | **单次实验无法区分 2–3pp 的差异**——这正是我们关心的量级 |
| **附录 A：功效分析公式**（同上） | 见 §4.1，本文档给出可直接代入的形式 | **决定我们必须跑多少次** |
| **Resolution Diagnostics for Paired LLM Evaluation**（ICML 2026） | 配对设计 `N* = ((z₁₋α/₂+z₁₋β)·σ_D/\|δ\|)²`；**流行的"单臂 Cohen's h × (1−ρ)"捷径在小效应下低估约一半** | 不要用简化公式算样本量 |
| **GitLab Orbit Evals Harness 统计方法文档** | **96 个 rep 级配对数实际只有 ~21 个独立 task 簇**；朴素 Wilcoxon/配对 t 的 **p 值膨胀 10–1000×**；n=21 时 Berry-Esseen 界 0.19 → **t 检验只能当 sanity check**，主检验用 **BCa 分层 bootstrap**（~10,000 次） | 我们的 ticket 数远小于 21 → **必须用分层 bootstrap，不能用 t 检验** |
| **Don't Use the CLT in LLM Evals**（ICML 2025 Spotlight） | 少于几百个数据点时 CLT 失效；**bootstrap 在小 N 下覆盖同样差**；推荐贝叶斯可信区间或精确频率派（Clopper-Pearson/Wilson） | 小样本区间要用精确/贝叶斯方法 |
| **Token Reduction Is Not Cost Reduction**（arXiv 2607.12161） | cost 的 **ICC = 0.37–0.55**；**712 runs/arm 的 Kish 有效样本量只有 ~38–45 个任务**；"**重复运行永不当独立样本，推断单位是 task**" | **我们的推断单位 = ticket** |
| **agentic-dev-team Exp 02/05** | 预注册范例：时间戳 + "注册时所有 JSONL 均为 0 行"的证明；主终点预先写死；**机制隔离假设**（refactor vs ordering） | 直接可抄的预注册模板 |
| **HCast / METR**（metr.org/hcast.pdf） | 任务套件设计（189 任务、1 分钟–8 小时）；**CI 宽的主因是任务套件的局限而非测量噪声**；长时长任务样本量不足是"真问题" | 任务分布要铺开，堆同类任务不增功效 |

### 2.2 工程/工具候选

| 候选 | 提供什么 | 适用性 |
|---|---|---|
| **mdredd** | Claude Code 专用 A/B 沙箱：**每次运行独立沙箱**、**隐藏宿主真实 `.git/`**（放空仓避免分支名/提交信息泄入 prompt）、**屏蔽项目 auto-memory**、**排除项目 `.claude/`**（防磁盘上的 skill 遮蔽被测变体）；用户级全局配置**故意保留**（各变体一致，故可对消） | 🟢 隔离设计**直接可搬**；工具本身是第三方 npm（4 star），不建议依赖 |
| **self-bench** | 从**已合并 PR** 自动重建任务（取变更前 commit）+ 生成隐藏测试与参考解 + 验证（无解必败/原实现必过） | 🟢 **解决我们"没人力写隐藏验收"的死结** |
| **AgentAssay** | SPRT 自适应试验数：**-78% 试验数**；自适应预算 **4–7×** 降本；合计 5–20× | 🟢 若重复次数成为成本瓶颈 |
| **evalstats** | 小样本（N<100，最低 15）统计：**两层嵌套 bootstrap**（先重采样输入、再重采样输入内重复）、种子/输入方差分解、BH-FDR、PPI 校正 | 🟢 **推荐直接使用** |
| **gh-aw experiments** | 变体轮转分配（取调用次数最少者）、guardrail 指标自动中止、~10 变体实用上限 | 🟡 多臂轮转思想可借 |
| **GrowthBook（agent 实验指南）** | workflow 级度量、级联失败、replay-based、步骤级评分"active misleading" | 🟢 度量定义可借 |
| **JCodeMunch A/B 实例** | 50 次迭代、**变体交替以控顺序效应**、隔离 0-finding 轮次以剥固定开销 | 🟢 成本归因的实操范例 |
| **AgentEval 成本分级** | `--budget-tier`：TRIVIAL/LOW/MEDIUM/HIGH 评估器分层 | 🟡 可按需 |

---

## 3. 排除清单及原因

| 候选 | 排除原因 |
|---|---|
| 各类"AI 写测试排行榜/评测平台"营销页 | 无一手实验记录，仅作存在性证据 |
| 厂商 A/B 平台（PostHog/GrowthBook 产品） | 产品本身排除；仅取其方法学章节 |
| 人类 TDD 实验方法学（Beck/工业研究） | 预置硬性排除 |
| METR 的 time-horizon 曲线拟合方法 | 目标是能力天花板估计，与"两流程对比"不同构；仅保留其"任务套件局限导致 CI 宽"的教训 |
| 需要 Blackwell 集群/专有数据集的复现方案 | 违反本机约束 |
| Superpowers 类无对照组的"合规度"评测 | 无 vanilla 对照 = 不构成效果证据（已在上一份报告 G1 判定） |

---

## 4. 关键技术判断

### 4.1 分化点 A：样本量——先算清楚，再决定做不做

KTH 附录 A 的两样本形式：

```
n ≥ 2 · ((z_{α/2} + z_β) / (Δ/σ))²        α=0.05, power=80% ⇒ 15.68 / (Δ/σ)²
```

配对形式（Resolution Diagnostics）：

```
N* ≥ ((z_{1-α/2} + z_{1-β}) · σ_D / |δ|)²   α=0.05, power=80% ⇒ 7.84 / (δ/σ_D)²
```

**代入 KTH 实测的 σ（1.5–1.8pp），两样本情形所需的"每臂独立观测数"：**

| 目标效应 Δ | σ=0.7pp（最有利） | σ=1.5pp | σ=1.8pp（最不利） |
|---|---|---|---|
| 10pp | 1 | 1 | 1 |
| 5pp | 1 | 2 | 2 |
| **2pp** | 2 | **7** | **13** |
| 1pp | 8 | **35** | **51** |

**读法（对我们最重要的一行）**：想测出 **2pp** 的差异，需要 **7–13 次独立观测/臂**；想测 **1pp**，需要 **35–51 次**——**在本机串行条件下不可行**。

**配对 + 聚类的修正**（我们的真实形态）：
- 配对本身极强——若同一 ticket 两臂的差值标准差 σ_D 远小于跨 ticket 的 σ（因为任务难度被对消），所需 N 大幅下降；
- **但必须除以设计效应**：`DEFF = 1 + (m−1)·ICC`。以实测 ICC≈0.45、每 ticket 跑 m=3 次计，DEFF ≈ 1.9，即有效样本量约为原始的一半。
- PhAIL 的实例可作校准参照：朴素 McNemar 估 600–1500 rollouts/格 → 加设计效应校正后降到 **~25–45**。

**给我们的落点建议**：目标是 **≥2pp 量级**的效应检测（这个目标**可达成**），放弃 1pp 级别的结论（不可达成，且外部证据本身的效应量也大于此）。粗算：**6–8 个 ticket × 每臂 3 次重复**，用分层 bootstrap 出区间——**这是本机能承受的量级**（成本见 §4.4）。

### 4.2 分化点 B：推断单位是 ticket，不是 run

这是最容易被忽略、且后果最严重的一条。实测 ICC 0.37–0.55 意味着：**同一 ticket 的多次重复高度相关**，把它们当独立样本 = 伪重复。

- GitLab Orbit 的实测：96 个 rep 级配对数 → **实际只有 ~21 个独立 task 簇**；朴素检验 **p 值膨胀 10–1000×**（即：把不显著的结果报成显著）。
- 正确做法：**BCa 分层 bootstrap**——重采样 ticket（有放回）→ 在每个被抽中的 ticket 内重采样重复 → 算均值差 → 重复 10,000 次 → 偏差校正与加速。
- 小 N 下**正态近似不可用**：Orbit 在 n=21 时 Berry-Esseen 界 0.19，t 检验只能当 sanity check。

### 4.3 分化点 C：隐藏验收测试——没有它，整个实验无效

三份关键证据（KTH / agentic-dev-team / arXiv 2602）全都依赖**隐藏验收**：
- agentic-dev-team：**"验收测试仅在评分时注入，任何臂都无法看到（或意外满足）它被评判所依据的测试"**；
- arXiv 2602 的教训：agent 写的测试主要是 `print` 观测，**用它当评分依据等于自评**；
- Exp 02 的发现：vague spec 下 **"被省略的决策"探测器在所有 workflow 上都是 0%** —— 这类测试才是区分度的来源。

**低成本构造路径（R4 闭合）**：
1. **从自己仓库的已合并 PR 反向重建**（self-bench 思路）：取变更**之前**的 commit 作为起点，把该 PR 的**测试**扣下来当隐藏验收，并验证"无解必败 / 原实现必过"。
2. **三集分离**：`dev`（提示用）/ `report`（封存，出分前不看）/ `holdback`（连评测者也不可见，防记忆）。
3. 协议写成 **可哈希的 YAML**：每个任务带稳定 ID、语言、fixture 路径、超时、public/hidden 标志；**缺哈希则拒绝计算百分比**。
4. **规模**：40–80 例起步（**<20 例时一个 flaky 就摆动约 5pp**）。
5. 判分顺序：**确定性断言优先（免费）→ 小模型 judge → 仅失败/低置信时升级到强 judge**。

### 4.4 分化点 D：成本归因——三个已实测的陷阱

| 陷阱 | 实测证据 | 后果 |
|---|---|---|
| **缓存伪装成效率提升** | provider 侧前缀缓存可减掉约 **61% 的账面账单，而行为指标完全不变** | 直接比"账单金额"会得出假结论；**四类 token（未缓存输入/输出/缓存读/缓存写）必须分开计价** |
| **多轮成本非线性** | 历史每轮重发（三角增长）：6 步 agent ≈ **3.8×** prompt tokens，而非 2× | 按"步数×单价"估预算会严重低估 |
| **比较了不同工作量** | 某项目"1.87× 成本"校正为等量工作后变成 **0.84×** | **必须比"每观测单位成本"，不是总额** |

**量级参照**（供预算校准）：Markspace 1,440 trials ≈ **$19.30**；AgentAssay 7,605 trials ≈ **$227**（含多模型）。即**每 trial 约 1–3 美分**量级——**我们的实验成本瓶颈不是钱，是墙钟时间**（本机串行）。

### 4.5 分化点 E：门禁自身也要被度量

若实验结果导致我们改门禁（例如把 g0 升为必过），该门禁本身需要两个指标（取代"通过率"）：
- **seed recall**：注入的已知故障被门禁抓到的比例，**目标 ≈100%**；
- **clean 假阳性率**：已知良好补丁被误拒的比例，**目标 <5%**。

可操作的 g0 五步循环（R4 实证）：**先冻结 flaky 测试**（否则随机失败会让每个变异都"看起来被杀"）→ **只变异本次改动触碰的函数** → 生成单点故障（`eq_to_neq`/`lt_to_le`/`add_to_sub`/`zero_to_one`）→ 逐变异重跑套件 → **卡 kill rate**。

实证案例：一个队列补丁全绿通过所有既有门禁，注入 4 个故障后 **kill rate 仅 2/4**——两个 survivor 都是 modulo 环绕路径从未被执行。**这正是 g0-inject.sh 应产出的信号类型。**

### 4.6 顺序效应与污染控制

- 随机化顺序**限制**偏差但**不证明**无 carryover；"两种顺序都跑"也不完全消除（"只是随机化了谁受益"）。
- 实操：**变体交替**（JCodeMunch 做法）+ 块内配对 + **检查顺序签名**（跑前 vs 跑后的基线差异 CI 是否跨零）。
- **环境隔离必须有**（mdredd 做法）：每次运行独立沙箱、**隐藏宿主 `.git/`**、**屏蔽 auto-memory**、**排除项目 `.claude/`**（否则磁盘上的 skill 会遮蔽被测变体）。注意：**用户级全局配置保留**——它对两臂一致，故可对消。
- **对我们额外重要**：本机项目记忆 / `~/.claude` 记忆 / `CLAUDE.md` 都会在重复运行间累积——**必须逐次隔离，否则第二轮已经不是同一个实验了**。

### 4.7 预注册：写成可哈希协议

agentic-dev-team 的范例可直接抄：**时间戳 + "注册时所有数据文件均为 0 行"的证明 + 主终点写死 + 假设列表 + N per cell**。对我们的额外价值：**本实验的结论要用于推翻/保留一条既有门禁，事后解释的空间必须提前关闭。**

---

## 5. 缺口裁决表（L4）

| # | 缺口 | 产生于 | 闭合动作 | 结论 |
|---|---|---|---|---|
| G1 | 小样本 + 配对 + 聚类下的功效如何计算？ | R2（KTH 公式是 benchmark 级） | 检索配对设计与聚类校正 | **已闭合**：配对式 `N* = ((z+z_β)σ_D/\|δ\|)²`；聚类用 `DEFF=1+(m−1)ICC`；小 N 主检验用 BCa 分层 bootstrap。见 §4.1/§4.2 |
| G2 | 隐藏验收测试如何低成本构造？ | R2 | 检索"自带仓库 held-out 构造" | **已闭合**：**从已合并 PR 反向重建**（self-bench 路径）+ 三集分离 + 哈希协议 + 40–80 例起步。见 §4.3 |
| G3 | 重复运行是否独立？顺序效应如何控？ | R2 | 检索 ICC/顺序效应/carryover | **已闭合**：**不独立**（cost ICC 0.37–0.55；712 runs 的有效样本仅 ~38–45 task）；推断单位 = task；交替变体 + 顺序签名检验。见 §4.2/§4.6 |
| G4 | 本机串行条件下的成本预算？ | R2 | 检索试验成本实测 | **已闭合**：每 trial ≈ 1–3 美分（$19.3/1440、$227/7605）；真正瓶颈是**墙钟时间**；降本手段 SPRT（-78%）、自适应预算（4–7×）。见 §4.4 |
| G5 | 杀灭力/故障注入能否作为可测结果门禁？ | R2 | 检索 g0/fault-injection 实践 | **已闭合**：五步循环 + 门禁自身度量（seed recall ≈100% / 假阳性 <5%）；实证案例 kill rate 2/4。见 §4.5 |

---

## 6. 推荐结论

### 6.1 实验设计的最小可行形态（MVP）

| 维度 | 建议 | 依据 |
|---|---|---|
| **设计** | 配对：同一 ticket 跑 A（现状 RED 前置）/ B（无前置或结果门禁），**变体交替** | §4.2、§4.6 |
| **推断单位** | **ticket** | ICC 实测 |
| **样本量** | **6–8 ticket × 每臂 3 次重复**；目标效应 **≥2pp** | §4.1 |
| **主检验** | **BCa 分层 bootstrap**（10,000 次），**不用 t 检验** | §4.2 |
| **主指标** | ① 隐藏验收通过率 ② **g0 kill rate** ③ 成本（四类 token 分开 + 墙钟） | §4.3、§4.5、§4.4 |
| **次指标** | 回归率、review findings 数、阶段到达 | 上一份报告 §4.4 |
| **隔离** | 每次运行独立沙箱 + 隐藏 `.git` + 屏蔽 auto-memory + 排除项目 `.claude/` | §4.6 |
| **协议** | 哈希冻结的 YAML，跑前落盘 | §4.7 |
| **工具** | `evalstats`（两层嵌套 bootstrap）或自写脚本 | §2.2 |

### 6.2 必须先接受的三个限制

1. **测不出 1pp**——若争议点是"1–2pp 的微小改进"，本机实验无法裁决，只能如实报告"不可判定"。
2. **成本瓶颈是墙钟不是钱**——六配置 × 10 次的 KTH 规模我们做不到，代价是结论只能覆盖大方差场景。
3. **隐藏验收的质量决定实验上限**——若重建的隐藏测试本身弱，实验会给出"两臂无差异"的**假阴性**（Phoenix 的发现：弱套件上约 20% 通过测试的补丁语义仍错）。

### 6.3 与上一份报告的接合点（重要）

本调研过程中浮现一条**改变问题框架**的证据：agentic-dev-team 的**机制隔离假设**实测显示——

> `tdd-no-refactor`（701 行）≈ `test-after`（700 行），而 `tdd-refactor`（664 行）显著更低。
> **"收益来自 refactor 步骤，不是 test-first 顺序。"**

而**我们的门禁恰好只强制顺序**（"写实现前必须有 RED commit"），**不强制 refactor**。若该结论成立，我们一直在门禁化的，正是证据显示**不承重**的那一半。

这给实验设计一个更锐利的假说（建议作为主端点）：
> **H1**：在 ticket 级，"RED commit 前置"对隐藏验收通过率与 kill rate **无显著影响**，但显著增加 token 与墙钟成本。
> **H2（机制）**：若把门禁改为"必须有一次 refactor 提交"（而非 RED 前置），kill rate 提升幅度大于改成 RED 前置。

**H2 才是这个实验真正的价值所在**——它测的不是"要不要门禁"，而是"**门禁该管哪一步**"。

### 6.4 分期建议

- **短期**：只做 H1（两臂、6–8 ticket × 3 次），回答"现有门禁是否值得留"。
- **中期**：若 H1 支持，做 H2（三臂：无门禁 / RED 前置 / refactor 前置），回答"改成什么"。
- **长期**：把 g0 的 seed recall / 假阳性率纳入常规门禁体检（§4.5），实验从"一次性对照"变成"持续体检"。

---

## 7. 来源列表

**一手·全文**
- On Randomness in Agentic Evals（KTH）— https://ar5iv.labs.arxiv.org/html/2602.07150 ｜ ICLR 页面 https://iclr.cc/virtual/2026/10016323
- Don't Use the CLT in LLM Evals（ICML 2025 Spotlight）— https://ar5iv.labs.arxiv.org/html/2503.01747
- HCAST: Human-Calibrated Autonomy Software Tasks（METR）— https://metr.org/hcast.pdf
- agentic-dev-team Exp 02 结果 — https://github.com/bdfinst/agentic-dev-team/blob/main/docs/experiments/02-final-results.md
- agentic-dev-team 实验总览 — https://github.com/bdfinst/agentic-dev-team/blob/main/docs/experiments/README.md
- evalstats — https://raw.githubusercontent.com/ianarawjo/evalstats/main/README.md
- gh-aw A/B experiments 指南 — https://raw.githubusercontent.com/github/gh-aw/main/.github/aw/experiments.md
- JCodeMunch A/B 实测 — https://raw.githubusercontent.com/jgravelle/jcodemunch-mcp/25062d4182eff57c32ae1e69f58f5674fdddb3c5/benchmarks/ab-test-naming-audit-2026-03-18.md
- GrowthBook：agent/workflow 实验指南 — https://www.growthbook.io/insights/run-experiments-ai-agents-workflows
- mdredd（A/B 沙箱设计与隔离清单）— https://github.com/slaFFik/mdredd

**一手·部分 / 检索摘要**
- Resolution Diagnostics for Paired LLM Evaluation（ICML 2026）— https://en.papernotes.org/ICML2026/llm_evaluation/resolution_diagnostics_for_paired_llm_evaluation/
- GitLab Orbit Evals Harness 统计方法 — https://gitlab.com/gitlab-org/orbit/orbit-evals-harness/-/blob/4049ab88794beef1cd1fd4af4257aa1e0e09d0b5/docs/statistical-methodology.md
- Token Reduction Is Not Cost Reduction — https://arxiv-org.ezproxy.obspm.fr/html/2607.12161v5
- self-bench（从 PR 反向构造隐藏测试）— https://github.com/mupt-ai/self-bench
- skill-eval-harness（holdout/holdback）— https://github.com/adewale/skill-eval-harness
- AgentAssay（SPRT 降本）— https://ar5iv.labs.arxiv.org/html/2603.02601
- markspace 实验成本数据 — https://github.com/opinionated-systems/markspace/blob/main/experiments/validation/analysis.md
- AgentEval 成本分级 — https://raw.githubusercontent.com/AgentEvalHQ/AgentEval/refs/heads/main/docs/benchmarks/agentic/cost-guidance.md
- Mutation Testing as a Merge Gate for Agent-Written Tests — https://dev.to/datacpp_8185/mutation-testing-as-a-merge-gate-for-agent-written-tests-5gie
- The Gate Rejected Nothing（seed recall / 假阳性率）— https://dev.to/datacpp_8185/the-gate-rejected-nothing-so-i-injected-40-bugs-to-see-if-it-could-4ecg
- The Agent's Tests Passed. Mutation Testing Showed 2 of 4 Faults Survived — https://dev.to/datacpp_8185/the-agents-tests-passed-mutation-testing-showed-2-of-4-faults-survived-738
- 中文：大模型评测实验设计（方差/显著性/小样本）综述来源集 — https://github.com/ianarawjo/evalstats ｜ https://statsig.com/perspectives/abtesting-llms-misleading
