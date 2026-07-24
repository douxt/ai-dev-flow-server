# tickets 阶段出口检查清单

> 触发：/to-tickets 完成后
> 对应 v3.2 tickets 阶段 → tdd 阶段转换
> 对照宪法：Ticket 质量宪法（15 项 + 安全红线）

## 检查项

| # | 检查项 | 方式 |
|:-:|--------|:--:|
| T1 | 宪法 15 项对照审查（L1 语法 + L2 语义） | AI 自动 |
| T2 | 每 ticket ≤ 窗口 40%（~48K token） | AI 估算 |
| T3 | 所有 AC 标注验证级别（[auto]/[human-verify]/[decision]） | 正则 |
| T4 | blocked_by 无循环依赖 | 拓扑检查 |
| T5 | 安全红线标记已处理（auth/payment/crypto/delete/permission → safety frontmatter） | 正则 |
| T6 | issues/ 目录下所有 .md 可解析 | AI 验证 |

## 自动审查

> /to-tickets 产出 issues/ 后，AI 自动对照宪法逐 ticket 检查并输出报告。
> 人工只需看结论确认，无需手动逐项对比。

### L1 语法层（可正则/脚本化）

| 检查 | 方法 | 宪法 |
|------|------|:--:|
| frontmatter 完整 | 检查 estimate/type/test_files/blocked_by/needs_* 字段 | #1 |
| AC 标注格式 | `[auto]` / `[human-verify]` / `[decision]` 三选一 | #3 |
| estimate ≤1d | 值必须为 `0.5d` 或 `1d` | #1 |
| test_files 非空 | AFK ticket 必须声明 test_files | #14 |
| blocked_by 引用存在 | 引用的 ticket 文件存在于 issues/ | #9 |

### L2 语义层（需 LLM 对照）

| 检查 | 方法 | 宪法 |
|------|------|:--:|
| 函数签名完整 | 逐 ticket 对比接口定义与实际调用 | #5 |
| 前置准备具体 | 含具体 ID/值/参数，非占位符 | #5 |
| AC 覆盖集成层 | 跨模块 AC 不遗漏中间表/接口 | #11 |
| DAG 接口对齐 | 上游产出字段 = 下游消费字段 | #9 |

### 审查报告格式

```
📋 Ticket 宪法审查报告

L1 语法层:
  [T1] frontmatter: ticket-01 ✅ | ticket-02 ✅ | ticket-03 ⚠️ 缺 needs_docker
  [T2] AC 标注: 全部 ✅
  [T3] estimate: 全部 ≤1d ✅
  [T4] test_files: ticket-01 ⚠️ AFK 但 test_files 为空
  [T5] blocked_by: 全部引用有效 ✅

L2 语义层:
  [T6] 接口签名: ticket-02 ⚠️ 缺 &$map 参数
  [T7] 前置准备: ticket-03 ⚠️ "至少含 1 型材" → 需具体 ID

结论: 8/12 项通过，4 项需修正 → 修正后重新审查
```

### 异常处理

- L1 不过 → 修正 ticket frontmatter 后重新审查
- L2 不过 → 回 `/to-tickets` 补充，或标 `[decision]` 人工裁决
- 安全红线未标记 → 禁止进入 /tdd

## 通过条件

T1 + T2 必须通过。T3-T5 为 advisory 警告。

## 产物

- `issues/` 目录（每个 ticket ≤ 48K token，带 safety 标记）
- AI 宪法审查报告（全部通过）
