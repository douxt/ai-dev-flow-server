# 测试质量路线图 v2.0

> 全局长期方案——单一起源，持久维护，不被任务级计划覆盖。
> 配套 ADR：[006 门禁设计原则](../decisions/006-gate-architecture-principles.md) · [007 G0 反向突变测试](../decisions/007-g0-reverse-mutation-testing.md)
> 上次更新：2026-07-30

## 文档定位

本文档是 DevFlow 测试质量体系的**唯一持久路线图**。所有反馈、调研、决策在此归口：

```
UMES3 feedback/memory/xxx.md   →   Inbox  →  归类到阶段 N  →  重大决策写 ADR  →  实施
```

每次新反馈追加到 Inbox，定期归类；阶段可无限追加，编号不覆盖。

---

## Inbox：待处理反馈

> 新反馈先入此，标注来源+日期+优先级。归类后移入对应阶段，Inbox 中留引用。

| # | 来源 | 摘要 | 优先级 | 日期 | 归类 |
|:--|------|------|:--:|------|:--|
| F1 | UMES3 `process-feedback-session-20260730.md` | G0 反向突变测试——补形式vs有效性缺口 | P0 | 07-30 | ✅ 已实施 |
| F2 | 同上 | C0 扩展 waitForTimeout 扫描（100+ 残留） | P1 | 07-30 | ✅ 已实施 |
| F3 | 同上 | C5 报告增加测试分类（烟雾/契约/交互/错误态） | P2 | 07-30 | → 阶段五 |
| F4 | 同上 | playwright.config.js 模板默认 workers:2 | P1 | 07-30 | ✅ 已实施 |
| F5 | 同上 | 文档一致性检查（CLAUDE.md vs RULES.md 端口冲突） | P2 | 07-30 | → 阶段六 |
| F6 | 同上 | 门禁"伤疤"增长模式 → 通用防线设计原则 | P0 | 07-30 | ✅ ADR-006 |
| F7 | P1 差距分析 | B1 触发时机：tickets:done → 改动前 | P2 | 07-30 | → 阶段七 |
| F8 | 同上 | B2 生命周期文档：reconcile/删除/升级 | P2 | 07-30 | → 阶段七 |
| F9 | 同上 | B3 多栈 Golden Master（Node/Python/Go） | P3 | 07-30 | → 阶段七 |
| F10 | P2 验证 | V2 微信小程序组件集成方案 | P3 | 07-30 | → 阶段七 |
| F11 | P2 验证 | V3 决策树"UI vs 数据"混合场景指引 | P3 | 07-30 | → 阶段七 |
| F12 | P2 验证 | V1 install.sh 未更新项目级 checklist | P0 | 07-30 | ✅ 已修 |

---

## 阶段模板

每个阶段按此结构展开：

```markdown
## 阶段 N：阶段名

**状态**：✅ / 🔵 / ⏳
**触发事件**：什么反馈或事故促成了这个阶段
**ADR**：关联的架构决策（如有）
**设计摘要**：核心设计决策（2-3 句）

### 已完成
| # | 产出 | 文件 |

### 待办
| # | 事项 | 来源 | 优先级 | 阻塞条件 |
```

---

## 阶段一：E2E 可信度 ✅

**触发事件**：UMES3 42/42 GREEN → 手工"参数缺失"，75% 测试 Action 绕过 UI

**设计摘要**：测试必须走用户真实路径。Action 用 `page.click`/`page.fill`，`apiCall` 仅限 Setup/Teardown。E2E RED 信号以 `test.fail()` 为准（Playwright 官方 TDD 机制）。

### 已完成

| # | 产出 | 文件 |
|:--|------|------|
| 1 | T8 E2E 测试完整性（Action 走 UI） | `gate-checklists/test-checklist.md` |
| 2 | C7 E2E 可信度（Action 路径 + 完整链路 + 结果断言） | `gate-checklists/test-checklist.md` |
| 3 | E2E RED 信号以 `test.fail()` 为准 | `gate-checklists/test-checklist.md` §C2 |
| 4 | G11 Action 绕过检测 + apiCall/@test:api-only 规则 | `knowledge/stacks/playwright/test-quality.md` |
| 5 | 宪法 §二点七（Action-via-UI 原则） | `knowledge/09-测试质量宪法.md` |
| 6 | 宪法 §二点五 C2 E2E 变体（test.fail） | `knowledge/09-测试质量宪法.md` |

