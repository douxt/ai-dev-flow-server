# Silent Observer 进化方向

> 2026-08-06 | 基于网络调研（Reflexion / A-Mem / LLM-as-a-Judge / self-evolving agent / ERL / MAR）
> 配套阅读：[evolve.md](evolve.md)（四级路径建议初稿）· [reflection-mechanism-improvement-plan.md](reflection-mechanism-improvement-plan.md)（P1/P2 反思增强）· [reflection-layer-research-20260729.md](reflection-layer-research-20260729.md)（调研细节）

---

## 一、定位

当前能力停在三级记忆中的**存储 + 检索**两层（ChromaDB KB + `search_chat_history`），缺**评估与适应**。

进化目标不是引入重型 agent 框架，而是在现有 `default.py` + ChromaDB 上，把「经验—反馈—改进」闭环跑通。

调研结论：反思层在 2025-2026 已是标准模式，无需外部依赖；LangBot 生态**没有**现成反思/进化插件，需自建。

---

## 二、技术选型结论

| 决策点 | 结论 | 理由 |
|--------|------|------|
| 自建 vs 框架 | **自建** | Reflexion 模式轻量，200-300 行即可；框架（Letta/Mem0）需重构运行时，过度 |
| 存储 | **复用现有 ChromaDB**，新建 `reflections` collection | 零额外部署，与聊天记录 KB 同库不同表 |
| 检索 | **复用 `search_chat_history` 的语义搜索逻辑** | 已验证可用 |
| 评分模型 | **qwen3.6-flash**（已配置的视觉模型同款） | 便宜、够用，独立实例避免自我偏好 |
| 参考实现 | Reflexion（Shinn 2023）+ SuperClaude ReflexionMemory | 错误分类 + 规则学习，与群聊场景最贴合 |

**否决的方案**：
- QQ酒馆记忆插件 → 角色扮演向，记忆机制与「错误反思」不是一回事，且受插件更新节奏牵制
- Letta / Mem0 / Zep → 需引入独立 agent runtime 或图数据库（Neo4j），对群聊 bot 过度设计
- RL 训练类（Memory-R1 / Mem-α / A-Evolve） → 需训练管道，成本远超收益

---

## 三、四级进化方向（落地版）

对齐 evolve.md 的四级路径，给出具体技术落地方向与优先级。

### 第一级：反思层 ★当前聚焦

**方向**：错误被指出 → 结构化反思 → 存库 → 下次回答前检索注入。

```
写入侧（gate 中）：
  检测纠正信号 → LLM 生成结构化反思 → ChromaDB reflections collection

检索侧（inject 中）：
  当前消息语义检索 reflections → top-3 → 注入 system prompt [反思提醒]
```

反思记录结构（预留 `score` 字段供第二级）：
```json
{
  "scenario": "情景描述",
  "error_type": "错误类型（假设过多/信息滞后/答非所问...）",
  "mistake": "具体做错了什么",
  "correct_approach": "正确做法",
  "how_to_avoid": "如何避免",
  "trigger_keywords": ["触发关键词"],
  "timestamp": "2026-07-11",
  "importance": "high|mid|low",
  "score": null
}
```

**触发器**：
- 自动：@bot 且含「错/不对/纠正/更新一下」等词；bot 回答后用户紧接反驳
- 手动：`/反思` 命令

**关键设计**：
- 去重：相似反思合并，避免重复
- 分级：高频纠正自动提权
- 上限：检索 top-3，防 prompt 膨胀
- ≥3 次确认才从「一次性纠正」升级为「常驻规则」（防噪声固化）
- 与聊天 KB 分离，独立 collection

### 第二级：自我评估层

**方向**：LLM-as-a-Judge，独立模型给 bot 每条回复打分，低分触发反思，高分存正样本。

