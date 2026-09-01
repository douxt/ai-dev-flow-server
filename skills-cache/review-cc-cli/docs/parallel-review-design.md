# --parallel 并行评审设计文档

## 概述

在现有串行评审基础上，新增 `--parallel` 可选参数。启用后，多个独立 `claude -p` 子进程按维度并行评审，verifier 交叉检查去重合并，输出统一报告。

默认行为不变（串行），加 `--parallel` 才启用并行。

## 行业最佳实践吸收

### 1. 维度分离（Anthropic 内部 + CodeX-Verify）

每个 agent 只审一个维度，独立上下文避免锚定偏差：

| 维度 | Rubric | 阻断 | 关注点 |
|------|--------|------|--------|
| **correctness** | correctness.md | ✅ | 逻辑、边界、空值、类型、异步/异常、状态、并发 |
| **security** | security.md | ✅ | OWASP top 10、注入、认证、密钥泄露 |
| **performance** | performance.md | ⚠️ | N+1、内存泄漏、阻塞 I/O、算法复杂度 |
| **style** | default.md | ❌ | 可维护性、命名、SOLID、DRY、死代码 |

> 审查顺序不可颠倒：correctness（阻断）→ security（阻断）→ performance（警告）→ style（建议）。

> 参考：Anthropic 内部 Explorer×N 模式——每个 explorer 独立搜索，互不知晓对方发现。

### 2. Verifier 交叉检查（`/ultrareview` 模式）

并行 explorer 输出 → 一个独立 verifier agent 逐条交叉验证：
- 去重：file:line 相同 → 合并，保留 severity 高者
- 诈骗检测：verifier Read 源码验证 explorer 的发现是否真实
- 降噪：verifier 确认后才进入最终报告

> 核心洞察：**找 bugs 和确认 bugs 是不同任务，不能绑在一个 agent 里。**

### 3. 对抗评分（PAR 模式）

两个 agent 同维度竞争 → 分歧时取 worst severity。
review-cc-cli 暂不采用（成本翻倍，收益有限），留作未来 `--adversarial` 扩展。

### 4. 自适应路由（ai-review-agent 模式）

分析 diff 内容后只激活相关维度：
- 纯 CSS 改动 → 不激活 security agent
- 纯测试文件 → 不激活 performance agent
- 认证模块 → 安全 agent 权重最高

review-cc-cli 第一版不实现自适应路由（增加复杂度），默认全维度激活，用户可 `--parallel security,correctness` 手动选择。

## 参数设计

```
/review-cc-cli --parallel [维度列表] [其他参数]
```

| 用法 | 说明 |
|------|------|
| `/review-cc-cli --parallel` | 4 维度全部并行（security/correctness/performance/style） |
| `/review-cc-cli --parallel security,correctness` | 仅安全和正确性两维 |
| `/review-cc-cli --parallel --loop` | 并行 + 循环收敛（每轮并行） |
| `/review-cc-cli --parallel --scope "第一批"` | 分批评审 + 并行 |

## 执行流程

```
/review-cc-cli --parallel <范围>
        │
  ① 主进程分析范围，确定激活维度
        │
  ② 并行启动 N 个 claude -p（Bash 后台任务）
     ┌────────┬────────┬────────┬────────┐
     │ claude │ claude │ claude │ claude │
     │  -p    │  -p    │  -p    │  -p    │
     │correct │security│  perf  │ style  │
     │rubric  │rubric  │rubric  │rubric  │
     └───┬────┴───┬────┴───┬────┴───┬────┘
         │        │        │        │
  ③ 收集所有 agent 的 JSON 输出
         │
  ④ 主进程去重：Stage 1（file:line 精确碰撞）+ Stage 2（候选配对：同文件 + 行号差 ≤20 或 Jaccard > 0.3，阈值参考 CodeX-Verify 实践，后续可 A/B 调优）
         │
  ⑤ 启动 verifier agent（claude -p）
     - Stage 3：LLM 判重「同一问题不同表象」→ 合并+交叉引用
     - 逐条 Read 源码验证真实性（≤15 全验，>15 按 severity 截断）
     - 标记 confirmed / false_positive / uncertain
         │
  ⑥ 主进程输出合并报告：
     ✅ Confirmed（N 条）
     ⚠️ Uncertain（N 条）
     ❌ False Positive（N 条）
             ⏭️ Unverified（N 条，超出配额未经 verifier 确认）
     📊 各维度统计 + agent 覆盖度
```

