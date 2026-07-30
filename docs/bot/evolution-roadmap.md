# Silent Observer 进化方向

> 2026-07-11 | 基于网络调研（Reflexion / A-Mem / LLM-as-a-Judge / self-evolving agent）
> 配套阅读：[evolve.md](evolve.md)（四级路径建议初稿，不改动，本文档为落地方向）

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

1. **第一级（本周可做）**：反思写入 + 检索闭环，路线 B 自建，~200 行
2. **第二级（1-2 周）**：LLM-as-a-Judge 打分，低分触发反思
3. **第三级（1 月）**：高频错误类型 → 行为微指令动态组装
4. **第四级**：不落地，仅储备

> 群里的「零」「喵酱」事实上已在充当评估者。每次他们指出漏洞就是免费训练信号，把这些信号结构化存下来即已启动自主进化。
