# 测试质量路线图 v1.0

> 2026-07-30 | 基于 UMES3 E2E 测试可信度调研
> 调研报告：UMES3 `docs/references/frontend-testing-best-practices-research.md`

## 背景

UMES3 喷涂/穿条单功能开发中，C0-C6 全部门禁通过、46/46 GREEN，但人工验证"发起喷涂"第一下就报"参数缺失"。根因：75% 的测试 Action 绕过 UI（用 `apiCall()` 直接调 API），`handlePaintCreate` 内部的参数拼装、URL 构造从未被执行。

调研确认了 5 大领域，当前流程只覆盖其中表层。本路线图分三期推进。

## P0: E2E 可信度门禁（本次）

**解决**：测试写对了没有——Action 必须走 UI。

| 改动 | 文件 |
|------|------|
| C7 E2E 可信度（4 项检查） | `gate-checklists/test-checklist.md` |
| T8 E2E 测试完整性 | `gate-checklists/test-checklist.md` |
| Action-via-UI 原则 + Testing Trophy 引用 | `knowledge/09-测试质量宪法.md` |
| G11 Action 绕过检测 | `knowledge/stacks/playwright/test-quality.md` |

C7 为 advisory 警告级——`apiCall` 在 Setup/Teardown 中是合法的，需人工区分。

## P1: 遗留代码特征测试

**解决**：改旧代码前的安全网——当前 `/tdd` 只覆盖新功能。

### 问题

- UMES3 ChainSellDetail.js 9044 行，PHP 5.4 后端
- 当前流程：`/tdd` → RED → GREEN，假设"新功能从零开始"
- 遗留项目 80% 的改动是修改已有行为，不是新功能
- 没有测试的代码 = 改了就不知道是修复还是破坏

### 方案要点

1. 新增 skill 或 checklist：`characterization-test` — 改旧代码前的特征测试步骤
2. Feathers 4 步法：找改动点 → 写特征测试锁行为 → 最小改动 → 重构
3. Seam 识别指南：`store_api.php?action=` / `page.route()` / 组件 props
4. 门禁集成：`/to-tickets` 后检测 ticket 是否涉及遗留代码 → 触发特征测试步骤

### 关键设计问题

- 特征测试放在哪？（跟随 ticket 还是独立的 characterization 目录？）
- 如何判断"这是遗留代码改动"？（ticket 含 `[legacy]` 标记？自动检测测试覆盖率为 0 的文件？）
- 特征测试的执行时机（TDD RED 之前还是并行？）

## P2: 测试分层指导

**解决**：不该全写成 E2E——引导 AI 选择正确的测试层级。

### 问题

- UMES3 100% E2E（46 条），0 集成，0 单元
- E2E 慢（46 条 ~10min）、脆（数据依赖）、边界覆盖差
- Testing Trophy：E2E 10% + 集成 50-70% + 单元 20-30%

### 方案要点

1. 新增 knowledge：`knowledge/10-测试分层策略.md`（Testing Trophy + 层级选择决策树）
2. `/to-spec` 的 Testing Decisions 段增加层级选择指导
3. `test-plan-template.md` 增加层级分配表（E2E/集成/单元 分配比例）
4. 分层决策树：
   ```
   需要浏览器才能验证？ → E2E
   多个组件/模块交互？ → 集成（mock 网络层）
   纯计算/状态迁移？ → 单元
   ```

### 关键设计问题

- 集成测试技术栈推荐（Vitest + MSW？项目自选？）
- 如何不增加项目依赖负担？（UMES3 没有 Node 测试框架）
- 遗留项目（如 PHP 后端）的集成测试怎么做？

## P3: 长期（调研中，暂不进入开发）

- CI/CD 分层门禁：pre-commit → C0 + unit，PR → integration，merge → E2E
- Locator 质量规则（role > text > testid > css）
- 测试数据工厂标准化
- 测试执行时间监控与预算

## 参考资料

- Kent C. Dodds, "The Testing Trophy": https://kentcdodds.com/blog/static-vs-unit-vs-integration-vs-e2e-tests
- Michael Feathers, "Working Effectively with Legacy Code" (2004, 2024 updated)
- Steve Kinney, "API and UI Hybrid Tests": https://stevekinney.com/courses/self-testing-ai-agents/api-and-ui-hybrid-tests
- Playwright Best Practices: https://playwright.dev/docs/best-practices
- NoriSte, "UI Testing Best Practices" (2025): https://github.com/NoriSte/ui-testing-best-practices
