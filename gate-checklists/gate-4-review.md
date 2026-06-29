# Gate 4: Issue 评审（/review-cc-cli）

## ⚠️ 安全规则（不可跳过）

1. 每完成一个步骤，输出结果给用户，**等待用户确认后才能继续下一步**
2. 禁止自动执行多个步骤，禁止跳过用户确认环节
3. 这不是 CC Workflow 脚本——不做后台子代理，全程与用户交互
4. 遇到不确定的判断，询问用户，不自行决策
5. 全程与用户交互，不 spawn 子代理

## 步骤 0：确认当前 Gate 进度

Read `.gate-state`，确认 gate-4 当前状态：
- 如果 `status: passed` → 跳过，告知用户
- 如果 `status: in_progress` 且有中断记录 → 从断点继续
- 确认 gate-3 必须为 `passed`，否则告知用户"请先完成 Gate 3"
- 如果 `status: pending` → 继续步骤 1

## 步骤 1：读 Issue 宪法 + Issue 文件

1. Read `04-Issue质量宪法.md`，回顾 14 项宪法规则
2. Read `issues/` 下所有待评审的 issue 文件
3. 向用户确认评审范围和标准

**等待用户确认后继续。**

## 步骤 2：逐条评审 Issue

对每条 issue 按 14 项宪法逐条检查：

| # | 检查项 | 状态 |
|:-:|--------|:----:|
| 1 | 工时 ≤1d | |
| 2 | type 正确 | |
| 3 | AC 可测量 | |
| 4 | 目录已指定 | |
| 5 | 前置准备完整 | |
| 6 | mock/E2E 已声明 | |
| 7 | SDK 可参考 | |
| 8 | 验收不含主观 | |
| 9 | blocked_by 清晰 | |
| 10 | 架构约束已引用 | |
| 11 | AC 覆盖集成层 | |
| 12 | Scope 边界已声明 | |
| 13 | needs_* 已声明 | |
| 14 | test_files 已指定 | |

> 参照 `04-Issue质量宪法.md` 获取每项的详细检查方法。

**全部 issue 审完，向用户汇报结果，等待确认。**

## 步骤 3：可选 — AI 辅助审查

如需增强审查，可调用 `/review-cc-cli` 对 issue 文件进行独立评审：
```
/review-cc-cli --rubric default issues/
```

**通过**：更新 `.gate-state` gate-4 status → `passed`（通过则自动写 passed，不通过则设 blocked）。
**不通过**：按评审意见修正 issue → 重新 Gate 3 或 Gate 4。
