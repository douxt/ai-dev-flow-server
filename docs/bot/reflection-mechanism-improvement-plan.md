# 反思机制功效提升计划

> 2026-07-31 | 基于网络调研最佳实践（ERL / Reflexion / Claude Code / EvoLLM）
> 配套：[evolution-roadmap.md](evolution-roadmap.md) / [reflection-layer-research-20260729.md](reflection-layer-research-20260729.md)

---

## 问题诊断

当前反思系统代码跑通，但**实际功效近乎为零**：
- 唯一 1 条反思来自自动化测试（`/sync`），非真实用户
- 真实纠正（如小通豆"时间又弄错了"）未能捕获
- 根因：捕获率低（关键词窄 + 窗口短 + rate limit 激进）+ 无可观测性

## 核心洞察（来自研究）

1. **ERL 论文**：Heuristics（When-Then 规则）> raw trajectories（原始对话），反思应生成可执行规则
2. **Claude Code**：regex 抓 80% 信号，零延迟；每 5 轮 side-channel 自我反思
3. **Amazon**：纠正检测需先做话语重写（ellipsis/anaphora → 补全）
4. **EvoLLM**：反思需要生命周期管理——聚类、合并、动态质量分、修剪弱原则
5. **ERL 关键数据**：LLM-based retrieval > embedding retrieval；k=20 优于 k=3

---

## 进度总览

| 阶段 | 状态 | 开始 | 完成 |
|------|:----:|------|------|
| P0 — 参数调优 + 可观测性 | ✅ 完成 | 07-31 | 07-31 |
| P1 — 结构增强 + 自我反思 | ⏳ 待开始 | — | — |
| P2 — 长期演进 + 评估框架 | ⏳ 待开始 | — | — |

---

## P0：参数调优 + 可观测性 ✅

**目标**：不改架构，立刻提升捕获率，让漏报可见。

| # | 改动 | 状态 |
|---|------|:----:|
| P0.1 | 扩展关键词：17→31 个 + 3 类（事实反驳/补充纠正/质疑）+ rebuttal regex | ✅ |
| P0.2 | sender 冷却：10min → 3min | ✅ |
| P0.3 | 纠正窗口上限：120s → 300s | ✅ |
| P0.4 | 全路径诊断日志（6 个埋点） | ✅ |

