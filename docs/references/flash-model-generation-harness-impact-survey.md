# Flash 档模型换代（架构变更）对 Harness 的影响：社区实践调研（L4）

> **日期**：2026-09-12 · **方法**：gale-research L4（R1 广度 10 路 → R2 一手深挖 7 源 → R3 终裁 → R4 缺口递归 5 条），实际 14 搜索 / 8 抓取
> **场景**：用户具体命题——"DeepSeek V4.1-Flash（换架构 CED）、Qwen3.8-Flash-Next（换架构 QSA）这类**同档模型换代**，能力与'性格'巨变后，harness 该受到什么影响、社区怎么应对？" 这直接决定 DevFlow 模板体系（为现役模型校准的一切）在换代时的维护协议。
> **硬性排除**：纯跑分新闻、无操作细节的观点文
> **读取范围声明**：一手·全文=完整读取（DeepSeek 官方公告、Qwen3.8-Flash-Next 官方模型卡、Cursor 官方博客、Scaffold Ablation 模式页全文、MindStudio 维护文全文、DarwinX 摘要）；Reddit/HN 帖为摘要转引。**V4.1-Flash 发布仅 2 天（9/10），其"第一周 Claude Code 实录"尚不存在**——本报告显式区分"V4.1 直接证据"与"换代冲击的同类先例证据（V4 首发、Opus 5 代、Anthropic postmortem）"。

---

## 1. 术语对照表

| 中文 | 英文 | 区分项 |
|---|---|---|
| 脚手架消融 | **Scaffold Ablation on Model Upgrade**（别名 Harness Assumption Review / Scaffold Decay Review） | 社区已命名的换代应对模式——本次调研的核心发现 |
| 组件=假设 | encoded model-limitation assumption | 每个 harness 组件都编码着一条"当前模型做不到 X"的假设，**假设静默过期** |
| 默认行为面 | behavioral defaults surface | 换代冲击的第二层：`reasoning_effort`、`enable_thinking`、**`preserve_thinking`**、采样参数、输出预算 |
| 协议兼容面 | protocol compatibility surface | 第一层：tool call 参数形态（JSON string vs object）、流式续传、`tool_choice=required`、structured output |
| 性格 | temperament / personality（社区用词） | 可观测行为向量：啰嗦度、指令遵从风格（字面 vs 意会）、拒答阈值、重试倾向——**与跑分解耦** |
| 模型-脚手架拟合 | model-harness fit | Salesforce 论文正式化：围绕某模型原生规划风格调出的 harness，换训练/换模型都可能错配 |
| 上下文焦虑 | context anxiety（Cursor 命名） | 特定模型怪癖：窗口将满就开始拒绝工作——**用 prompt 缓解，属 harness 职责** |
| 静默路由 | silent redirect | `deepseek-v4-pro` 这个**名字不变、模型变**（9/14 起路由到 V4.1-Flash）——pin 了名字 ≠ pin 了行为 |

## 2. 候选对比总表

### 2.1 两个主角换代的"性格变更点"（官方一手）

