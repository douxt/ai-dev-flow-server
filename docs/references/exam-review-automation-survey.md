# 考卷审卷自动化调研报告

> 2026-09-13 · L4（R1 广度 15 路 → R2 深挖 8 件 → R3 终裁 3 路线 → R4 缺口 5 条闭合 4.5） · 场景：E1 造卷三关后的人工推导审查（泄题 + 隐藏卷可推导性）难做，求高效自动化审卷 · 硬约束：可无头、本地 LLM（token-plan）或开源件，排除众包标注服务

## 1. 术语对照表

| 英文 | 中文 | 说明 |
|---|---|---|
| task/instance QC (quality control) | 任务质检 | 基准条目入集前的准入检查 |
| test–instruction alignment | 测试-题面对齐 | 判"可推导性"的规范术语（TB3 rubric 原名） |
| under-specified / over-specified | 题面欠定 / 测试过约束 | 两个相反的失效方向：题不够推 / 测试超范围 |
| solution leakage (in-prompt) | 题面泄题 | 解法在题面/链接中可见，≠训练污染 |
| Rigorous / Lax / Misaligned | 严格/宽松/错位 | MPE 对 fail-to-pass 测试的三分（Lax=F2P 过但仍放行错误修复） |
| surviving mutant / laxity rate | 存活变体 / 宽松率 | 语义变体未被测试杀死的比例 |
| oracle / nop validation | 参考解/空手验证 | 参考解必过 + 啥也不做必挂 |
| flake quarantine | 不稳定测试隔离 | N 次重跑不一致的测试挂起弃用 |
| information firewall | 信息防火墙 | 出题侧防泄题的架构（生成题面的模型不见 bug spec） |
| hacker–fixer loop | 攻防迭代硬化 | 对抗 agent 找漏洞、修 verifier 的循环 |

须区分：**污染检测**（模型训练见过题）≠ **泄题检测**（题面自带答案）。我们只需后者，但两法在工具链上同族（n-gram/相似度是共同底座）。

## 2. 候选对比总表