**验证方式**：部署后观察日志 `diag:` 和 `stage1 miss:` 出现频率。
**分支**：[`ref-p0-improvements`](https://github.com/douxt/ai-dev-flow-server/pull/new/ref-p0-improvements)

---

## P1：结构增强 + 自我反思源

**目标**：引入 ERL 式的自我反思，话语重写，提升检索质量。

### P1.1 话语重写层

**问题**：省略句"不对，你搞错了"缺上下文，LLM 确认阶段难以判断。
**方案**：`_stage2_confirm` 前加一个轻量重写步骤：

```
用户: "不对，你搞错了"
  → LLM 补全: "不对，[bot 之前说的三相电电压] 搞错了"
  → 补全后的完整句子送 stage2 确认
```

**改动文件**：`service/correction.py` — 新增 `_rewrite_utterance()` 方法
**依据**：Amazon 论文 — utterance rewriting 消除 ellipsis 导致的大部分漏报
**预计代码量**：~40 行

### P1.2 自我反思源

**问题**：仅靠用户主动纠正，信号稀疏。Claude Code 每 5 轮 side-channel 自我反思。
**方案**：每隔 N 轮群聊（N=10），后台异步触发一次自我反思扫描：

```
自我反思 Prompt:
"以下是最近 10 轮对话。请你审视自己的回答，找出可能的错误或不够好的地方。
如果有，生成一条反思（When-Then 格式）；如果没有，回答 NONE。"

最近对话:
{recent_messages}

你是否犯了错误？（如果有，请生成反思 JSON；如果无，回复 NONE）
```

**改动文件**：
- `service/reflection.py` — 新增 `SelfReflectionScanner` 类
- `components/event_listener/default.py` — gate 中加计数器，每 10 轮触发
**预计代码量**：~80 行

### P1.3 检索增强：k=3→10 + LLM Rerank

**问题**：k=3 太小，纯 embedding 检索不如 LLM 检索。
**方案**：
1. `search_similar` 返回 top_k=10
2. 新增 `_llm_rerank()`：输入 10 条候选 + 当前对话，让 LLM 选出最相关的 5 条
**依据**：ERL 论文 — LLM-based retrieval > embedding；k=20 效果最佳
**改动文件**：
- `store/reflection_store.py` — `search_similar` top_k 可配置
- `service/reflection.py` — 新增 `rerank()` 方法
**预计代码量**：~50 行

### P1.4 When-Then 格式增强

**问题**：反思 JSON 缺可执行规则字段。
**方案**：生成 prompt 中要求 LLM 输出 `when` + `then` 字段：

```json
{
  "scenario": "...",
  "when": "用户在问电气相关技术问题时",
  "then": "先确认电压等级和用电场景（工业380V/民用220V），再给方案",
  "mistake": "...",
  "correct_approach": "..."
}
```

**改动文件**：`service/reflection.py` — `GENERATE_PROMPT` 模板更新
**预计代码量**：~15 行

### P1 验证方式

- 日志中出现 `diag: skip no_signal` 频率应下降
- 7 天内新增反思 ≥ 3 条（来自真实用户）
- `stage1 miss` 日志中不再出现明显纠正（如"明明是""其实是"）

---

## P2：长期演进 + 评估框架

### P2.1 反思生命周期管理

**问题**：反思只增不减，低质量反思污染检索。
**方案**（参考 EvoLLM）：

| 操作 | 触发条件 | 动作 |
|------|---------|------|
| **合并** | 两条反思 cosine > 0.85 | 保留 confirm_count 高的，合并 entities |
| **升级** | confirm_count ≥ 3 来自 ≥ 2 个不同用户 | importance: low → medium |
| **降权** | 30 天未被检索命中 | importance 降一级，或标记 dormant |
| **归档** | 90 天未被命中 | archived=True，不参与检索 |

**改动文件**：`store/reflection_store.py` — 新增 `_lifecycle_scan()` 方法
**现有基础**：decay loop 已存在（`_reflection_decay_loop`），需增强

### P2.2 A/B 评估框架

**问题**：无法量化反思注入是否改善了回复质量。
**方案**：
1. 固定 20 组历史对话作为 eval set
2. 每组对话：分别用"有反思注入"和"无反思注入"跑一次
3. LLM-as-Judge 评分（准确性/有用性/连贯性）
4. 记录 win/lose/tie

**改动文件**：新建 `tests/eval_reflection.py`
**依据**：DeepEval 多轮评估 + Prometheus-style LLM judge
**预计代码量**：~150 行

### P2.3 纠正检测分类器

**问题**：regex+LLM 两阶段仍有漏报，且 LLM 确认有延迟和成本。
**方案**：积累 100+ 标注样本后，训练轻量 RoBERTa 分类器替代 stage1 关键词+stage2 LLM：
- 输入：用户消息 + bot 上条回复（截断 512 tokens）
- 输出：是纠正/不是纠正（二分类）+ 错误类型

**依赖**：需积累标注数据（可从诊断日志中抽样标注）
**改动文件**：
- 新增 `service/correction_classifier.py`（模型推理）
- `service/correction.py` — 可插拔检测器接口

### P2 验证方式

- eval set 上"有反思注入"的胜率 > 55%
- 90 天后活跃反思 ≥ 15 条（不再只有 1 条）
- 用户满意度（通过"谢谢"等正反馈词统计）趋势上升

---

## 成功指标

| 指标 | 现状 | P0 目标 | P1 目标 | P2 目标 |
|------|:--:|:--:|:--:|:--:|
| 反思总数 | 1 | ≥2 | ≥5 | ≥15 |
| 真实用户反思占比 | 0% | ≥50% | ≥80% | ≥90% |
| 纠正捕获率（估算） | ~5% | ~20% | ~50% | ~70% |
| 反思注入命中率（每次检索有结果） | 100%（1条） | ≥30% | ≥50% | ≥60% |
| LLM-as-Judge 胜率 | — | — | — | >55% |

---

## 不做

- ❌ fine-tune 底层模型（成本/复杂度远超收益）
- ❌ 引入独立 agent 框架（LangGraph/Letta）——保持轻量
- ❌ RL 训练管道（需训练基础设施）
- ❌ 实时在线学习（风险高于异步批处理）
