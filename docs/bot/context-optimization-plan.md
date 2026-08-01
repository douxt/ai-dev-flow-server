# Bot Context 优化方案

> 2026-08-01 | 基于 2025-2026 行业最佳实践调研
> 前置分析：LLM 平均耗时 9.3s，输入 8741 tokens，57% 被对话历史占据

## 现状数据

| 指标 | 值 |
|------|----|
| 平均输入 token | 8741 |
| 平均输出 token | 114 |
| 输入:输出比 | 77:1 |
| 平均 LLM 耗时 | 9.3s |
| 最精简请求（重启后） | 3008 tokens |
| 活跃对话 | 8995-9192 tokens |

### Context 组成

```
  System prompt (persona + rules)      425 tok    6.0%
  Silent observer injection            800 tok   11.4%
  ★ 对话历史 (40轮)                  ~4000 tok  56.9%
  KB 检索结果 (5条×2KB)              600 tok    8.5%
  RAG template + user msg             500 tok    7.1%
  工具定义 + 其他开销                 700 tok   10.0%
  ─────────────────────────────────────────────────
  TOTAL                              ~7000 tok  (实测~9000)
```

---

## 优化路线

### P0 — 立即可做（不改架构，纯配置调整）

**1. history_count 40→20**

当前 silent observer `history=40` 行，从 2 天前的消息开始。改成 20 行直接砍半历史 token。

- 预估省：~2000 tokens (22%)
- 成本：改 1 行配置

**2. System Prompt Caveman 化**

当前 1275 字符。去掉礼貌用语、连接词、人读舒适的填充——保留所有规则、枚举值、工具名。Mantel Group 实测 ~35% token 省，质量不降。

```
改前：当你在处理用户问题时，如果信息不完整，你应该先确认再回答，不要猜测。
改后：信息不完整 → 先确认再答。禁止猜测。
```

