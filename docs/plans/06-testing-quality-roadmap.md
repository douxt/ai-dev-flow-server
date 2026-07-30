# 测试质量路线图 v1.1

> 2026-07-30 | 基于 UMES3 E2E 测试可信度调研
> 调研报告：UMES3 `docs/references/frontend-testing-best-practices-research.md`
> 最新状态：P0 ✅ / P1 ✅ / P2 ✅ → 待 UMES3 实战验证

## 当前进度总览

| 阶段 | 状态 | 产出 | 未闭环 |
|------|:--:|------|------|
| P0 E2E 可信度 | ✅ | C7 + T8 + G11 + 宪法二点七 | — |
| P1 特征测试 | ✅ | 12 文件（知识+清单+skill+4栈模块） | 3 个缺口（见 §P1 遗留缺口） |
| P2 测试分层 | ✅ | 7 文件（决策树+S13/R7+2栈模块） | 待实战验证 |
| P3 长期 | ⏳ | 调研中 | CI/CD/locator/数据工厂/hook 硬阻断 |

> **下一步**：在 UMES3 走完整流程 `/to-spec → S13 → /tdd → R7`，验证 P0-P2 实战有效性。

## 背景

UMES3 喷涂/穿条单功能开发中，C0-C6 全部门禁通过、42/42 GREEN，但人工验证"发起喷涂"第一下就报"参数缺失"。根因：75% 的测试 Action 绕过 UI（用 `apiCall()` 直接调 API），`handlePaintCreate` 内部的参数拼装、URL 构造从未被执行。

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

## P1: 遗留代码特征测试 ✅ 已完成（2026-07-30）

**解决**：改旧代码前的安全网——当前 `/tdd` 只覆盖新功能。

> 详细调研：[docs/references/characterization-tests-research.md](../references/characterization-tests-research.md)
> 差距分析：[~/.claude/plans/char-test-p1-gap-analysis.md](../../.claude/plans/char-test-p1-gap-analysis.md)

### 已实施

| # | 产出 | 文件 |
|:--|------|------|
| 1 | 通用知识（四阶段模型） | `knowledge/11-遗留代码特征测试.md` |
| 2 | 门禁清单（C-C0~C-C11） | `gate-checklists/characterization-checklist.md` |
| 3 | `/characterize` skill（ANALYZE→CAPTURE→VERIFY） | `skills/characterize/SKILL.md` |
| 4 | stage-tracker `[legacy]` 检测 | `config-templates/default/hooks/stage-tracker.sh` |
| 5 | CLAUDE.md `/characterize` 命令 | `config-templates/default/CLAUDE.md` |
| 6 | spec-checklist S12 | `gate-checklists/spec-checklist.md` |
| 7 | test-plan-template §1.1 | `templates/test-plan-template.md` |
| 8 | PHP 栈模块 | `knowledge/stacks/php/legacy-characterization.md` |
| 9 | Node 栈模块 | `knowledge/stacks/node/legacy-characterization.md` |
| 10 | Python 栈模块 | `knowledge/stacks/python/legacy-characterization.md` |
| 11 | Go 栈模块 | `knowledge/stacks/go/legacy-characterization.md` |
| 12 | 知识宪法引用 | `knowledge/09-测试质量宪法.md` |

### 遗留缺口（不紧急，待实战反馈）

| # | 缺口 | 当前缓解 | 触发条件 |
|:--|------|------|------|
| B1 | 触发时机在 `tickets:done` 太晚 | ticket `[legacy]` 标签 + S12 spec 门禁 + AI 自觉 | 发现 AI 跳过特征测试直接改遗留代码 |
| B2 | 缺生命周期文档（reconcile/删除标准/升级路径） | 核心规则三句话（GREEN/不改/可删） | 跑通首次 reconcile 流程后 |
| B3 | 多栈 Golden Master 策略不完整 | PHP 已有详细模式，Node/Python/Go 有基础栈模块 | 非 PHP 遗留项目需要时 |

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

### 已实施（7 文件）

| # | 产出 | 文件 |
|:--|------|------|
| 1 | 通用知识 + 决策树 + 反模式 + 遗留起步 | `knowledge/10-测试分层策略.md` |
| 2 | 模板增强（§0 守卫 + §1 层级分配 + §4 层级列） | `templates/test-plan-template.md` |
| 3 | S13 must-pass（E2E ≤ 15%） | `gate-checklists/spec-checklist.md` |
| 4 | R7 must-pass（分层一致性） | `gate-checklists/test-checklist.md` |
| 5 | 宪法 §三 重写（集成三子类 + E2E 硬约束） | `knowledge/09-测试质量宪法.md` |
| 6 | Node 集成测试（Vitest + nock + 4 模式） | `knowledge/stacks/node/integration-testing.md` |
| 7 | PHP 集成测试（裸 assert + 4 模式） | `knowledge/stacks/php/integration-testing.md` |

### 待验证

1. AI 是否真的按决策树走（不跳过步骤直接选 E2E）
2. S13 15% 阈值在存量 100% E2E 项目是否合理
3. R7 跨会话约束是否生效

### UMES3 实战验证（2026-07-30）

> 测试用例：`spec-bundle-pstore-mode.md`（组合入库/出库），微信小程序 + PHP 后端

| 验证项 | 结果 | 说明 |
|--------|:--:|------|
| 决策树路由 | ✅ | 正确导向 0% E2E（全部集成），与 spec 作者手动判断一致 |
| S13 门禁 | ✅ | 0/6 = 0% ≤ 15%，通过 |
| install.sh 部署 | ⚠️ | 用户级 checklist 更新成功，但项目级独立拷贝未更新 |

**发现 3 个问题**：

| # | 问题 | 影响 |
|:--|------|------|
| V1 | `install.sh --update` 只更新 `~/.claude/gate-checklists/`，不更新项目级 `.claude/gate-checklists/` 独立拷贝 | P1 S12 和 P2 S13 从未到达 UMES3 |
| V2 | 栈模块只覆盖 React/Vue，微信小程序无组件集成方案 | 决策树导向"组件集成"但实际不可执行 |
| V3 | "UI 交互 vs 数据逻辑"二分要求 AI 自行拆分混合场景 | 无明确拆分指引，AI 可能选错分支 |

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