| 维度 | DeepSeek V4.1-Flash（9/10） | Qwen3.8-Flash-Next（8/26 preview） |
|---|---|---|
| 架构 | 全新 CED 因果编码-解码（非点版本，官方系"新架构家族最小成员"）；552B MoE/8B 激活 | Qwen4 架构预演：QSA 块级稀疏注意力 + Gated Residual + N-gram Embedding；125B/6B 激活 |
| **对 harness 最重的默认** | KV cache 1/4 HBM / 1/8 SSD，**官方明言"缓存命中占 agent 成本大头"**→ 计费结构变化（peak $0.15/$0.6，off-peak 半价，cache hit $0.003） | **默认思考开启 + 默认 xhigh + 默认 `preserve_thinking=True`（整个会话的历史思考块全部保留进上下文！）**——官方理由："agent 场景决策一致性 + 提高 KV 利用率" |
| 官方自带警告 | Pro 身份被路由替换（9/14）；V4-Flash 名字退役 | **"多轮 agent 任务里，降低 reasoning effort 不一定缩短总时间"**（少思考→失败重试反而更贵）——模型方在给 harness 方上课 |
| 社区首周冲击 | 集中在**协议面**：NIM 流式 tool call 不续传（arguments 恒为 string）、cc-router thinking+tools 400、`tool_choice=required` 被拒、vLLM response_format 崩——**不是质量差，是兼容层碎** | 集中在**默认面**：单轮 13 分钟 ~7000 token 思考的啰嗦抱怨；sglang `qwen3_coder` parser 死循环 bug（新架构 × 旧解析器）|
| 能力面（官方自评，注意 harness 口径） | Terminal-Bench 90.6 / DeepSWE 74.2（超自家前代 Pro）| DeepSWE 58.7 > V4-Flash 54.4；IFBench 81.3；自曝"在 mini-SWE-agent 上表现最好"（=承认 harness 敏感）|

### 2.2 换代冲击的统一图景（三层爆炸半径，跨案例稳定）

| 层 | 碎什么 | 案例 |
|---|---|---|
| **① 协议/兼容层**（先碎） | tool 格式、流式续传、structured output | V4 系首发时 cc-router #1378"N4 Pro+thinking 一动 tool 就 400"；Qwen3.8 新架构 × qwen3_coder parser 死循环；Cursor 证言："给模型用错 tool 格式（patch vs string-replace）**多花推理 token、多出错误**" |
| **② 默认行为层**（碎预算） | reasoning effort / thinking 保留 / 啰嗦度 / 采样默认 | Qwen3.8 三默认；Anthropic postmortem：**为降 verbosity 加的一条 system prompt 反而伤 coding 质量、3% eval 回测、六周才被用户抱怨定位**；Opus 5 代 verbosity+"忘了上下文里的指令"实录 |
| **③ 能力面**（最后、最不易碎） | 真做对了/做错了什么 | V4.1 Pro→Flash 路由后多数工作流报告"更省更好"；但**方向可逆**——Opus 5 被大票用户判"practically unusable"回滚 4.8，"升级=降级"实证成立 |

**推论（模型无关）**：换代时**先测协议面与默认面，再测能力面**；把换代当"新模型接入"而非"版本+1"。

### 2.3 社区的应对模式（一手操作细节）

| 模式 | 操作内容 | 出处 |
|---|---|---|
| **Scaffold Ablation on Model Upgrade**（正式命名） | 每个组件贴"补偿哪代模型哪个弱点"标签 → 换代时逐组件**临时摘除跑 eval**：通过=假设过期、删除；回归=假设仍成立、保留。**eval 套件是闸门**；policy/安全组件豁免消融 | agentpatternscatalog 模式页全文；known uses：Anthropic（删 sprint 构造）、Cursor（拆早期 guardrails）、Osmani |
| **删光重建**（消融即评测） | Boris Cherny（Claude Code 作者）：每个新模型发布**删掉 system prompt 从零重建**而非编辑；"删 80%"公开宣讲 | YC Startup School 演讲 + 转写 |
| **per-model 深定制**（工业标准） | Cursor：拿到新模型**数周定制**——tool 格式按训练格式配、prompt 按版本调、**错误基线按 per-tool×per-model 分算**（不同模型搞砸 tool 的速率不同）、"context anxiety"类怪癖用 prompt 缓解、会话中切模型要注入"接管声明" | Cursor 官方博客全文 |
| **pin + 计划内升级窗口** | 七步 SOP：pin 精确版本→新模型进**影子环境**跑契约测试→修 harness→**先部署新 harness 再切模型**→48h 加密观察；"pinning is a delay, not a strategy" | MindStudio 维护文 + 企业 pinning 政策页簇 |
| **回滚产品化** | Claude Code v2.1.161–167 官方加 `fallbackModel` 链（最多 3 个）+ Safe Mode——把"回到已知-good 模型"做成配置 | digitalapplied 解读 + 官方 docs |
| **自动 harness 进化**（学术前沿） | DarwinX：模型冻结、harness 种群自然选择，+17pp 均值、跨 benchmark 迁移；显式提出"换代时 harness 演化是**经常性成本还是摊销成本**"问题；HarnessX/Co-Evolving：弱模型受益大、模仿破坏 fit | arXiv 2608.07545 / 2606.14249 / 2609.09134 |