- 评分维度（从历史满意回复中提炼）：准确性 / 信息完整度 / 简洁度 / 框架先进性
- 实现：独立 qwen3.6-flash 调用，rubric 打分
- 参考：[EvalAssist (IBM)](https://ibm.github.io/eval-assist/)、[NVIDIA Judge's Verdict](https://github.com/NVIDIA/Judges-Verdict)
- 注意：用**不同模型**做评判，规避自我增强偏差；位置偏差需双向打分

### 第三级：行为策略自适应

**方向**（选路径 A 轻量级）：基于反思库高频错误类型，回答前动态组装「行为微指令」注入 prompt。

- 例：近三次电工问题都被批「假设太多」→ 出现「三相电/零线」关键词时自动追加「先确认前提假设」
- 本质是**基于经验的 prompt 动态组装**，不需模型微调
- 参考：[SCOPE](https://github.com/JarvisPei/SCOPE)（双流记忆 + prompt 进化）、[A-Mem](https://arxiv.org/abs/2502.12110)（记忆自动链接进化）
- **否决路径 B**（RL 训练记忆操作策略）：需训练管道，超出场景需求

**借鉴 QQ酒馆世界书的双通道触发机制**：

[QQSillyTavern](https://github.com/sanxianxiaohuntun/QQSillyTavern) 的「世界书」把设定分两类注入，正好是行为微指令的现成触发骨架：

| 通道 | QQ酒馆用法 | 本项目对应 |
|------|-----------|-----------|
| **常驻条目**（`constant: true`） | 始终注入的世界观 | 通用行为准则（如「简洁不啰嗦」），常驻 system prompt |
| **关键词触发条目**（`constant: false`） | 提到关键词才激活 | 情景化微指令（如「三相电」触发「先确认前提」），命中才注入 |

**只借机制不借实现**：
- QQ酒馆世界书内容是**人工写死**的静态设定；本项目的微指令由**反思库高频错误自动提炼**，动态生成
- QQ酒馆是文件式存储（`shijieshu/` 目录）；本项目复用 ChromaDB，触发关键词即反思记录里的 `trigger_keywords` 字段
- 即：用它的「常驻 + 关键词触发」双通道**结构**，喂进来自第一级反思库的**动态内容**

### 第四级：经验驱动生命周期

**方向**：暂不落地。群聊 bot 不需要自我重写 prompt / 工具集。

- 前沿参考（仅储备）：[Hermes Self-Evolution](https://github.com/NousResearch/hermes-agent-self-evolution)、EvolveR、Gödel Agent
- 判断：对本场景过度设计，一二三级闭环跑通即达目标

---

## 三-A、并行方向：对话成熟度——多轮纠正与渐进学习

> 2026-08-06 新增 | 与四级进化并行的独立方向，侧重「从对话中持续修正认知」的能力

### 问题场景

群聊中信息天然是渐进式呈现的：

```
用户 A: "这个项目周末要上线"           ← 部分信息
Bot: 基于此回答
用户 B: "不对，延期到下周了"           ← 第一次打脸
Bot: 修正理解
用户 B: "其实是甲方改需求了"           ← 第二次打脸（揭示更深的根因）
```

当前系统能检测到纠正信号，但**学不到教训**——每次纠正只影响单次回复，不会改变后续行为。核心痛点是三个阶段的问题：

1. **收不到信号**：省略句（"不对，你搞错了"）缺乏指代对象，关键词漏检率 ~95%
2. **学了用不上**：反思存了但 embedding 检索命中率低（语义距离太远）
3. **学了就忘**：反思是描述性文本，不是可执行规则，LLM 看到后不知道具体该怎么做

### 方案：P1/P2 反思增强

基于 [reflection-mechanism-improvement-plan.md](reflection-mechanism-improvement-plan.md)，四个相互咬合的改动修复三个断裂点：

#### P1.1 话语重写层（修断裂 1：收不到信号）

**原理**：Amazon 对话系统研究——省略（ellipsis）和指代（anaphora）是纠正检测漏报的最大单一来源。

```
输入: "不对，你搞错了"
  ↓ LLM 补全（~40 行代码）
输出: "不对，[bot 之前说的三相电电压是 220V] 搞错了，[实际是 380V]"
```

补全后的句子包含被纠正的具体内容和正确答案，stage2 LLM 确认时不再猜谜。**捕获率从 ~5% → ~50%。**

#### P1.2 自我反思源（扩信号源）

**原理**：Claude Code 的 side-channel 模式——不等用户纠正，每隔 N 轮自己审视自己。

```
每 10 轮: 送最近对话 → LLM 自我审视
"找出你自己的错误或不够好的地方。
 有则生成 When-Then 反思，无则回复 NONE。"
```

用户纠正是被动稀疏信号，自我反思是主动高频信号。**不是替代用户纠正，是补充**——用户纠正质量高但数量少，自我反思数量多但需去噪。

#### P1.3 检索增强：k=3→10 + LLM Rerank（修断裂 2：学了用不上）

**原理**：ERL 论文关键数据——LLM-based retrieval > embedding retrieval，召回率高 40%+。

```
当前: embedding 搜 top-3 → 可能 3 条都不相关
P1:   embedding 搜 top-10 → LLM 从 10 条挑最相关的 5 条 → 精准注入
```

额外 token 开销（~200 tok）远小于注入不相关反思的浪费。

#### P1.4 When-Then 格式增强（修断裂 3：学了就忘）

**原理**：ERL 论文核心洞见——Heuristics（When-Then 规则）> raw trajectories（原始描述）。来自认知心理学的产生式规则（production rule）：`IF condition THEN action` 比描述性文本更容易被一致执行。

```json
// 旧格式（描述性——LLM 需要自己推理出该怎么做）
{"scenario": "用户问三相电", "mistake": "混淆了电压", "correct_approach": "先确认电压等级"}

// 新格式（可执行——LLM 直接执行）
{"when": "用户在问电气相关技术问题时",
 "then": "先确认电压等级和用电场景（工业380V/民用220V），再给方案"}
```

### 闭环效果

```
用户问: "零线要不要接地？"
  → inject: embedding 检索 + LLM rerank → 命中"电气问题先确认电压"
  → When-Then 注入 → LLM 回复: "这取决于场景。你是问工业380V还是民用？"
      （而不是直接给方案）

用户纠正: "其实是 220V 家用"
  → gate: 话语重写补全 → 检测到纠正 → confirm_count+1
      （confirm_count≥3 → 反思升级为常驻规则）

下次有人问类似问题:
  → 常驻规则在 inject 时必定注入 → 不会再犯同样的错
```

**关键特性**：不是一次性修复，是持续迭代——越被纠正，反思越精准，同类型错误不会犯第三次。

### P2 延伸：反思生命周期 + 评估框架

详见 [reflection-mechanism-improvement-plan.md](reflection-mechanism-improvement-plan.md) P2 部分：

| 能力 | 触发条件 | 效果 |
|------|---------|------|
| 反思合并 | 两条反思 cosine > 0.85 | 保留高频的，合并信息 |
| 升级为常驻规则 | confirm_count≥3，来自≥2个不同用户 | 必定注入，不再需要检索命中 |
| 降权 | 30 天未被检索命中 | 降低注入优先级 |
| 归档 | 90 天未命中 | 不再参与检索（不删除） |
| A/B 评估 | 固定 eval set 对比有/无反思注入 | 量化反思对回复质量的提升 |

### 与四级进化的关系

| 维度 | 四级进化 | 对话成熟度 |
|------|---------|-----------|
| 核心驱动 | 反思写入/检索/自适应 | 纠正检测→学习→行为改变 |
| 关键指标 | 反思数量、注入命中率 | 纠正捕获率、同错误复发率 |
| 侧重点 | 能力构建（build） | 质量提升（improve） |
| 关系 | 基础设施 | 建立在反思层之上的应用 |

两条线并行：四级进化提供反思存储与检索的底座，对话成熟度在此底座上实现「从对话中学习」的完整闭环。

---

## 四、推荐路线

**路线 B：在 Silent Observer 上自建**（可控性最高）

```
gate  现流程：保存 KB → 视觉识别 → 引用提取
gate  增加后：保存 KB → 视觉识别 → 引用提取 → ★错误检测 → 反思写入

inject 现流程：时间线 → 引用提取 → 图片注入 → prompt 组装
inject 增加后：时间线 → 引用提取 → 图片注入 → ★反思检索 → prompt 组装
```

改动量估算（第一级）：
| 模块 | 行数 |
|------|------|
| 反思数据结构 | ~30 |
| 反思写入（gate） | ~60 |
| 反思检索（inject） | ~40 |
| 错误检测逻辑 | ~50 |
| 提示词模板 | ~20 |
| **合计** | **~200** |

不影响现有逻辑，纯增量。

---

## 五、参考项目清单

### 第一级直接参考
| 项目 | 用途 | 许可证 |
|------|------|--------|
| [Reflexion 论文 (arXiv:2303.11366)](https://arxiv.org/abs/2303.11366) | 理论基础 | - |
| [LangGraph ReflexionAgent](https://github.com/tanaypatil/Langgraph_ReflexionAgent) | 最简实现（draft→execute→revise） | - |
| [SuperClaude ReflexionMemory](https://github.com/SuperClaude-Org/SuperClaude_Framework/blob/af3a965d/docs/research/reflexion-integration-2025.md) | 错误分类 + 规则学习 + JSONL 持久化 | MIT |

### 第二级参考
| 项目 | 用途 |
|------|------|
| [EvalAssist (IBM)](https://ibm.github.io/eval-assist/) | LLM-as-a-Judge，rubric 迭代 + 位置偏差检测 |
| [NVIDIA Judge's Verdict](https://github.com/NVIDIA/Judges-Verdict) | 评判质量与人类一致性分析 |
| [TrustJudge](https://github.com/TrustJudge/TrustJudge) | 概率化打分，缓解评分不一致 |

### 第三级及以后储备
| 项目 | 用途 |
|------|------|
| [SCOPE](https://github.com/JarvisPei/SCOPE) | 双流记忆 + prompt 自动进化（MIT） |
| [A-Mem (NeurIPS 2025)](https://github.com/agiresearch/A-mem) | Zettelkasten 记忆自动链接权重进化 |
| [Letta (MemGPT)](https://github.com/letta-ai/letta) | OS 启发三层记忆，agent 自管生命周期 |
| [Hermes Self-Evolution](https://github.com/NousResearch/hermes-agent-self-evolution) | 执行轨迹驱动 prompt 进化（ICLR 2026） |

### 2025-2026 经验记忆最佳实践要点
- **写在回答之前**：检测到纠正后先写反思再生成回复，用户当场看到改进
- **工具无关描述**：反思内容描述「做什么」而非「用哪个工具」
- **衰减机制**：30 天未用降权，90 天归档（归档 ≠ 删除）
- **错误分类优先**：挖掘高频错误类型比记录偶发成功收益更大稳定（SAMULE 三级反思）
- 来源：[Self-Reflective Agents 用日志改进](https://yodaplus.com/blog/how-self-reflective-agents-use-logs-to-improve/)、SAMULE、SpecWeave Reflect

---

## 六、执行优先序

### 四级进化线

1. **第一级（✅ 已实现）**：反思写入 + 检索闭环，路线 B 自建，~200 行
2. **第二级（1-2 周）**：LLM-as-a-Judge 打分，低分触发反思
3. **第三级（1 月）**：高频错误类型 → 行为微指令动态组装
4. **第四级**：不落地，仅储备

### 对话成熟度线（并行）

1. **P1（本周可做）**：话语重写 + 自我反思源 + When-Then 格式 + LLM Rerank，~185 行
2. **P2（2-4 周）**：反思生命周期管理 + A/B 评估框架，~200 行
3. **P2.3（2 月，依赖标注数据积累）**：纠正检测分类器（RoBERTa）

> 两条线的关系：对话成熟度的 P1/P2 直接建立在四级进化的第一级（反思层）之上。第一级提供了反思存储和检索的底座，对话成熟度在此底座上实现「从对话中学习」的完整闭环。
>
> 推荐先做对话成熟度 P1——改动量最小，直接解决「反思系统收了信号但学不进去」的问题，让已有的反思基础设施产出实际价值。