---

## 阶段二：遗留代码安全网 ✅

**触发事件**：UMES3 ChainSellDetail.js 9044 行，80% 改动是修改已有行为，当前 `/tdd` 只覆盖新功能

**设计摘要**：改旧代码前先锁行为。四阶段串行——`/characterize → 预重构 → /tdd → 后重构`。特征测试独立目录 `tests/characterization/`，生命周期与 TDD 测试分离。

### 已完成

| # | 产出 | 文件 |
|:--|------|------|
| 1 | 通用知识（四阶段模型 + 接缝识别 + Golden Master） | `knowledge/11-遗留代码特征测试.md` |
| 2 | 门禁清单（C-C0~C-C11） | `gate-checklists/characterization-checklist.md` |
| 3 | `/characterize` skill（ANALYZE→CAPTURE→VERIFY） | `skills/characterize/SKILL.md` |
| 4 | stage-tracker `[legacy]` ticket 自动提示 | `config-templates/default/hooks/stage-tracker.sh` |
| 5 | CLAUDE.md `/characterize` 命令注册 | `config-templates/default/CLAUDE.md` |
| 6 | spec 阶段 S12（特征测试强制） | `gate-checklists/spec-checklist.md` |
| 7 | 模板 §1.1（特征测试策略） | `templates/test-plan-template.md` |
| 8-11 | 4 个技术栈模块 | `knowledge/stacks/{php,node,python,go}/legacy-characterization.md` |
| 12 | 宪法引用 | `knowledge/09-测试质量宪法.md` |

---

## 阶段三：测试分层体系 ✅

**触发事件**：UMES3 42 条测试 100% E2E，0 集成，0 单元——Ice Cream Cone 反模式

**设计摘要**：两层机制——决策树（认知引导） + 硬门禁 S13/R7（不可绕过）。入口守卫 `[no-test]`/`[hotfix]`，防冗余检查。技术栈按项目现状选（Vitest），不装新框架。

### 已完成

| # | 产出 | 文件 |
|:--|------|------|
| 1 | 统一集成测试定义 + 6 步决策树 + 反模式 + 遗留起步 | `knowledge/10-测试分层策略.md` |
| 2 | 模板 §0 `[no-test]` 守卫 + §1 层级分配表 | `templates/test-plan-template.md` |
| 3 | S13 must-pass（E2E ≤ 15%） | `gate-checklists/spec-checklist.md` |
| 4 | R7 must-pass（分层一致性——跨会话约束） | `gate-checklists/test-checklist.md` |
| 5 | 宪法 §三 重写（集成三子类 + 层级选择 + E2E 硬约束） | `knowledge/09-测试质量宪法.md` |
| 6 | Node 集成测试（Vitest + nock + 4 模式） | `knowledge/stacks/node/integration-testing.md` |
| 7 | PHP 集成测试（裸 assert + 4 模式） | `knowledge/stacks/php/integration-testing.md` |

---

## 阶段四：测试有效性验证 ← 下步进入

**状态**：🔵 进行中
**触发事件**：UMES3 连续三次"47/47 GREEN → 手工'参数缺失'"，现有 C0-C7 门禁全查形式不查有效性
**ADR**：[006 门禁设计原则](../decisions/006-gate-architecture-principles.md) · [007 G0 反向突变测试](../decisions/007-g0-reverse-mutation-testing.md)

**设计摘要**：门禁体系从单轴线（形式）扩展为双轴线（形式 + 有效性）。G0 是通用有效性防线——破坏代码 → 验证测试必须失败 → 恢复。不追加特化规则（C8/C9…），优先扩展通用防线。

### 已完成

| # | 产出 | 文件 |
|:--|------|------|
| 4.1 | G0 故障注入验证（流程+注入规则+预检报告+异常处理+人工签出） | `gate-checklists/test-checklist.md` |
| 4.2 | C0.4 固定延时扫描（waitForTimeout 警告级） | `gate-checklists/test-checklist.md` |

### 待办

| # | 事项 | 来源 | 优先级 |
|:--|------|------|:--:|
| 4.3 | 断言强度等级纳入知识文档（精确值 > 集合/结构 > 数量/范围 > 存在性 > 恒真） | F1 | P1 |

---

## 阶段五：门禁自动化与深化

