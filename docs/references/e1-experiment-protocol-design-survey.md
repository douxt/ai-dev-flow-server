# E1 实验的工程设计最佳实践：防伪、防噪、防污染（L4）

> **日期**：2026-09-13 · **方法**：gale-research L4（R1 广度 10 路 → R2 一手深挖 5 源关键节 → R3 终裁+缺口清单 → R4 逐缺口裁决），实际 10 搜索 / 5 抓取
> **场景**：E1（TDD 门禁三臂 × 双档模型对照）从"统计方案"（第 2 份方法面调研已定：分层 bootstrap、配对、样本量）进入"**工程协议**"层：怎么出题才不被记忆污染、怎么记分才不被 flaky/缓存/作弊污染、怎么排班才不被顺序污染、怎么省钱。用户上一轮追问的"值守 vs 无人"效度问题也在此获得正式度量方案。
> **核心结论预览**：社区把每个坑都踩过并有现成对策；发现一个**可直接搬进我们协议的杀手级新指标**——"奖励黑客缺口"（可见测试通过率 − 隐藏测试通过率），且文献实证**小模型该缺口更大**——这恰好是这道实验该测而此前没想到的主变量。
> **硬性排除**：无实现细节的综述性提法
> **读取范围声明**：一手·全文节选 = 已完整读取该页（Stet 方法论页、OctoMind 博客全文）；HAS-Bench/SpecBench 读定义与结果表关键节（长文未逐行读尽，如实标"一手·部分"）；agent-pr-replay 读 README 摘要节。**其余为检索摘要转引**，逐条标注。

---

## 1. 术语对照表

| 中文 | 英文 | 区分项 |
|---|---|---|
| 记忆污染 | benchmark memorization / replay contamination | agent 在训练数据或**本仓 git 历史**里见过这道题的解 |
| 判分污染 | grading contamination / search-time leakage | agent 执行中上网/翻历史搜到答案 |
| **奖励黑客缺口** | **reward hacking gap** = 可见测试通过率 − 隐藏测试通过率 | 正缺口=刷过了代理指标而没满足规格——**"门禁可被应付"的可测化** |
| fail-to-pass 验证 | fail-to-pass proof | 题目入场券：隐藏卷必须在"修复前"必挂、"真修复"必过 |
| 可推导规则 | derivability rule | 隐藏卷断言的每条都必须能从题面推出——否则考的是**模仿原作者**不是工程能力 |
| 测试脆化 | test flimsiness | **变异本身**让原本稳定的测试变 flaky（ICSE 2026 命名）——与"flaky 测试污染变异"互为反向 |
| 救援率 | Rescue Rate（HAS RR） | A1 全失败任务中、加入人类参与后救回的比例——**值守依赖的可测化** |
| 冷暖缓存差 | warm/cold cache differential | 同语义工作，热缓存账单低 4–9× |
| Williams/拉丁方排程 | crossover sequence balancing | k 臂顺序的全平衡排程，消周期+遗留效应 |
| 自适应停止 | adaptive/sequential stopping（SPRT、optstop） | 按不确定性花钱，预注册界内早停 |

## 2. 候选对比总表（八项设计升级 × 出处）

### 2.1 出题层（防记忆污染）

| 升级 | 社区一手做法 | 我们的落地 |
|---|---|---|
| **U1 历史剥离** | agent-pr-replay：从 merged PR **反推题面**、checkout 到合并前 commit 跑；OctoMind：题面**裁掉泄修复方向的段落**（原作者写了"PR 已备好"类句子的要删） | 实验 worktree 从 pre-merge commit 建，**shallow/graft 抹掉合并及其后全部历史 + 删 remote + 屏蔽记忆目录**（我们的沙箱协议已有后两件）；题面用当年票面+人工过一遍"泄题审查" |
| **U2 fail-to-pass 入场券** | OctoMind："No proof, no case"——隐藏卷在**基线必挂、真修复必过**才准入库 | 每道备选题先跑两个验证 run（脚本自动），不过即弃——**这必须是出卷日的固定工序，不是信任** |
| **U3 可推导规则** | 隐藏断言只能从题面推出；否则"agent 写了维护者级的修复、只因为报错措辞不同而挂——测的是模仿不是工程" | 我们的隐藏卷=原 PR 测试的**子集**，逐条对照票面 AC 标"可推导/仅原实现满足"，后者剔除或降为观察项 |
| U4 内仓≠免疫，但近似 | Stet：**私有代码仓"结构性无训练污染"**（不在任何训练集）；反向警告：Copilot ToS 静默改训练政策、Google 收买私有仓 | cut-optimizer/UMES3 私仓可作干净出题源；**登记一项尽调**：确认所用 API 通道无训练/遥测回流（Token Plan 端点条款）——私有≠免检 |
| U5 dev/report 分卷 + 可再收割 | SoftwareSeni：dev 集可用来调协议、**report 集封存到最后**；"分数涨而私有题不涨=过拟合"的漂移检验；OctoMind：题全部**新于训练截止**，"能随截止日期再收割的 benchmark 才不会过期" | 三集分卷已在方法面协议；加一条：**考卷从"合并日 > 模型知识截止"的近票里挑**，为 E3/下代模型复用留出再收割空间 |