| 方案 | 来源 | 验什么 | 可指认证据 | 无头/本地 | 适配我们 |
|---|---|---|---|---|---|
| TB3 审卷流水线（静态检查+rubric LLM 评审+Oracle/Nop+Agent/Cheat Trials+Hacker-Fixer） | [TASK_REVIEW_AUTOMATION.md](https://github.com/harbor-framework/terminal-bench/blob/main/docs/TASK_REVIEW_AUTOMATION.md) | 全谱：泄漏、对齐、可行、抗 hack | ✅ 文档原文逐检查项 | 部分（依赖 Harbor/Modal，判分逻辑可抄） | ★★★ 结构蓝本 |
| `test_instruction_alignment` 判据（35 条 rubric 之一） | [task-implementation.toml](https://github.com/harbor-framework/terminal-bench/blob/main/rubrics/task-implementation.toml) | **双向可追溯**：每条断言↔题面需求；测试不得引入题面外要求；>~100 行提示过约束 | ✅ guidance 原文（§3 引） | LLM judge 即可 | ★★★ 直接抄作审卷核心判据 |
| Rubric 回归自校准（fail-rubric-*  planted 反例集，评审器 100% catch 率过闸） | 同上（rubric-regression workflow） | judge 自身可靠性 | ✅ 文档原文 | 需造反例题（我们有真实弱题素材：make_exam 关2 拒收场景） | ★★★ 防"judge 假绿" |
| MPE 三分 + Temporal Matrix（CoHarden） | [arXiv 2607.19843](https://arxiv.org/abs/2607.19843) | F2P 过但 Lax 的题：对 golden fix 造 12 个 4 算子语义变体，宽松率 β/total ≥τ=0.2 → Lax | ✅ 论文原文；成本 $0.84/实例（全 cogen 流水线，纯 MPE 仅占 9.5%） | 变异需 LLM，执行纯本地 | ★★★ 可推导性的**执行级**证据 |
| STING 变体诊断 | [arXiv 2604.01518](https://arxiv.org/abs/2604.01518)（ASE'26，v1 名 STING/v2 名 PROBE） | SWE-bench Verified **77% 实例存在存活变体**；强化后 top-10 agent resolved 掉 4.2–9.0pp | ✅ 摘要原文 | 同族方法 | ★★ 提供量级标定：人工审卷也拦不住 Lax |
| Senior SWE-Bench 三层公平可测判据 | [Snorkel blog](https://snorkel.ai/blog/senior-swe-bench-evaluating-coding-agents-like-senior-engineers/) | 测试只许覆盖：①行为契约（题面明示）②承重代码库惯例 ③无可辩驳替代的最佳实践；超此=过约束 gotcha | ✅ 博客原文 | judge 判据直接可用 | ★★★ 给"可推导"以规范定义 |
| 信息防火墙 + issue-patch alignment check + trigram 守卫 | [SWE-benchify 研究页](https://ai-innovation.team/SWE-benchify/) | 出题侧防泄题：题面由症状生成、模型不见 bug spec；题面-补丁错配检测；文本过相似拒收 | ✅ 页面原文；附 11 条准入约束（C1-C11） | 生成侧重写题面（我们票面不改，只借检查侧） | ★★ 检查项可摘 |
| N-run flake quarantine（F2P/P2P 跑 3 次，结果漂移的测试隔离） | 同上 + lm-eval 惯例 | 隐藏卷自身稳定性 | ✅ 页面原文 | 纯本地 | ★★★ 我们缺这条（make_exam 单次） |
| Cheat Trials（对抗提示单跑）+ `/fortify`（[harden-v0](https://github.com/few-sh/harden-v0)，hacker/fixer/solver 三角色，Apache-2.0，litellm 可指 token-plan） | TB3 文档 | 不真解题能否骗过判分 | ✅ README 原文（需 Python≥3.12+Docker+Harbor） | 可本地 | ★★ 完整版重；简化版单 hacker 可用 |
| Solvability gate：oracle 必须同 harness 解出才入集 | [APIFlow-Bench](https://blog.postman.com/apiflow-bench/)、[Terminal-X Pass@4](https://unipat.ai/blog/TerminalX)、[Scaling RL envs（丢~50%）](https://www.alphaxiv.org/abs/2601.16443)、[Uni-Agent oracle 验证](https://uni-agent.readthedocs.io/en/latest/quickstart/oracle-verification.html) | 题可解性 | ✅ 各原文 | 已是我们的 pilot 结构 | ★ 只排除硬缺陷，测不出过约束 |
| SWE-rebench V2 自动过滤 underspecified issue | [arXiv 2602.23866](https://arxiv.org/html/2602.23866v2) | 大规模自动准入的先例（32k 任务无人工） | ✅ 论文句 | — | ★ 参照系 |
| CCV：N 个隔离 session 解同一题，测解多样性 | [arXiv 2603.21454](https://arxiv.org/abs/2603.21454) | 污染 vs 真推理分离（9 题小样本 r=1.0） | ✅ 摘要原文 | 我们 run 设施即得 | ★ 附带金句：多轮复审产生假阳快于发现真错 |
| GPTZero AI 内容检测 | TB3 可选件 | 题面是否 AI 生成 | ✅ 文档提到，**未接入默认流水线** | API 收费 | ✗ 与目标无关，弃 |
| 众包专家审卷（Scale/Toloka/Snorkel 商业模式） | 各官网 | 人工 | — | — | ✗ 硬性排除 |

## 3. 排除清单及原因

- **Storm/众包服务**：违反约束（人工标注）。
- **Harden-v0 全量引入**：依赖 Harbor 任务格式+Modal/集群假设，为 ~10 题引入整套框架不值；**抄其判据与角色设计，不引其代码**。
- **"独立 solver 写测试算 agreement"作为文献方法（G4）**：检索未命中直接先例（只有泛 agreement-statistics），属方法空位——可自研但须自知无成熟背书，降级为可选探针。
- **"自动化=撤人闸"的叙事**：**被证伪**——TB ICLR 论文原文自认 *"Test case quality is not assessed via objective, automated metrics. Instead, the benchmark relies on extensive human review"*；Scale 3.0 博客口号是 *"Automated checks first … Human in the loop throughout"*。全行业共识形态=**自动闸先行 + 人工终审**，无人做到全自动入集。

## 4. 关键技术判断（分化点）

1. **分化点=证据类型，不是模型强弱**：审卷三问各对应不同最廉价可靠证据——
   - 泄题 → **静态可判定**（正则已有；补 trigram overlap(题面, fix diff+PR 文本) + judge 单问"只读题面能否复述实现"）；
   - 过约束/可推导 → **规范判据**（TB3 alignment 双向追溯 + Senior 三层清单）judge 可判，但**judge 可信度须反例集回归**（TB3 100% catch 门）；执行级铁证是 **MPE 变体率**：对原修复造 plausible-but-wrong 变体，隐藏卷放行了任何"不违反题面"的变体 → Lax 题拒收；
   - 可解性 → 我们的 pilot A-arm r1 即 oracle gate，零额外成本（Terminal-X Pass@N 同款）。
2. **人工的角色改判为"裁决证据包"**：auto 层每题产出 verdicts.json（逐判据 PASS/FAIL/证据行号），人只复核 flagged 项与 ≥10% 抽样——10 分钟/题 → ~1 分钟/题，且比裸读题面**证据更强**（裸读恰是 16.4% flawed Verified 的失效方式）。
3. **防 judge 腐败纪律**：judge 用与出题/解题**不同档**模型（token-plan qwen3.8-max 审、flash 解题），盲化（不告诉 judge 这题已 sealed）；CCV 警示多轮复审假阳堆积——**审一遍，证据包说话，不加轮**。
4. 采购前必测：①我们的 t2/t3 上跑 MPE 变体管线，看现有 2 卷宽松率是否 <0.2；②judge 判据回归用 make_exam 已知的 needs-review 泄题 fixture 当反例，catch 率必须 100%。

## 5. 缺口裁决表（R4）

| # | 缺口 | 裁决 | 证据 |
|---|---|---|---|
| G1 | harden-v0 可本地跑？ | ✅ 闭合：Python≥3.12+Docker+Harbor+litellm（可指任意 provider），Apache-2.0，活跃至 2026-06 | [repo](https://github.com/few-sh/harden-v0) |
| G2 | TB3 对齐判据原文可引？ | ✅ 闭合，`test_instruction_alignment` guidance 全文已录 | [rubrics raw](https://github.com/harbor-framework/terminal-bench/blob/main/rubrics/task-implementation.toml) |
| G3 | judge 对齐量化 | ⚠️ 部分：SWE-benchify 给 judge-evasion>50% 与 N=3 flake quarantine 实配，但未公布 judge-vs-human 一致率数字（issue #85 是进行项） | [研究页](https://ai-innovation.team/SWE-benchify/)、[issue](https://github.com/Red-Hat-AI-Innovation-Team/SWE-benchify/issues/85) |
| G4 | solver-agreement 先例 | ✅ 闭合（否定性）：无直接先例，属空位；最近似=Senior 三层判据+CCV 多样性 | 本报告 §3 |
| G5 | 人机分工成规 | ✅ 闭合：自动闸→全绿才到人，人工终审是全行业形态；TB 论文自认测试质量无客观自动指标 | [CONTRIBUTING](https://github.com/harbor-framework/terminal-bench/blob/main/CONTRIBUTING.md)、[arXiv 2601.11868](https://arxiv.org/html/2601.11868v1)、[Scale blog](https://labs.scale.com/blog/terminal-bench-harder-tasks-for-better-agents) |

## 6. 推荐结论（落到我们工程）

**短期（E1 用，~半天工）**：`make_exam.py` 加装 `review_exam.py` 三段自动审——
1. 静态段（零 API）：题面↔fix diff trigram overlap；隐藏卷 N=3 flake quarantine；
2. judge 段（每题 1-2 次 claude -p，max 档）：泄题单问 + `test_instruction_alignment` 双向追溯 + Senior 三层清单，输出 verdicts.json；评审器先用 fail 反例（已知泄题 fixture + 已知弱题）做 100% catch 回归；
3. 变体段（每题 ~10 次本地 pytest + 4 次 LLM 变异）：CoHarden 4 算子对原修复造变体 → 隐藏卷宽松率，Laxity≥0.2 且 judge 确认"变体不违反题面" → 拒收。
人工闸降格：只裁决 evidence pack 中的 flagged 项 + 10% 抽样签字。**t2/t3 即首两个试跑件。**

**中期（E3/manifest 后通用）**：Cheat Trial 单跑（hacker 提示词抄 TB3 hack-trial-prompt 思想）入造卷第四道关；harden-v0 仅在票池 >50 题值得整体引入。

**长期口径**：审卷产出从"人点头"变为"可重放的证据包"——预注册 amendment 里把 derivation-review 定义改绑 verdicts.json 哈希，与本仓预注册纪律同构。

## 7. 来源列表

见上文各内联 URL（TB3 文档/rubrics/CONTRIBUTING、harden-v0、SWE-benchify 研究页+GitHub issue #85、arXiv 2607.19843、2604.01518、2603.21454、2602.23866、2601.11868、2509.16941、2503.15223、OpenAI why-no-longer + separating-signal、Snorkel Senior SWE-Bench blog、APIFlow-Bench blog、Terminal-X、Scaling RL Environments、Uni-Agent docs、SWE-bench+ 32.67% 泄题、Aleithan、lm-eval decontamination、OpenCompass 污染指南）。