**状态**：⏳ 计划中
**触发事件**：C5 只报数量不报分类 / CI/CD 无分层门禁 / P1 硬阻断靠 AI 自觉不可靠

**设计摘要**：门禁从"AI 自觉 + 人工确认"向"自动化脚本 + 硬阻断"演进。分层门禁：pre-commit → C0 + unit，PR → integration，merge → E2E。

### 待办

| # | 事项 | 来源 | 优先级 | 阻塞条件 |
|:--|------|------|:--:|------|
| 5.1 | C5 报告增加测试分类（烟雾/API契约/UI交互/错误态） | F3 | P2 | — |
| 5.2 | CI/CD 分层门禁（pre-commit/PR/merge 三级） | P3 远期 | P2 | 阶段三分层测试落地后 |
| 5.3 | P1 硬阻断：PreToolUse hook 拦截未完成 `/characterize` 的 `[legacy]` ticket | P3 远期 | P2 | 阶段二试点稳定后 |
| 5.4 | C0 脚本化——自动扫描 if-count 静默跳过 + 断言强度 | P3 远期 | P2 | — |

---

## 阶段六：工程基础设施

**状态**：🔵 部分完成
**触发事件**：47 条 E2E 耗时 430s / UMES3 测试数据硬编码 / 文档矛盾（CLAUDE.md vs RULES.md）

**设计摘要**：性能优化（workers:2 默认，45% 提速）、数据管理（测试数据工厂）、文档治理（单一定义源）、Locator 质量标准。

### 已完成

| # | 产出 | 文件 |
|:--|------|------|
| 6.1 | 性能优化建议（workers:2 + 页面导航 load+waitForSelector） | `knowledge/stacks/playwright/test-quality.md` |

### 待办

| # | 事项 | 来源 | 优先级 | 阻塞条件 |
|:--|------|------|:--:|------|
| 6.2 | 文档一致性规则——同类约束只在一处定义，其余引用 | F5 | P2 | — |
| 6.3 | 测试数据工厂标准化（fixture/factory/seeder 模板） | P3 远期 | P2 | — |
| 6.4 | Locator 质量规则（role > text > testid > css） | P3 远期 | P3 | — |
| 6.5 | 测试执行时间监控与预算 | P3 远期 | P3 | — |

---

## 阶段七：覆盖缺口补充

**状态**：⏳ 计划中
**触发事件**：P1 差距分析（3 缺口） + P2 UMES3 验证（2 缺口）

**设计摘要**：低优先级改进——特征测试生命周期完善、多栈 Golden Master、微信小程序支持、决策树混合场景指引。不阻塞主流程，等实战反馈驱动。

### 待办

| # | 事项 | 来源 | 优先级 | 阻塞条件 |
|:--|------|------|:--:|------|
| 7.1 | B1：特征测试触发时机从 `tickets:done` 提前到改动开始前 | F7 | P2 | AI 实际跳过 `/characterize` 的证据 |
| 7.2 | B2：特征测试生命周期文档（reconcile 流程/删除标准/升级路径） | F8 | P2 | 首次 reconcile 流程跑通后 |
| 7.3 | B3：多栈 Golden Master 完善（Node snapshot/Python syrupy/Go golden） | F9 | P3 | 非 PHP 项目需要时 |
| 7.4 | V2：微信小程序前端测试方案（替代 Vitest+Testing Library） | F10 | P3 | 微信小程序项目新增测试需求时 |
| 7.5 | V3：决策树增加"混合场景（UI+数据）拆分指引" | F11 | P3 | AI 实际选错分支的证据 |

---

## 变更记录

| 日期 | 版本 | 变更 |
|------|:--:|------|
| 2026-07-30 | v2.0 | 重构为 7 阶段 + Inbox + ADR 006/007。合并 P1 差距分析、P2 验证发现、UMES3 反馈、P3 远期全部待办 |
| 2026-07-30 | v1.1 | P0/P1/P2 完成标记 + 待验证清单 |
| 2026-07-30 | v1.0 | 初始版本（基于 UMES3 E2E 调研） |

## 关联资源

- [测试分层策略调研](../references/testing-layering-research.md)
- [特征测试最佳实践调研](../references/characterization-tests-research.md)
- [P1 差距分析](~/.claude/plans/char-test-p1-gap-analysis.md)
- [UMES3 流程反馈 2026-07-30](/home/dou/projects/UMES3/memory/process-feedback-session-20260730.md)