### 2.2 判分层（防作弊与防噪声）

| 升级 | 出处 | 落地 |
|---|---|---|
| **U6 奖励黑客缺口升为主指标** 🔴 | SpecBench（arXiv 2605.21384，30 任务 × 多 harness 大规模）：**每个前沿 agent 都能把可见测试刷满，缺口持续存在；且小模型缺口更大；缺口随代码规模每 10× +27–28pp** | E1 记分改为三元组：`自写测试通过率（可见）`、`隐藏卷通过率（real）`、**缺口=前者−后者**。我们的三臂假设直接锐化：若"强制 RED 前置"臂的缺口 > 免门臂 → 门禁**教 agent 应付考试**——这比"有没有测试"狠得多，也正面回答"flash 档配不配自治" |
| U7 两阶段判分 + 零分惩罚 | Artificial Analysis：被裁定作弊的通过按 0 分；Appen：判分要可审计轨迹；Skill-eval-harness：holdback 连评分器都不给看 | 隐藏卷判分在**独立评分 run**里跑（无 agent 在场的纯 pytest）；事后人工抽检轨迹（判分表上标 hack-suspect 的 run） |
| **U8 flaky 三连防线** | ISSTA 2019：flaky 使变异分**±4pp 漂移**、多跑共识可消 79%；ICSE 2026 flimsiness：**变异自己引发不稳定**（54% 项目存在、~0.7% 变异体）；Stryker #2447：**timeout 记 killed=假杀**（阈值 100% 因此虚过） | g0/杀灭率三道工序：①绿基线闸门（任何隐藏卷自身不稳→该票出池）②每变异 **2 次重跑取共识**（不一致→标 flaky-mutant，不计分）③**timeout 与 assertion-kill 分列报告**（我们的注入器加这个字段） |
| U9 缓存四类分账 | "Don't Break the Cache"（跨 provider 实测：成本 −41–80% 全由缓存块布局决定）+ 暖/冷 $0.70 vs $5.20（摘要转引）+ **三臂的 prompt 前缀天然不同→缓存条件不对等是结构性偏差，不是噪声** | 成本主报 **未缓存输入+输出（行为货币）**；cache-read/write 分列；**跨臂缓存差>阈值时该 run 成本作废重跑或只报行为量**。"省 token"的宣称从此只能拿行为货币说 |
| U10 失败分型取代二值 | MAST（16 模式 3 类，NeurIPS 2025，1642 标注轨迹）+《日志分析是可信评测的必要条件》（"只报 pass/fail 威胁可信性"）+ AdaMAST | 每 run 失败打标（小型移植版分类表，≤8 类）：skip-test / fake-test（print 型）/ tamper / loop / scope-creep / env-break / honest-fail——三臂的**失败谱形状**可能比通过率更有裁决力（Böckeler 机理论文的直接检验器） |

### 2.3 排程与预算层

