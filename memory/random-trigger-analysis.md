---
created: pre-2026-07
name: random-trigger-analysis
description: 随机插话功能的技术困境与尝试全记录
metadata: 
  node_type: memory
  type: project
  originSessionId: ce5705ee-9449-4465-9669-d16ceba28729
---

# 随机插话功能 — 问题分析与尝试记录

> 2026-07-08

## 目标

bot 以低概率（10%）主动评论群聊内容，不依赖 @ 触发。评论应为自由形式，不拘泥于触发消息。

## 架构约束

LangBot Pipeline 的消息模型：

```
[system] 系统 prompt（身份、规则）
[system] 我们的缓冲注入
[user] 触发消息 ← Pipeline 自动添加，插件无法移除
```

**核心矛盾**：LLM 总是把最后一个 `user` 消息当作"当前任务"，天然倾向回复它。

## 尝试时间线

### 尝试 1：Pipeline random 规则（✅ 成功）

- 改 Pipeline `group-respond-rules.random` 从 `0` 到 `0.99`（`1.0` 被当作特殊值不生效）
- **结果**：`0.99` 生效，非 @ 消息成功触发 Pipeline
- **问题**：bot 回复总是引用触发消息（quote-origin），且内容针对最后一条

### 尝试 2：系统 prompt 条件规则（⚠️ 部分有效）

- 改规则 2 为：`@时：回复20-50字。随机插话时（历史开头有【随机插话模式】标记）：自由评论`
- **结果**：bot 开始识别随机模式概念，但声称"历史开头没有标记"

### 尝试 3：query_var 传递触发类型（❌ 失败）

- gate handler 用 `ctx.set_query_var('silent_trigger', 'random')` 传递
- inject handler 用 `ctx.get_query_var('silent_trigger')` 读取
- **根因**：`GroupMessageReceived` 和 `PromptPreProcessing` 在不同时间执行，query_var 不跨事件持久化

### 尝试 4：self._last_trigger 字典（⚠️ 键不匹配）

- gate 用 `f'{launcher_type}_{launcher_id}'` 存，inject 用 `session_name` 读
- **根因**：两个 key 格式可能不一致，导致 inject 取不到值，默认 fallback 到 'at'

### 尝试 5：伪装 user 消息（❌ 反效果）

- 在 `PromptPreProcessing` 中 `append` 一条 fake user 消息：
  `（系统通知：你是被随机选中插话的...）`
- **结果**：bot 把假消息当成用户说的，逐字回复"格式不对"、"条件未触发"
- **教训**：LLM 无法区分真实用户消息和系统注入

### 尝试 6：insert(0) → append（当前进行中）

- 将注入的 system 消息从 `insert(0)` 改为 `append`
- **理论**：`insert(0)` 把标记放在系统 prompt 前面，LLM 不认为它是"群聊历史"
- **预期**：`append` 让它紧跟系统 prompt 的"以下由【】包裹的是群聊最近记录"之后
- **待验证**

## 可能的根本问题

### 假设 A：注入位置不对

系统 prompt 说"以下由【】包裹的是群聊最近记录"，但注入的 system 消息在它**前面**（insert(0)），LLM 不关联。

→ 尝试 6 改为 append 可能解决。

### 假设 B：系统 prompt 条件逻辑自身卡死

规则写"被@时：回复。随机插话时：自由评论"——LLM 可能理解为"只有这两种情况才能说话"，而随机标记检测失败时，连 @ 回复也被抑制。

→ 尝试 2 的 prompt 改动可能导致 @ 和随机互相干扰。

### 假设 C：LangBot local-agent 的 prompt 构建方式特殊

local-agent 可能不是简单的 message list，而有自己的 prompt 组装逻辑。我们的 `ctx.event.prompt` 修改可能被后续阶段覆盖或重组。

### 假设 D：LLM 对 system role 消息的处理差异

DeepSeek-V4 可能不把 system 消息当作上下文，只认 user/assistant 消息。`append` 的 system 消息可能被忽略。

## 备用方案（未尝试）

### 方案 1：插件直调 LLM

绕过 Pipeline，用 `self.plugin.invoke_llm()` 直接调 LLM，完全自定义 prompt。

- 优点：完全控制上下文，无触发消息污染
- 缺点：丢失 KB 检索、LongTermMemory 工具、流式输出
- 复杂度：需手动补 KB 检索和 tool-use loop

### 方案 2：修改系统 prompt 本身

不注入额外消息，直接改 Pipeline 的系统 prompt，去掉条件触发逻辑。

- 优点：简单，LLM 不会困惑
- 缺点：无法区分 @ 和随机行为

### 方案 3：接受现状

当前效果其实不差——bot 以 10% 概率触发，回复风格一致（高冷吐槽），内容偶有自由评论。引用问题可后续解决。

## 仍待解决

1. **引用剔除**：`NormalMessageResponded` 的 `prevent_default()` 会破坏发送流程，`platform_message` 导入路径已找到但未验证
2. **随机标记检测**：LLM 能否识别 `【随机插话模式】` 取决于注入位置
3. **worktree 合并**：`fix-random-trigger-context` 分支有多轮尝试的 commit，需清理后合入 main

## 相关记忆

- [[langbot-plugin-best-practices]] — 16 个踩坑记录
- [[ssh-tailscale-synology-timeout]] — NAS SSH 超时
