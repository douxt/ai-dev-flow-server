# 测试质量路线图 v1.0

> 2026-07-30 | 基于 UMES3 E2E 测试可信度调研
> 调研报告：UMES3 `docs/references/frontend-testing-best-practices-research.md`

## 背景

UMES3 喷涂/穿条单功能开发中，C0-C6 全部门禁通过、46/46 GREEN，但人工验证"发起喷涂"第一下就报"参数缺失"。根因：75% 的测试 Action 绕过 UI（用 `apiCall()` 直接调 API），`handlePaintCreate` 内部的参数拼装、URL 构造从未被执行。

调研确认了 5 大领域，当前流程只覆盖其中表层。本路线图分三期推进。

## P0: E2E 可信度门禁 ✅ 已完成（2026-07-30）

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

### 设计决策（已确定）

> 详细调研：[docs/references/characterization-tests-research.md](../references/characterization-tests-research.md)

| # | 问题 | 决策 | 理由 |
|:--|------|------|------|
| 1 | 触发机制 | 显式命令 `/characterize` + ticket `[legacy]` 自动提示 | Feathers 流程是显式步骤，不能全自动；AI 检测到零覆盖率文件时主动提示 |
| 2 | 文件放置 | 独立 `tests/characterization/` | 生命周期与 TDD 测试不同（短期、可删），混在一起无法区分 |
| 3 | TDD 集成 | 四阶段串行：`/characterize → 预重构 → /tdd → 后重构` | 特征测试 GREEN 锁现状，TDD RED→GREEN 做改动，两者共存不互斥 |
| 4 | 技术栈差异 | 通用文档 + 各栈模块 | PHP 用 HTTP 探针快照，Node 用组件快照，DB 用状态对比 |

### 核心规则

- **特征测试必须立即 GREEN**——如果失败，是你理解错了代码行为，修测试不修代码
- **不改行为**——特征测试捕获现状，包括 bug。锁住之后再改
- **可删除**——改完后特征测试可升级为回归测试或删除

### 实施清单

| # | 产出 | 文件 | 估计 |
|:--|------|------|:--:|
| 1 | 通用知识 | `knowledge/11-遗留代码特征测试.md`（四阶段模型） | 1h |
| 2 | 门禁清单 | `gate-checklists/characterization-checklist.md` | 30min |
| 3 | 流程集成 | stage-tracker 增加 `/characterize` 阶段检测 | 30min |
| 4 | PHP 栈模块 | `knowledge/stacks/php/legacy-characterization.md` | 1h |
| 5 | UMES3 验证 | 在真实遗留 API 上跑通特征测试 | 1h |
| **合计** | | | **~4h** |

## P2: 测试分层指导

**解决**：不该全写成 E2E——引导 AI 选择正确的测试层级。

### 问题

- UMES3 100% E2E（46 条），0 集成，0 单元 ← Ice Cream Cone 反模式
- E2E 慢（46 条 ~10min）、脆（数据依赖）、边界覆盖差
- Testing Trophy：E2E 5-10% + 集成 50-70% + 单元 20-30%

### 设计决策（已确定）

> 详细调研：[docs/references/testing-layering-research.md](../references/testing-layering-research.md)

| # | 问题 | 决策 | 理由 |
|:--|------|------|------|
| 1 | 集成测试技术栈 | **uvu**（Node 10+ 兼容）+ 裸 PHP assert() | MSW 不兼容 Node 14；先写测试用手头工具，不先装框架 |
| 2 | 遗留项目兼容 | Strangler Fig：新功能用新方式，旧代码只加特征测试 | 不动已有测试方式，增量演进 |
| 3 | E2E 比例控制 | 软指导：spec 阶段决策树 + 默认禁 E2E（选 E2E 需写理由） | 不硬阻断，用决策树引导 AI 选正确层级。CI 脚本 warning（>30%）后期加 |

### 决策树（嵌入 prompt 前端）

```
开始
  ├─ 需要浏览器/真实 UI？→ 是 → 关键业务路径？→ E2E（≤10%）
  │                         └ 否 → 能拆成独立交互？→ 集成
  ├─ 涉及多模块/服务交互？→ 是 → 集成测试
  └─ 纯逻辑/计算/状态迁移？→ 是 → 单元测试

防冗余检查：已被更低层覆盖？→ 降级。能用集成替代 E2E？→ 降级。
```

### 实施清单

| # | 产出 | 文件 | 
|:--|------|------|
| 1 | 通用知识 + 决策树 | `knowledge/10-测试分层策略.md` |
| 2 | 层级分配表 | `test-plan-template.md` §1 增强 |
| 3 | spec 阶段分层检查 | `spec-checklist.md` S13 新增 |
| 4 | 宪法更新 | `knowledge/09-测试质量宪法.md` §三 |
| 5 | Node 栈模块 | `knowledge/stacks/node/integration-testing.md`（uvu + nock） |
| 6 | PHP 栈模块 | `knowledge/stacks/php/integration-testing.md`（裸 assert + simpleunit） |

## P3: 长期（调研中，暂不进入开发）

- CI/CD 分层门禁：pre-commit → C0 + unit，PR → integration，merge → E2E
- Locator 质量规则（role > text > testid > css）
- 测试数据工厂标准化
- 测试执行时间监控与预算
- **P1 硬阻断**：PreToolUse hook 拦截 `/tdd`——检测 `[legacy]` ticket 未完成 `/characterize` 时阻止执行（当前为文档提醒，试点后再加）

## 参考资料

- Kent C. Dodds, "The Testing Trophy": https://kentcdodds.com/blog/static-vs-unit-vs-integration-vs-e2e-tests
- Michael Feathers, "Working Effectively with Legacy Code" (2004, 2024 updated)
- Steve Kinney, "API and UI Hybrid Tests": https://stevekinney.com/courses/self-testing-ai-agents/api-and-ui-hybrid-tests
- Playwright Best Practices: https://playwright.dev/docs/best-practices
- NoriSte, "UI Testing Best Practices" (2025): https://github.com/NoriSte/ui-testing-best-practices