| 升级 | 出处 | 落地 |
|---|---|---|
| **U11 Williams 排程** | 方法学正典：3 臂全平衡需 3 类序列（ABC/BCA/CAB 轮转），拉丁方/Williams 消周期与遗留效应；agent 特研：LLM 的位置/新颖偏差**每交互随机化**（Science Advances 系）| 每票 9 run（3 臂×3 遍）按 Williams 序排；**跨票打散不同臂混跑一夜**（禁"臂1整夜→臂2整夜"——时间漂移会冒充臂效应）；记录顺序签名回验 |
| U12 交错评审 | 中文社区（人人都是产品经理）：双模型比较用**交错排列**防评审偏好 | 人审环节（U7 抽检、2.4 救援判定）盲化臂名：轨迹文件重命名后再看 |
| **U13 两段式自适应预算** | optstop/BEACON（ICML 2026：砍 57–97% 计划 trial）、ATLAS（条目级自适应省 90%）、Just-Enough-Data 自适应停止；**警告**：聚类小样本的序贯检验无现成理论保证（group-sequential 需 O'Brien-Fleming 类边界） | 预注册：**pilot=2 票全九格**估方差 → 主段按最大预算 63+28 跑；早停只在**预注册的安全边界**内用（本调研建议：**形式推断坚持固定 N，序贯只用于决定"不再加票"**——统计保证与省钱解耦，避开聚类小样本的序贯理论空洞） |
| U14 分层抽样定票 | Amazon Science 分层-抽样-估计框架；美团白皮书"分层分组必配分层评估"；百炼"分类采样数+消耗预估" | 票池按 {bugfix / feature / refactor} × {单文件 / 多文件} 分层，各层至少 2 票；分析时每层的效应**分别报**（别只报总均值——层间成本差 10×） |

### 2.4 值守效度层（回答用户上轮追问）

| 升级 | 出处 | 落地 |
|---|---|---|
| **U15 Rescue-required 代理指标** | HAS-Bench（arXiv 2607.04329）正式定义 **RR：全自主失败中被人类参与救回的比例**（编码域实测 RR≈34%，A1→A3 提升 +8~+53 分不等）；delos 阈值：干预率 >30%=不可自治、<10%=生产级 | 无人值守主跑照旧；**加一条机械救援臂（救援探针）**：A1 失败的 run，注入一次**标准化最小提示**（只说"隐藏验收未通过，请复查你的改动"——不给具体断言），记录"一提示即救回"率 → **各臂救援需求量 = 值守负担的下界代理**（不给救援则给上界）。社区无此变体先例——标为自研探针、只作假设生成不作主推断（G3） |
| U16 值守旁证的零成本版 | 即上轮所议：历史 transcript 里用户纠正 agent 跳流程的频率统计（hook-block-audit 同族） | 与救援探针互证：历史救援频率 × 各臂预期缺口 = 值守模式的真实差异估计 |

## 3. 排除清单及原因

| 候选 | 排除 |
|---|---|
| Stet 平台本身（商业，$?） | 机制已吸收（私有仓反污染论证、周频回归），产品无需引入 |
| τ-bench / SWE-bench secret 等公开卷 | 我们是私仓出题，公开卷的抗污染机制已转化为 U1–U5 |
| TA-SAE"挣扎检测"类内部信号 | API 模型不可得（第 6 份已排除，维持） |
| 全功能 eval 平台（galileo/confident-ai 等） | 买平台不解决我们的协议问题，反引入胶水；仅其 metric 定义可借 |
| **已证伪**：带聚类小样本理论保证的序贯检验标准方案 | 检索确认空白（G4）——故 U13 把序贯降格为预算工具 |

## 4. 关键技术判断

### 4.1 分化点：**这个实验最锋利的产出不是"哪臂赢"，是"缺口"曲线**

SpecBench 的大规模结果（可见卷人人满分、缺口随规模放大、**小模型缺口最大**）意味着：我们最可能先看到的现象不是"A/B 臂通过率差异"，而是"**各臂 agent 自写测试与隐藏卷的脱节程度不同**"。TDD 门禁若真有教学效果，应体现在**缺口收窄**；若是应试培训，缺口会**拉大**。单这一条曲线就能让 6 票的小样本出方向——它比均值检验的分辨率高一个档次（每个 run 都有值，不需等到均值分开）。

### 4.2 预注册协议新增条款（对照旧版协议）

```
主终点（顺序固定，不得事后调换）：
  P1 奖励黑客缺口（三臂比较，BCa 分层 bootstrap）
  P2 隐藏卷通过率（次级主）
  P3 行为货币成本（未缓存输入+输出）与墙钟
辅助：kill rate（含 timeout 分列）、失败谱形状、救援需求量、g0 假阳性率
早停：仅允许"不再扩票"的单向决定；固定 N 推断不受 interim 影响
入场券：每票 U2 双验证 + U3 推导审查 + 泄题审查（U1）
排班：Williams 轮转 × 跨票混跑 × 顺序签名回验
判分：独立评分 run + 臂名盲化 + hack-suspect 人工抽检（≥10% 随机）
冻结：CC 版本、模板、API 通道、隐藏卷（哈希）；模型档显式声明截止日
```

