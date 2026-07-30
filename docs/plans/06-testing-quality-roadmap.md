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

## P2: 测试分层指导 ✅ 已完成（2026-07-30）

**解决**：不该全写成 E2E——引导 AI 选择正确的测试层级。

### 实施决策（v3 终版）

> 详细调研：[docs/references/testing-layering-research.md](../references/testing-layering-research.md)
> 实施方案：[~/.claude/plans/d-github-personal-kb-ai-coding-workflow-hazy-lovelace.md](../../.claude/plans/d-github-personal-kb-ai-coding-workflow-hazy-lovelace.md)

| # | 问题 | v3 终版决策 | 为何推翻 v2 |
|:--|------|------|------|
| 1 | 决策树第一节点 | **"测 UI 交互还是数据逻辑？"** | v2 "需要浏览器？"所有前端功能都答"是"，形同虚设 |
| 2 | E2E 触发条件 | **跨系统流程（支付/外部API/OAuth）** | v2 "关键业务路径"太模糊，AI 自我合理化 |
| 3 | S13 级别 | **must-pass**（E2E > 15% 硬阻断） | P1 已验证 advisory 无效 |
| 4 | spec→tdd 约束 | test-checklist **R7**（跨会话分层一致性） | 上下文清空后约束丢失 |
| 5 | 集成测试技术栈 | **Vitest**（项目已有）+ 裸 PHP assert() | UMES3 已有 Vitest，uvu 过时 |

### 核心机制

**两层机制**：
- 第一层（认知引导）：/to-spec 模板内联决策树，AI 被迫按顺序回答问题
- 第二层（硬门禁）：S13（must-pass E2E≤15%）+ R7（/tdd 对照 spec 分层分配）

**入口守卫**：[no-test] 无业务逻辑跳过 / [hotfix] 豁免+事后补测
**防冗余**：特征测试覆盖 → /tdd 自动降级 / 不可测代码 → 先建议提取纯函数

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