- 预估省：~500 tokens (6%)
- 成本：改写 prompt 文本
- ref: [Reducing AI token consumption the Caveman way](https://mantelgroup.com.au/reducing-ai-token-consumption-caveman-method/)

**3. Bot 旧回复截断**

`_format_timeline` 把 bot 长篇回复全文塞进历史，每条可超过 200 字。加截断：bot 消息超 100 字的部分用 `...[已截断]` 替代。

- 预估省：~800 tokens (9%)
- 成本：改 `_format_timeline`

### P1 — 短期可做（小改动，大效果）

**4. Head-Middle-Tail 架构**

所有生产系统（Hermes、Claude Code、Microsoft Agent Framework）的通用模式：

```
Head  → System prompt（永久保留原文）
Middle → 旧消息 → LLM 摘要（替代原文）
Tail   → 最近 5-10 轮（保留原文）
```

silent observer 已有 timeline 注入机制——差在 Middle 没有做摘要，而是原文全量保留。

- 预估省：~2000 tokens (22%)
- 成本：silent observer 加摘要逻辑
- ref: [How Hermes and Claude Handle Context Compression](https://mem0.ai/blog/how-hermes-and-claude-handle-context-compression-in-real-production-agents)

**5. 摘要用便宜模型**

Chronicle-Gist、ReCompress 的结论：Llama 3 8B / GPT-4o-mini 做摘要效果足够，成本极低。可用百炼免费 Qwen 模型。

- 不增省 token，但降摘要成本
- 成本：配一个额外 API endpoint
- ref: [ReCompress: Query-Aware Rewriting and Tiered Memory](https://zenodo.org/records/20786357)

### P2 — 中期可做（需开发）

**6. Multi-Fidelity 记忆（AFM 方案）**

给每条消息打分（语义相似度 + 时间衰减 + LLM 重要性判断），分三级：
- **FULL** — 与当前问题相关，原文保留
- **COMPRESSED** — LLM 摘要
- **PLACEHOLDER** — `[第12轮: 讨论过数据库schema]`

AFM 在基准测试中**省 66% token**，同时保留了关键事实（如过敏信息）不被丢弃。

- 预估省：~2000 tokens (22%)
- 成本：新建评分模块
- ref: [Adaptive Focus Memory for Language Models](https://ar5iv.labs.arxiv.org/html/2511.12712)

**7. Progressive Summarization（增量更新）**

不是每次触发压缩都重摘要全部历史，而是增量更新一份持续摘要。ICML 2026 C-DIC 方案维持了近常数推理时间。

- ref: [Context-Driven Incremental Compression for Multi-Turn Dialogue Generation](https://icml.cc/virtual/2026/poster/63188)
- ref: [Distilling from Dialogues: Finding Meaning in LLM Interactions](https://huggingface.co/blog/chansung/adaptive-summarization)

---

## 关键原则

来自 2025-2026 生产系统共识：

1. **50% 触发，不是 85%**。满仓再压会丢信息，Hermes 和 Microsoft Agent Framework 都用 50% 阈值。
2. **选择 > 摘要**。保留原文比让 LLM 重写安全——JetBrains 发现摘要导致 agent 多走 13-15% 步骤。
3. **先做便宜的确定性优化**（截断、去重、去 bloat），再做 LLM 摘要。这是多层防线策略。
4. **摘要后验证**——审查是否丢失了关键约束（数字、禁令、决策原因）。
5. **分离存储与呈现**：保持完整不可变日志在存储中，每次发给 LLM 的是优化后的视图。
6. **KV-Cache 友好排序**：系统 prompt 最前不变 → 工具定义 → 历史 → 动态内容最后。
7. **Anti-Thrashing**：连续 2 次压缩省不到 10% token → 锁定压缩直到新会话。miniHermes 加 60 秒冷却期。
8. **写前提取**：压缩前先把关键事实写入持久存储（如 LTM），确保压缩丢不掉。
- ref: [Context Window Management for Long-Running Agents](https://machinelearningmastery.com/context-window-management-for-long-running-agents-strategies-and-tradeoffs/)
- ref: [LLM Context Budget Optimization](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering/blob/7a95d94c/skills/context-optimization/SKILL.md)
- ref: [Automatic Context Compaction (Anthropic)](https://platform.claude.com/cookbook/tool-use-automatic-context-compaction)
- ref: [Structurally Lossless Trimming (CMV)](https://ar5iv.labs.arxiv.org/html/2602.22402)

---

## 预期效果

P0+P1 四项落地后：

| 指标 | 当前 | 优化后 |
|------|:---:|:---:|
| 平均输入 token | 8741 | 4000-5000 |
| 平均 LLM 耗时 | 9.3s | 3-5s |
| 输入:输出比 | 77:1 | 35:1 |

---

## 参考链接

- [Reducing AI token consumption the Caveman way](https://mantelgroup.com.au/reducing-ai-token-consumption-caveman-method/)
- [How Hermes and Claude Handle Context Compression](https://mem0.ai/blog/how-hermes-and-claude-handle-context-compression-in-real-production-agents)
- [Adaptive Focus Memory for Language Models](https://ar5iv.labs.arxiv.org/html/2511.12712)
- [ReCompress: Query-Aware Rewriting and Tiered Memory](https://zenodo.org/records/20786357)
- [Context-Driven Incremental Compression (ICML 2026)](https://icml.cc/virtual/2026/poster/63188)
- [Automatic Context Compaction (Anthropic)](https://platform.claude.com/cookbook/tool-use-automatic-context-compaction)
- [Context Window Management for Long-Running Agents](https://machinelearningmastery.com/context-window-management-for-long-running-agents-strategies-and-tradeoffs/)
- [LLM Context Budget Optimization](https://github.com/muratcankoylan/Agent-Skills-for-Context-Engineering)
- [Structurally Lossless Trimming (CMV)](https://ar5iv.labs.arxiv.org/html/2602.22402)
- [SuperCompress: Query-Aware Context Compression](https://github.com/Supercompress/Supercompress)
- [Which Agent Memory Approach Is Best for Long Conversations?](https://blogs.oracle.com/developers/which-agent-memory-approach-is-best-for-long-conversations)
- [Distilling from Dialogues (Hugging Face)](https://huggingface.co/blog/chansung/adaptive-summarization)
