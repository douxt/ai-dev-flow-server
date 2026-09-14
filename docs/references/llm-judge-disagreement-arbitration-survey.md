# 双 LLM-judge 分歧仲裁与"可推导性"标尺 调研报告

> 2026-09-14 · 方法 L4（R1 广度 10 路 → R2 深挖 3 篇承重原文；R3 终裁并入 R2 量化；R4 缺口递归未启动，理由见 §4.5 收益闸门） · 场景：E1 考卷"推导审查"用 qwen(主)+deepseek(二审) 并行全审、三态仲裁（both-PASS 自动绿 / both-FAIL 判废 / 分歧升人），求此机制的业界依据与正确参数，替代拍脑袋 · 硬约束：一手论文/官方文档，排除纯博客作为唯一证据

## 1. 术语对照

| 英文 | 中文 | 区分项 |
|---|---|---|
| selective evaluation / abstention | 选择性评估/弃权 | judge 可拒绝判定并升级，非强出结论 |
| Trust-or-Escalate | 信任或升级 | 有统计保证的"何时交人"框架 |
| Simulated Annotators | 模拟标注员 | 同模型多次采样、以自一致率估置信度 |
| Condorcet jury theorem | 孔多塞陪审定理 | 多数票有效的前提=独立+优于随机 |
| Kish effective sample size n_eff | 有效独立样本量 | 面板"名义 N 票、实际 ~n_eff 独立票" |
| correlated errors / artificial hivemind | 相关误差/蜂群效应 | 模型在相同题目犯相同错 |
| inter/intra-rater agreement (Cohen/Fleiss/Krippendorff) | 评审者间/内一致性 | chance-corrected，非裸一致率 |
| false-negative (FN) / under-specified (US) | 假阴（正确解被判错）/题面欠定 | 基准缺陷分类学两轴 |
| over-specification | 测试过约束 | 断言钉死题面未要求的实现细节 |

## 2. 候选方案对比总表（每格有出处）

| 方法 | 出处 | 机制 | 对 E1 适配 |
|---|---|---|---|
| 双 judge 并行 + 分歧升人 | orq.ai、Braintrust、W&B、Kili（一致口径）| "分歧即信号，路由给人" | ✅ 已实现，方向被业界共识背书 |
| Trust-or-Escalate（置信弃权） | arXiv 2407.18370 (ICLR'25) | 自评置信 + 风险 α + 校准集 → **可证明**人工一致率 | ⭐ 比"分歧才升"更严，应采纳其精神 |
| Simulated Annotators | 同上 | 同 judge 采 N 次、自一致率=置信度 | ⭐ 廉价可落地：抓"两审都自信但都错" |
| Cascaded Selective Eval | 同上 | 便宜模型先判、低置信升强模型 | ✅ 契合省人力：flash 先筛、max/pro 只在必要时 |
| 面板 n_eff≈2 警告 | arXiv 2605.29800 (Nine Judges…) | 相关误差：9 judge≈2 独立票，一致最不可信 | ⚠️ **核心约束**：别指望堆 judge 数量 |
| FN/US 缺陷分类学 | Can LLMs Detect Benchmark Defects? (ICML'26) | 文本层缺陷 LLM 可检出、省人工 | ✅ 印证"自动审值得做"；给判据词汇 |
| 执行级审计 | SWE-ABS 2603.00520 / BenchGuard 2604.24955 / STING | 变异/对抗**跑代码**验测试强度 | ✅ 已实现 S2/S3，属最强独立证据 |
| 期望缺陷率基准 | OpenAI SWE-bench Verified 审计 | 38.3% 题欠定 / 61.1% 测试有失 / 35.5% 钉实现 | ✅ 校准用：judge 报过约束是常态，非异常 |
| κ<0.6 判据太糊 | galileo / Arize | 人-人一致性 <0.6 说明任务定义太糊、判不了 | ✅ 用于校准我的判据措辞 |

## 3. 排除/存疑清单

- **"judge 数量越多越准"**：**证伪**。2605.29800 实测加到 9 票仅 ~2 独立信息量，最佳单 judge ≈ 或 > 面板；扩面板不能替代真独立性。
- **"两模型一致即可靠"**：**证伪**。一致同意项错误率 ~9.1%（独立假设应 0.02%）；unanimity 是最不可信的信号。
- **"分歧即知谁对"**：**部分证伪**。论文指 cross-model disagreement 本身因相关误差而不可靠——分歧=**模糊信号**，指示"该题该给人看"，不指示"某一 judge 正确"。
- **商用众包仲裁 / 单一"0.6 通过线"阈值**：排除（前者违反约束，后者被 Arize 明确警告"勿用通用阈值，随任务校准"）。

## 4. 关键技术判断（分化点）

4.1 **真正独立的信号是"执行"不是"意见"**。2605.29800 的处方是"推理多样化"而非更多模型；对本场景，最"异质"的判定者不是第三个 LLM，而是**确定性执行**（S2 flake、S3 变异跑测试、S4b 二审查的是补题忠实性）。→ 权重：执行证据 > 双 judge 意见 > 单 judge 意见。

4.2 **仲裁应三态+置信四态**。业界（Trust-or-Escalate）给的是"置信不足即弃权升级、且保证可控"，比"一致即过"更稳。落地最小版：每 judge 采样 K 次（Simulated Annotators），自一致率 < τ_conf 时**即便双 judge 结论相同也降级 need-human**（堵相关盲区）。

4.3 **人闸不可撤、但降频**。全行业（Braintrust/Kili/OpenTrain）共识=分层路由"规则→judge→人"，**共识绿仍小比例抽检**防静默漂移。这正对应"你扫一眼"的决定——现在有文献背书，非保守主义。

4.4 **过约束告警是预期内**。OpenAI 实测原始任务 ~61% 的测试有失、35.5% 钉实现——deepseek 对我的卷子报 overconstraint/overtrim **是正常检出率**，不是我的工具误报，反过来佐证自动审在做实事。

4.5 **收益闸门（未继续 R4 及原因）**：R2 三篇已把"如何仲裁、什么阈值、judge 天花板"三个决策必需量全部闭合（n_eff、9.1% 一致错误率、Simulated-Annotators 置信法、级联、38/61/35% 基准）；无 ≥3 条未闭合缺口，R4 递归边际价值低于继续执行主线，故停。

## 5. 落地结论（写进 review_exam 的改造）

短期（本次）：
1. **加 `--judge-samples`（默认 1，高保证设 3）**：同 judge 多采、自一致率当置信；arb 里 both-PASS 但任一 judge 自一致 <τ → 降 need-human。
2. **arb 权重声明**：执行段(S2/S3)FAIL 恒定 flagged，优先级高于 judge 意见（judge 说 PASS 也救不回执行挂）。
3. **报告字段固化 `effective-independence 警告`**：verdicts.json 注明"双 judge≈弱共识，非独立证明"，防我/你过度信赖绿色。

中期（E1 跑期）：级联省人力——flash 先审易题，低置信才升 max/pro；建 5-8 张人标"黄金小卷"测 judge-vs-人 κ，κ<0.6 的判据回炉改措辞。

## 6. 来源

见 §2/§3 内联：arXiv 2605.29800、2407.18370、2603.00520、2604.24955、2605.26079、Can-LLMs-Detect-Benchmark-Defects(OpenReview QdDcI0Ftvo)、OpenAI SWE-bench Verified 审计、orq.ai/Braintrust/W&B/Kili/Arize/galileo、MT-Bench 80%/领域 60-68% 一致率。