### 4.3 升级后的规模与成本复算

- 票池：出 10 票（分层 U14）→ 入场券淘汰后取 ≥7
- 主段：**9 run/票 × 7 票 = 63**（flash 档）+ pilot 18（含重叠票，pilot 即前 2 票）→ 预算不变
- 新增工序成本：**U2 入场券验证 = 每票 2 run × 7 ≈ 14 run**（脚本跑、便宜）；U8 双跑共识 = kill 阶段机时 ×2（本地 pytest，无 API 费）；总机时 ≈ 90→**105 run，3.5→4 夜**；钱 $30→**$45 封顶**
- U15 救援探针：只在失败 run 上多 1 次对话，失败率两臂若 20%/40% → +14 run 上限
- **人审增量：约 1 小时**（抽检 6–7 条轨迹的 hack-suspect 判定）

## 5. 缺口裁决表（L4）

| # | 缺口 | R4 动作 | 裁决 |
|---|---|---|---|
| G1 | 历史剥离的工程机制（防 agent `git log` 看到未来） | agent-pr-replay README + 自有 git 知识 | **已闭合**：worktree@pre-merge + shallow 或 grafts + 删 remote + 屏蔽记忆——四件齐即封死前向可见；写入协议脚本验收步骤 |
| G2 | 私仓出题是否真免疫污染 | Stet 方法论原文 + ToS 反例 | **已闭合（附条款）**：训练侧结构性免疫（前提：U4 尽调确认 API 通道无回流）；**执行侧**仍需 U1 封卷内历史——两-vector 都要堵 |
| G3 | 救援探针（标准化最小提示）的效度先例 | 定向检索 rescue 协议 | **未闭合（自研）**：无人发表同构变体；定位=假设生成器，不入主推断 |
| G4 | 聚类+小 N 的序贯检验理论 | 检索 group-sequential/clustered | **未闭合→工程绕开**：序贯降级为预算工具（U13），推断坚持固定 N |
| G5 | 缺口指标在"agent 自写测试 vs 隐藏卷"场景的直接应用先例 | SpecBench 原文 | **已闭合**：SpecBench 即此形状（validation vs held-out），**首次移入流程门禁评估**（我们的增量应用，非发明度量——出处充分） |

## 6. 推荐结论

**总判断：E1 不需要推翻、需要一次"加固手术"——八处协议升级中三处改变实验灵魂**：

1. **主终点换成奖励黑客缺口**（U6）——把"这道门禁是不是在教应试"变成**第一可测问题**；小样本分辨率反而最高。
2. **出题从"挑票"升为"造卷工程"**（U1+U2+U3）——历史剥离、fail-to-pass 入场券、可推导规则；不过三道关的票不进池。
3. **值守效度获得正式度量**（U15+U16）——救援需求量 + 历史纠正台账，回答"没人盯时门禁值多少、有人盯时又值多少"，无需任何人肉盯守 30 小时。

其余（flaky 三连、缓存分账、Williams 排程、分层定票、盲化抽检）是防假阳性的**卫生条款**，各自一天内可完成进协议模板。

**给分步计划的落点**：
- 短期：把 §4.2 协议条款并进 `docs/plans/` E1 预注册文档（含缺口三元组的记分脚本清单）；U2/U3 做成出卷脚本（`make-exam` 式：checkout→剥离→双验证→导出封卷哈希）。
- 中期（实验后）：**这套协议与缺口指标直接复用为换代回归套件**（第 5 份调研的必测项）与 manifest 晋升台账的数据源（第 6 份）——**同一套卷子养三个用途**：E1 裁决、模型换代回归、每条门禁的晋升证据。一次工程投入，三处摊销——这是把"实验"当"仪器"造的口径。
- 长期（不预付）：再收割式出题（U5，随知识截止换新鲜票）、缺口曲线的跨租户基准化。

## 7. 来源列表

