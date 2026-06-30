# 并行评审验收 fixture

`fixture-bugs.js` 是一个植入已知问题的测试文件，用于验证 `--parallel` 管道正确性。

## 植入问题清单

### 真实 bug（预期 verifier confirmed）

| # | 维度 | 行号 | 严重度 | 描述 |
|---|------|------|--------|------|
| 1 | correctness | 18 | high | `userId` 未做 null 检查直接拼入 SQL |
| 2 | correctness | 30 | high | `for` 循环 off-by-one：`<=` 应为 `<` |
| 3 | correctness | 40 | medium | `== 0` 类型强制，应用 `===` |
| 4 | security | 37 | high | API 密钥硬编码 `sk-abc123xyz456` |
| 5 | security | 18 | high | SQL 注入 — 字符串拼接 `+ userId` |
| 6 | performance | 27 | medium | N+1 查询 — 循环内逐条查 `order_items` |
| 7 | style | 43 | low | 魔法数字 `3`，应命名常量 |
| 8 | performance | 48 | medium | `setInterval` 创建后无 `clearInterval` |
| 9 | style | 55 | low | `legacyNormalize` 函数未被调用（死代码） |
| 10 | correctness | 72 | high | `reportId` 未做 null 检查（与 #1 同根因） |

### 语义重复

- **BUG #1**（行 18）与 **BUG #10**（行 72）：同一 null-check 遗漏模式，不同位置
  - Stage 1 不碰撞（不同行号）
  - Stage 2 应形成候选对（同文件 + desc Jaccard > 0.3）
  - Stage 3 verifier 应判定为同一根因 → 交叉引用标注

### False positive（预期 verifier marked false_positive）

| # | 行号 | 内容 | 排除理由 |
|---|------|------|---------|
| F1 | 22 | `user == null` | `== null` 是 JS 惯用法，同时检查 null/undefined |
| F2 | 62 | 注释掉的 `oldDiscount` | 有明确 KEEP-FOR-REFERENCE 标记，非死代码 |
| F3 | 65 | `const sq = x => x * x` | 短箭头函数中单字母变量可接受 |

## 验收标准

### 三级去重

1. **Stage 1**（精确碰撞）：无预期碰撞（所有 bug 不同行号）
2. **Stage 2**（候选配对）：BUG #1 和 #10 应形成候选对（同文件 + 相似 desc）
3. **Stage 3**（LLM 判重）：verifier 应合并或交叉引用 #1 和 #10

### Verifier

- 10 条确认 → ≤ 15 全验
- F1-F3 标记 false_positive，各附排除理由
- BUG #1-#10 标记 confirmed（≥ 8 条）
- 无新增发现（verifier 不生成新 finding）

### 维度覆盖

| 维度 | 预期发现 |
|------|---------|
| correctness | #1, #2, #3, #10 |
| security | #4, #5 |
| performance | #6, #8 |
| style | #7, #9 |

## 回归测试

串行 `/review-cc-cli` 与 `--parallel` 对同一 fixture 的 confirmed 数量应一致（≥ 8 条）。