### 2.4 观测缺口的社区自认

- claude-code-action **#1394**：*"No way to detect run quality regression after model update"*——连 Claude Code 官方自动化都没有换代回归检测，抱怨无信号。
- Anthropic postmortem 自认：三个变更**没有一个被内部 eval 拦住**（最后一个才测出 3%），全靠用户骂了六周。
- tianpan 中文圈同款：真正能拦 PR 的 prompt 回归测试刚出现；阿里开源 skill-up 补 agent skill 回归。**结论：换代回归检测是当前全行业的空白件，谁先建谁受益。**

## 3. 排除清单及原因

| 候选 | 排除 |
|---|---|
| V4.1-Flash 各跑分博客（flowtivity/kingy/buildfastwithai 等） | 数字转抄官方，无 harness 视角增量；仅 orcarouter "新基座非点版本、无第三方 serving 验证"一句保留为风险注记 |
| "Flash 取代 Claude" 类 YouTube/FB 营销 | 无方法 |
| 中文 harness-engineering 教程群（六层/十二模块） | 概念文；仅保留 aihao《会过期的 Harness》与 Paul Kuo《Harness 会过期，Criteria 会复利》作 L2.3 模式的中文独立复现 |
| 已证伪检索：**"换代后 harness 自动兼容无需动作"的正向证据** | 不存在。全部案例都是"要么 ablating 要么事故"，中间态没有 |

## 4. 关键技术判断

### 4.1 分化点：**换代冲击的持续性靠"默认值"，不靠"能力"**

两个主角的官方文档都说明一件事：**模型厂商正在把 harness 行为写进 API 默认**——`preserve_thinking` 的官方理由直接是"agent 场景 + KV cache 利用率"，`reasoning_effort` 的警告直接是"别以为调低就省时间"。也就是说：
- 换代对 harness 的最大冲击不是"它更强了你该少管"，而是**"它的思考预算怎么流动，厂商替你改了默认而你不知道"**；
- V4.1 的 KV cache 压缩 1/8 + cache-hit 定价 $0.003——**换代重写了我们的成本方程**（hook 注入量、CLAUDE.md token、防抖策略的经济性全要重算）。

### 4.2 "性格"是可测量的对象，且有专名了

社区给"换代性格漂移"的操作定义=三层清单：协议面（tool 格式/流式/structured output 兼容性测试）、默认面（reasoning/thinking/verbosity/输出预算 的显式覆盖测试）、能力面（现有 eval）。**"换模型像换依赖：先跑 contract test 再合并"已成文。**

### 4.3 对 DevFlow 的四条具体改造（可测项）

1. **`.devflow/config.yaml` 的 model 引用是雷区**：`deepseek-v4-pro` 9/14 起静默变 V4.1-Flash。**动作**：全租户 grep model 引用，改 pin 到带日期的具体版本名，并在平台文档标注"名字稳定 ≠ 行为稳定"（DeepSeek changelog 是公开路由的正面案例，但多数厂商不公告）。
2. **模板组件加"假设注释"**（Scaffold Ablation 的 DevFlow 落地）：`config-templates/default/CLAUDE.md`、`base.append`、各 hook 的每条规则，标注它补偿的模型弱点或它声明的流程纪律（后者=pattern 里"policy 豁免消融"类）。换代评审时逐"补偿类"标注项做摘除测试——**这与 DEFECT-019 的一致性校验是同一套机器检查的两用件**。
3. **E1 的固定子集升格为"换代回归套件"种子**：阶段四的 50 题/影子评估机制，换代必跑（Cursor 七步 SOP 的 DevFlow 版）——正好补 #1394 指出的全行业空白，做完即 DEFECT-011（漂移观察）的正解。
4. **成本模型按代重算**：V4.1 的 cache-hit 定价 + KV 压缩意味着"多注入上下文"变便宜、而（Qwen 线的）`preserve_thinking` 累积意味着"历史思考块"变贵——**不同厂商换代的符号相反**，不存在"换代=更省"的先验。