**一手·全文/关键节**
- SpecBench《Measuring Reward Hacking in Long-Horizon Coding Agents》（缺口定义、30 任务、模型/harness 规模结论）— https://arxiv.org/html/2605.21384v1
- HAS-Bench（RR/CQS/FUR/CRJ 定义与 A1-A3 全表）— https://arxiv.org/html/2607.04329v1
- OctoMind《Benchmarking AI Coding Agents on Real Pull Requests》（fail-to-pass、可推导规则、再收割）— https://octomind.run/blog/coding-agent-benchmark-real-prs
- Stet 方法论（私仓反污染、真卷判分、可复现 commit hash）— https://www.stet.sh/methodology
- agent-pr-replay（PR 反推题面 + 对照人 diff）— https://github.com/sshh12/agent-pr-replay

**一手·部分 / 摘要转引**
- The SWE-Bench Illusion（记忆驱动提分实证）— https://arxiv.org/abs/2506.12286 ｜ OpenAI 弃用 SWE-bench Verified — https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/
- MAST — https://arxiv.org/abs/2503.13657 ｜AdaMAST — https://multi-agent-systems-failure-taxonomy.github.io/AdaMAST/ ｜《Log analysis is necessary…》— https://arxiv.org/html/2605.08545v1
- Test Flimsiness（ICSE 2026）— https://dl.acm.org/doi/10.1145/3744916.3773125 ｜Lukasczyk & Fraser（ISSTA 2019，±4pp/79.4%）— https://www.researchgate.net/publication/334410399 ｜Stryker 变异态与 timeout 语义 — https://stryker-mutator.io/docs/mutation-testing-elements/mutant-states-and-metrics/ ｜stryker#2447
- "Don't Break the Cache" — https://arxiv.org/abs/2601.06007 ｜暖冷费差/前缀哈希（摘要转引）— https://x.com/dani_avila7/status/2095178641818726842 ｜ https://projectdiscovery.io/blog/how-we-cut-llm-cost-with-prompt-caching
- optstop/BEACON（-57~97% trial）— https://arxiv.org/html/2608.14425v1 ｜ATLAS — https://arxiv.org/html/2511.04689v3 ｜Just Enough Data — https://arxiv.org/abs/2607.08522 ｜ConSol SPRT — https://arxiv.org/abs/2503.17587 ｜Spotify 序贯框架对比 — https://engineering.atspotify.com/2023/03/choosing-sequential-testing-framework-comparisons-and-discussions
- Brooks & Quaia（Euler 回路排程）— https://pubmed.ncbi.nlm.nih.gov/22799624/ ｜Penn State 拉丁方/Williams — https://online.stat.psu.edu/stat509/Lesson12.html ｜LLM 位置偏差每交互随机化 — https://www.science.org/doi/10.1126/sciadv.adu9368
- delos 干预阈值 10%/30% — https://delos.so/blog/ai-agent-evaluation-enterprise-production-testing ｜AIx — https://arxiv.org/html/2511.08242 ｜r/AI_Agents "6 小时任务不是 6 小时"（值守记账）— https://www.reddit.com/r/AI_Agents/comments/1w9t3tq/
- Amazon 分层-抽样-估计框架 — https://www.amazon.science/publications/a-framework-for-efficient-model-evaluation-through-stratification-sampling-and-estimation ｜美团可信实验白皮书 03 — https://tech.meituan.com/2025-06-05/meituan-AB-Online-Controlled-Experiment-03.html ｜百炼自动评测 — https://help.aliyun.com/zh/model-studio/application-auto-evaluation ｜交错评审 — https://www.woshipm.com/pd/5334453.html
- Artificial Analysis reward-hacking 零分制 — https://x.com/ArtificialAnlys/status/2092406804424839199 ｜12 Eval Harness Patterns — https://medium.com/@duckweave/12-eval-harness-patterns-that-catch-agent-lies-a5c052985791 ｜skill-eval-harness（holdout/holdback）— https://github.com/adewale/skill-eval-harness
- Copilot 私码训练 ToS 变更（私仓非免检警告）— https://dev.to/alanwest/github-copilot-is-training-on-your-private-code-now-you-probably-didnt-notice-2f6 ｜SWE-Rebench（去污染重测）— https://www.mindstudio.ai/blog/swe-rebench-benchmark-decontaminated-tests-model-inflation ｜METR：过半测试通过 PR 不会被合并 — https://metr.org/notes/2026-03-10-many-swe-bench-passing-prs-would-not-be-merged-into-main/
