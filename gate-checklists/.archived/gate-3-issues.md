# Gate 3: 拆解 Issue（/to-issues）

## ⚠️ 安全规则（不可跳过）

1. 每完成一个步骤，输出结果给用户，**等待用户确认后才能继续下一步**
2. 禁止自动执行多个步骤，禁止跳过用户确认环节
3. 这不是 CC Workflow 脚本——不做后台子代理，全程与用户交互
4. 遇到不确定的判断，询问用户，不自行决策
5. 全程与用户交互，不 spawn 子代理

## 步骤 0：确认当前 Gate 进度

Read `.gate-state`，确认 gate-3 当前状态：
- 如果 `status: passed` → 跳过，告知用户
- 如果 `status: in_progress` 且有中断记录 → 从断点继续
- 确认 gate-2 必须为 `passed`，否则告知用户"请先完成 Gate 2"
- 如果 `status: pending` → 继续步骤 1

## 步骤 1：读 Issue 质量宪法 + PRD

1. Read `04-Issue质量宪法.md`（如项目中不存在，Read `ai-dev-flow/04-Issue质量宪法.md`），理解 14 项宪法规则
2. Read `docs/requirements/` 下最新的 PRD 文件，理解需求范围和验收条件
3. 向用户概述关键宪法规则，确认理解一致

**等待用户确认后继续。**

## 步骤 2：拆解 Issue — 调用 /to-issues

调用 `/to-issues` 技能将 PRD 拆成垂直切片 issue：
1. 垂直切片：每条是完整端到端路径，非水平层
2. 单 issue 工时 ≤1d
3. 类型标记：`type: AFK`（纯自动）/ `type: HITL`（含人工）
4. 依赖链清晰：`blocked_by` 字段
5. 每条 issue 含质量自检 checklist
6. 附带 Issue 质量宪法作为上下文

**等待 issue 拆解完成，用户审阅后继续。**

## 步骤 3：出口检查

逐条检查 Gate 3 出口标准（17 项）：

| # | 检查项 | 方法 |
|:-:|--------|------|
| 3.1 | 每条 estimate ≤1d | grep estimate: |
| 3.2 | type 正确 | AFK/HITL 分类正确 |
| 3.3 | AC 全可量化 | 无模糊词 |
| 3.4 | 代码目录已指定 | AC 或正文写清路径 |
| 3.5 | 前置准备完整 | 外部服务/token/文件已列 |
| 3.6 | mock/E2E 策略明确 | AC 写清测试方式 |
| 3.7 | SDK 用法可参考 | 依赖表格已记录 |
| 3.8 | 验收无主观 | 可自动化或可观测 |
| 3.9 | blocked_by 无循环 | 依赖链检查 |
| 3.10 | 架构约束已引用 | 不可变规则已引用 |
| 3.11 | AC 覆盖集成层 | 不只模块，含编配 |
| 3.12 | Scope 边界清晰 | In/Out 清单 |
| 3.13 | needs_* 已声明 | needs_llm/vision/pdf/docker |
| 3.14 | test_files 已指定 | 精确路径 |
| 3.15 | 总工时与 PRD 一致 | sum(estimate) ±20% |
| 3.16 | 切片方向标注 | 垂直/水平 |

**全部通过后**：告知用户，更新 `.gate-state` gate-3 status → `passed`。
**不通过**：输出缺失项清单，用户修正后重新检查。