## 5. 缺口裁决表（L4）

| # | 缺口 | R4 动作 | 裁决 |
|---|---|---|---|
| G1 | V4.1-Flash 在 Claude Code 的第一周实录 | 定向检索 | **未闭合（时间原因）**：发布 2 天，现存实录全部针对 V4 Flash 0731；已获先例证据链（V4 首发协议碎裂清单）可外推，**9 月底复审一次** |
| G2 | 换代是否存在"变差"证据 | 定向检索 | **已闭合（正向存在）**：Opus 5 代大规模回滚实录+可复现 issue #83510+Anthropic 自认 verbosity 修改伤质量——"升级可逆性"有硬案例 |
| G3 | Qwen3.8 `preserve_thinking` 对 agent 的实际成本 | 官方模型卡 | **已闭合（机制）/**存疑（量级）：官方定性"有益 agent+省 KV"，社区单点报 7000 token/轮啰嗦——**方向两说，需自己测**（进 4.3-3 回归套件的用例） |
| G4 | 换代回归测试的工业实践样本 | R2 已获 | **已闭合**：Cursor（shadow+per-model baseline）/pin-七步 SOP/fallbackModel 产品化；反例 #1394 确认工具空白 |
| G5 | **架构变更**（CED/QSA）对行为影响的直接研究 | 检索 | **未闭合**：不存在。冲击全部经协议面/默认面中介（§2.2 三层图景即为替代解释框架）——如实记 |

## 6. 推荐结论

**对用户的直接回答：**
1. **"模型变强了 harness 就要瘦身"这个先验，方向对但机制错**——社区证据显示换代冲击大头**不是能力而是兼容性与默认值**；瘦身（ablation）需要 eval 闸门，**没有回归套件的瘦身=换事故**。
2. **架构换代后 harness 模式的正确姿势已成型为可命名协议**：三层爆炸半径逐个测（协议→默认→能力）→ 组件按假设标签逐项 ablation → policy 类豁免 → pin 与影子评估。**这个概念有名字（Scaffold Ablation on Model Upgrade），有工业参照（Cursor 数周定制/per-model 基线），有反例警告（Anthropic 六周、Opus 5 回滚），有学术自动化路线（DarwinX）——但没有任何人有"换架构后不用重调"的证据。**
3. **对 DevFlow 最紧急的一条**：9/14 `deepseek-v4-pro`→V4.1-Flash 静默路由**就在本周**——现役校准过的整个模板体系对"新底层模型"零验证。**建议动作独立于 E0 决策：立刻做租户 model 引用审计 + 用 E1 的固定子集在 V4.1-Flash 上跑一轮影子评估**（这同时就是换代回归套件的首次实战，DEFECT-011 正解）。

**分期**：短期=上条 1+4.3-1；中期=模板假设注释体系（接 DEFECT-019 同一机器检查）+换代 SOP 入 knowledge/；长期=harness 版本化回归纳入 bats 矩阵（DarwinX 的自动化方向作为观察项，不预付）。

## 7. 来源列表

**一手·全文**
- DeepSeek 官方 V4.1-Flash 公告（CED/路由/KV/定价）— https://www.deepseek.com/en/news/deepseek-v4-1-flash/ ｜API changelog — https://api-docs.deepseek.com/updates/
- Qwen3.8-Flash-Next 官方模型卡（三默认/preserve_thinking 理由/effort 警告/按 harness 报分）— https://huggingface.co/Qwen/Qwen3.8-Flash-Next
- Scaffold Ablation on Model Upgrade（模式全文）— https://github.com/agentpatternscatalog/patterns/blob/main/patterns/scaffold-ablation-on-model-upgrade.md
- Cursor《Continually improving our agent harness》（per-model 定制/per-tool×model 基线/context anxiety/切模型声明）— https://cursor.com/blog/continually-improving-agent-harness
- MindStudio《AI Agent Harness Maintenance》（四层破坏/四原则/七步升级 SOP）— https://www.mindstudio.ai/blog/ai-agent-harness-maintenance-model-improvement
- Anthropic《An update on recent Claude Code quality reports》postmortem — https://www.anthropic.com/engineering/april-23-postmortem
- DarwinX 摘要 — https://arxiv.org/abs/2608.07545 ｜Co-Evolving 摘要（前轮已读全文）— https://arxiv.org/abs/2609.09134
- Superpowers #2017《Retuning SDD for Opus 6 and Sol 5.6》+ 6.0 release notes（换代→重写 reviewer）— https://github.com/obra/superpowers/issues/2017

**一手·部分 / 摘要转引**
- HN V4.1 发布帖 — https://news.ycombinator.com/item?id=49624603 ｜orcarouter"新基座非点版本"— https://www.orcarouter.ai/blog/deepseek-v4-1-new-base-model
- 协议面碎裂簇：NIM 流式 tool call — https://forums.developer.nvidia.com/t/deepseek-v4-pro-v4-flash-on-nvidia-nim-streaming-tool-calls-do-not-continue-in-claude-code-anthropic-compatible-agent-workflow/368085 ｜cc-router #1378 — https://github.com/musistudio/claude-code-router/issues/1378 ｜DeepSeek-V3 #1376（tool_choice=required）｜vLLM #51467 ｜SGLang #36537（qwen3_coder parser 死循环）
- 默认面：r/LocalLLaMA Qwen3.8 啰嗦 13min/7000tok — https://www.reddit.com/r/LocalLLaMA/comments/1w9nfx8/ ｜simonwillison Qwen3.8-27B overthinking — https://simonwillison.net/2026/Aug/16/qwen-38-27b/ ｜moclaw effort=xhigh 定位
- 升级=降级：#83510 可复现回退+未披露 fallback — https://github.com/anthropics/claude-code/issues/83510 ｜Opus 5 unusable/rollback 帖群（r/ClaudeCode 1veeuy5、r/Anthropic 1v6r82w、companionlink Great Rollback）｜claude-code-action #1394 无换代检测 ｜fallbackModel 产品化 — https://www.digitalapplied.com/blog/claude-code-safe-mode-fallback-models-production-resilience-guide
- V4 系一周实录 — https://www.reddit.com/r/ClaudeCode/comments/1t5xm50/ ｜tool calling tighter than Claude — https://www.reddit.com/r/DeepSeek/comments/1tuhm0z/ ｜harness showdown — https://www.reddit.com/r/LocalLLaMA/comments/1v7d8px/
- Boris Cherny 删 80%/删光重建 — https://www.youtube.com/watch?v=qyPCVqFUyDo（转写 sozai.app）
- 中文复现：会过期的 Harness/Model-Harness-Fit — https://blog.aihao.tw/2026-06-26/harness-engineering-8-model-harness-fit/ ｜Harness 会过期 Criteria 会复利 — https://paulkuo.tw/articles/harness-criteria-compounding/ ｜prompt 回归拦 PR — https://tianpan.co/zh/blog/2026-04-18/prompt-regression-tests-that-block-prs ｜skill-up — https://cloud.tencent.com/developer/article/2718421
- Anthropic 长任务 harness 设计（删 sprint 构造的 known-use 原典）— https://www.anthropic.com/engineering/harness-design-long-running-apps
- pinning 政策/影子升级簇：digitalapplied 一页 pin 政策 ｜Restate 在飞执行锁版本 ｜safjan "pin 名≠pin 行为" — 检索节选