## 与现有特性的兼容矩阵

| 特性 | 兼容 | 行为 |
|------|------|------|
| `--loop` | ✅ | 每轮并行，verifier 确认后写入 acceptedIssues |
| `--scope` | ✅ | scope 传给所有维度 agent |
| `--with` | ✅ | 参考文档传给所有维度 agent |
| `--rubric` | ⚠️ | 输出 warning「--rubric 与 --parallel 互斥，已降级为串行单 agent 评审」，然后正常执行。若需多 agent 独立用同一 rubric，不加 `--rubric` |
| `--quick` | ✅ | 跳过步骤⑥合并报告格式化，直接展示 verifier 原始 JSON + 各维度 agent 原始输出 |
| `--timeout` | ✅ | 每个 agent 独立超时控制 |
| `--model`/`--opus`/`--sonnet`/`--haiku` | ✅ | 所有并行 agent 共用同一模型 |
| `--shallow` | ✅ | 传给所有维度 agent |
| `--explore` | ✅ | 传给所有维度 agent |

## 失败处理

| 场景 | 处理 |
|------|------|
| 某维度 agent 超时（瞬态） | 阻断级（correctness/security）→ 保留成功维度 findings，仅重试失败维度；非阻断级 → 标注缺失 |
| 某维度 agent 被安全拦截（持久） | 阻断级/非阻断级均不重试（重试必然再被拦），记录到 errors，标注缺失 |
| 某维度 agent 输出无 JSON | 同超时，降级为原始文本标注 |
| 全部 agent 失败 | 降级为串行模式重试一次 |
| verifier 失败 | 跳过验证步骤，原始结果标注「未经 verifier 确认」 |
| 全部轮次某阻断维持续失败 | 记录到 errors，最终汇总输出缺失警示 |

## 成本估算

| 模式 | Token 倍数 | 典型耗时 |
|------|-----------|---------|
| 串行（当前） | 1× | 30-90s |
| --parallel 4 维 | 3-4× | 20-60s（并行瓶颈 = 最慢维度） |
| --parallel 2 维 | 1.5-2× | 15-45s |
| --parallel --loop ×3 轮 | 9-12× | 60-180s |
| verifier（独立） | +0.2-0.4× | +5-15s（≤15 条） |

> 并行无 session 复用：串行通过 `--resume` 复用 prompt cache 降本，并行各 agent 均为冷启动全价。实际成本差距可能大于上表倍数。

## 实施步骤

### Phase 1: 核心并行（含 verifier 全验 + 三级去重 + 阻断级重试）

Grill 后将原 Phase 2/3 硬需求合并至此。

1. SKILL.md 用法表加 `--parallel [维度列表]`
2. 主流程加并行分支（并行启动、三级去重管道、verifier、合并报告）
3. 并行启动用 Bash 工具（`run_in_background: true`）执行 `claude -p` 命令，TaskOutput 收集结果
4. verifier 逐条验证所有 findings（≤15 全验，>15 按 severity 截断）
5. 三级去重管道（精确碰撞 → 候选配对 → LLM 判重）
6. 阻断级维度失败 → 本轮不计入有效轮次，保留其他成功维度 findings，仅重试失败维度；非阻断级 → 标注缺失

### Phase 2: 自适应路由

分析 diff 内容后只激活相关维度（如纯 CSS 不激活 security agent，纯测试不激活 performance agent）。

### Phase 3: 对抗与持久化

1. 同维度对抗（`--parallel security --adversarial`）
2. 持久化 agent team（Agent Teams API 成熟后接入）
3. 验证策略待阶段启动时制定

## 验证策略

### 每步验证门禁

| 步骤 | 验证手段 |
|------|---------|
| 用法表 + 参数解析 | 跑 `/review-cc-cli --parallel --help`，确认参数提示/类型校验正常 |
| 并行启动 | 手动跑 `--parallel` 对比 `--parallel` 关闭时的输出，确认二者不冲突 |
| 三级去重 | 构造碰撞 case：同一 file:line + 同文件差 5-10 行相似 desc → 验证是否正确合并 |
| verifier 全验 | 构造 3 条已知 false positive + 2 条 real bug → verifier 应标记 3 FP + 2 confirmed |
| 阻断级重试 | 模拟某 agent 退出码 1 → 确认不计轮次，重试触发 |

### 回归测试

- 现有串行路径不受影响：`/review-cc-cli`（无 `--parallel`）行为与改前完全一致
- 用 5 条已知 bug 的 fixture 文件，跑串行 ++ `--parallel` 分别评审，确认并行不遗漏串行能发现的问题

### 验收标准

- verifier FP 率 < 10%（误杀 ≤ 1 条/10 条）
- 并行 4 维 vs 串行：发现数 ≥ 串行，且新发现的 issue 被人工判定为真实
- 去重后无语义重复项（同根因不同位置 → 交叉引用，非漏报）

## 不做的

- 多模型混合（Claude + GPT + Gemini）：增加外部依赖，review-cc-cli 定位是 Claude Code 生态工具
- 自动修复（`--fix`）：保持评审只读定位
- 持久化 agent team（Agent Teams API）：当前 API 稳定性不足，等成熟后再接入

## 风险

| 风险 | 缓解 |
|------|------|
| token 成本暴增 | 默认关闭，用户主动选择，文档明确标注成本 |
| 多 agent 对同一问题重复报告 | verifier 去重 |
| verifier 自身误判 | 不确定项标 uncertain 而非直接驳回 |
| 并发 Bash 任务资源竞争 | 最多 4 个并行 agent，不超过主机承载力 |
| API 并发限流 | 4 个 agent 不超过常规并发上限；claude -p 内置重试+退避机制 |
| 主进程去重 scalability | finding 总数 >60 条时，先按 severity 截断（保留 high+medium），再进入 Stage 2 |

## Grill 确认结论（2026-06-27）

以下经多轮访谈确认，已纳入 Phase 1（原 Phase 2/3 项合并，不延期）：

### Verifier 行为
- **每条 finding 都验证**，非仅冲突项。依据：Anthropic ultrareview <1% 误报率
- **先排序再验证**：≤15 条全验，>15 条按 severity 截断。依据：109-agent 事后分析节省 79% agent
- **verifier 不生成新发现**：分离关注点（finder=敏感度，verifier=特异度）。遗漏标注「⚠️ Verifier 提示」
- **verifier 分批验证**：同文件 findings 一次 Read 验证全部，减少重复 I/O

### 去重策略（三级管道）
- Stage 1：file:line 精确碰撞 → 直接合并，severity 取高
- Stage 2：同文件 + (行号差 ≤20 或 Jaccard(title) > 0.3) → 候选对
- Stage 3：候选对送入 verifier 判「同一问题不同表象」→ 合并 + 交叉引用

### 并行 + Loop 组合
- 收敛判断：全局维度合计（方案 A），非逐维独立
- 阻断级维度超时 → 保留成功维度 findings（已写入 acceptedIssues），仅重试失败维度
- 阻断级被安全拦截 → 不重试，标注缺失
- 非阻断维度（style）失败 → 标注缺失，照常收敛

### 实施阶段调整
- Phase 1 合并：核心并行 + verifier 全验 + 三级去重 + 阻断级重试（原方案分散在三个 phase）
- Phase 2 仅留：自适应路由（分析 diff 选维度）
- Phase 3 仅留：同维度对抗 + 持久化 agent team（等 API 成熟）
