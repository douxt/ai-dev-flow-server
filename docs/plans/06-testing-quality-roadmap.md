# 测试质量路线图 v2.2

> 全局长期方案——单一起源，持久维护，不被任务级计划覆盖。
> 配套 ADR：[006 门禁设计原则](../decisions/006-gate-architecture-principles.md) · [007 G0 反向突变测试](../decisions/007-g0-reverse-mutation-testing.md)
> 上次更新：2026-08-05

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
| F13 | UMES3 开发实践 | 测试数据工厂——流程化引导：评估复杂度→提案→审批→创建（关联 6.3） | P2 | 07-31 | → 阶段六 |
| F14 | UMES3 `session-status-report-20260731.md` | G0 首次完整闭环验证 + webpack 三层阻断修复 | P1 | 07-31 | → 阶段四 |
| F15 | 本会话 | hook 提醒过期导致质量门禁不被执行——stage-tracker/workflow-gate 已修 | P1 | 07-31 | ✅ 已修 |
| F16 | 社区调研 | 门禁分层阻断——L0 硬阻断(C0.5 exit 2)+L1 软阻断+L2 验证+L3 独立审查。社区三条铁律 | P1 | 07-31 | → 阶段五（已纳入设计原则） |
| F17 | UMES3 持续假 GREEN + 2026-08-01 调研 | AI reward hacking——GREEN 侧零门禁，7 种假 GREEN 手段仅 1 种被拦。需 GREEN 侧验证体系（G1-G4） | P0 | 08-01 | → 阶段八 |
| F18 | UMES3 `test-effectiveness-gap-20260801.md` | C0.8 断言强度扫描 + G0 自动化脚本 + 单测试级检查 + Playwright matchers | P0 | 08-01 | ✅ 已实施 |
| F19 | UMES3 多轮正则验收反馈 | C0.8 正则 Bug（expect(.*)贪婪 + \(\)空括号）+ 单文件蒙面效应 + dev-server编译等待 + config排除 | P1 | 08-01 | ✅ 已实施 |
| F20 | UMES3 `test-coverage-gap-in-dev-flow.md` | C0.9 代码覆盖率秒检——第四个质量维度（执行完整性） | P0 | 08-01 | ✅ 已实施 |
| F21 | UMES3 会话反馈 | v3.2 tickets:reviewed 独立阶段——审查从 advisory 提醒升级为显式 Gate | P1 | 08-01 | ✅ 已实施 |
| F22 | UMES3 `tdd-skip-leads-to-untested-features.md` | Plan Mode 方案太详细→Agent 跳过 /tdd→4功能无E2E覆盖。根因：阶段间缺硬阻断 | P0 | 08-04 | ✅ 5.7 stage-gate-block.sh |
| F23 | UMES3 `weak-assertion-gate-failure-20260804.md` | C0.8 三级检查全为 ⚠️ 警告不被 test-gate-block.sh 拦截。升级为 FAIL=1 硬阻断 | P0 | 08-04 | ✅ C0.8 升级硬阻断 |
| F24 | 同上 | 语义弱断言——`toBeGreaterThan(0)` 在白名单但语义弱（搜唯一订单返 19 条仍 PASS）。grep 无法区分，需 G0/G4 覆盖 | P2 | 08-04 | → 阶段八 G0/G4 |
| F25 | 同上 | AC-断言一致性校验——测试断言方向（正向/反向）与 spec AC 对齐检查，需 LLM 语义理解 | P3 | 08-04 | → 阶段五 5.4 |
| F26 | 2026-08-05 综合调研（20+来源） | G0 硬性化——将"建议跑 G0"升级为 implement:done 硬阻断（stage-verify.sh 检查 G0 执行证据） | P1 | 08-05 | ✅ 已实施 (5.10) |
| F27 | 同上 | 5.4 独立审查最低成本版——implement:done 强制要求 /code-review 产物 + stage-verify 检测 | P1 | 08-05 | → S2 短期 |
| F28 | 同上 | G0 全自动化——CI 集成变异测试，RED commit 后自动触发 g0-inject.sh | P2 | 08-05 | → S3 中期 |

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

## 阶段四：测试有效性验证 ✅

**状态**：✅ 已完成
**触发事件**：UMES3 连续三次"47/47 GREEN → 手工'参数缺失'"，现有 C0-C7 门禁全查形式不查有效性
**ADR**：[006 门禁设计原则](../decisions/006-gate-architecture-principles.md) · [007 G0 反向突变测试](../decisions/007-g0-reverse-mutation-testing.md)

**设计摘要**：门禁体系从单轴线（形式）扩展为双轴线（形式 + 有效性）。G0 是通用有效性防线——破坏代码 → 验证测试必须失败 → 恢复。不追加特化规则（C8/C9…），优先扩展通用防线。

### 已完成

| # | 产出 | 文件 |
|:--|------|------|
| 4.1 | G0 故障注入验证（流程+注入规则+预检报告+异常处理+人工签出） | `gate-checklists/test-checklist.md` |
| 4.2 | C0.4 固定延时扫描（waitForTimeout 警告级） | `gate-checklists/test-checklist.md` |
| 4.2.5 | G0 首次完整闭环验证 — UMES3 paint-select-create AC7: 注入→RED→恢复→GREEN ✅（F14） | UMES3 worktree |
| 4.2.6 | hook 提醒补全 — stage-tracker/workflow-gate 覆盖 S13/C7/G0/R7/决策树（F15） | `config-templates/default/hooks/` |
| 4.3 | C0.5 测试执行验证 — 防 PASS(0) 真空通过 | `gate-checklists/test-checklist.md` |
| 4.4 | C0.6 try/catch 腐烂断言检测 — T7 扩展 + 宪法同步 | `gate-checklists/test-checklist.md` + `knowledge/09-测试质量宪法.md` |
| 4.5 | 通用 test-gate.sh — C0.1-C0.6 跨框架自动秒检 | `scripts/test-gate.sh` |
| 4.6 | G0 @skip-g0 跳过理由要求 | `gate-checklists/test-checklist.md` |
| 4.7 | install.sh 项目级同步盲区修复 — gate-checklists + hooks 双通道 | `install.sh` |
| 4.8 | install.sh ADR + RULES.md 部署 | `install.sh` + `templates/RULES.md.test-quality` |

### 待办

（全部完成）

---

## 阶段五：强制执行硬化

**状态**：🔵 进行中
**触发事件**：本会话验证——hook 提醒虽已补全，但全链路仍为 advisory，AI 可跳过。社区调研（F16）确认：**advisory 警告 = 不存在**，exit 2 是 Claude Code 唯一可靠阻断机制。2026-08-04 UMES3 反馈（F22）：Plan Mode 方案太详细→Agent 跳过 /tdd→4 功能无 E2E 覆盖，根因同样是阶段间无硬阻断。
**设计原则**：[社区三条铁律](#三条铁律)

**设计摘要**：从"AI 自觉 + 人工确认"向"硬阻断 + 独立审查"演进。2026-08-04 综合调研（20+ 来源）确认行业方向从 prompt-based suggestions → code-enforced auditable gates。四层渐进式硬化模型，每层可独立实施。

### 三条铁律

> 来源：Makoto / Make No Mistakes 独立收敛 + 68 次 Claude Code 失败分析（[5-Layer QA System](https://github.com/anthropics/claude-code/issues/29795)）

1. **无证据不声明** — AI 说"测试全绿"不算，必须看工具输出
2. **作者不自审** — 写代码的 session 不能审自己的代码
3. **不能失败的检查不是检查** — advisory 警告可被跳过 = 形同虚设

### 社区最佳实践对标（2025-2026 调研）

> 来源：tdd-enforcer (Pi Coding Agent)、tdd-ai (CLI state machine)、correctless (agent separation)、
> QFAI (traceability gates)、XP Gates (4 sequential blocking constraints)、
> opencode-android-tdd (code-enforced RED classifier)、TDFlow (multi-agent TDD decomposition)

| 模式 | 机制 | 行业标杆 | 我方对标 | 差距 |
|------|------|------|:--:|------|
| **阶段间硬阻断** | PreToolUse exit 2 按 stage 阻断 | tdd-enforcer phase-locked file access | test-gate-block.sh | **缺失 stage-gate-block.sh** |
| **文件级阶段锁定** | RED 禁写实现文件，GREEN 禁写测试 | tdd-enforcer/tool-layer interception | G1 反作弊提示(advisory) | **需升级为硬阻断** |
| **过渡门禁验证** | 阶段推进前自动验证条件 | tdd-ai gate checks (test must fail→RED→GREEN) | 仅产物检测(有文件即推进) | **缺产物质量校验** |
| **独立审查** | 写代码 agent ≠ 审代码 agent | TDFlow/correctless multi-agent isolation | ❌ | **全链路缺失** |
| **证据链** | 每阶段产物哈希锁定+签名 | Sigstore/cryptographic attestation | ❌ | **远期** |
| **确定性门禁** | Block/Warn/Allow 三态 | Quality Gateway Pattern 5-layer | exit 2/警告/@skip | 基本对齐 |

### 四层渐进硬化模型

```
第一层（P0·今天）：阶段间硬阻断  ← stage-gate-block.sh
  检测 .devflow/stage，阶段不满足 → exit 2 阻断 Write/Edit/implement

第二层（P1）：文件级阶段锁定    ← 扩展 test-gate-block.sh
  RED 阶段禁止写实现文件，GREEN 阶段禁止改测试

第三层（P1）：过渡门禁验证      ← stage-verify.sh
  阶段推进前验证产物质量（非仅检测存在）

第四层（P2）：独立审查 + 证据链  ← 多 agent 分离 + 哈希锁定
  写代码 session ≠ 审代码 session，关键产物不可篡改
```

### 四层阻断模型（当前实现）

```
L0: PreToolUse 硬阻断（exit 2）  ← C0.5 测试发现 + test-gate.sh 全绿
L1: Pre-commit 软阻断            ← C0.1-C0.6 grep + lint/type
L2: Pre-implement 验证           ← C1-C5 + C7 + G0 故障注入
L3: 独立会话审查                ← 另一 session 审代码（铁律 2）
     ↑ 仅高风险改动触发
```

### 已完成

| # | 产出 | 文件 |
|:--|------|------|
| 5.0 | 社区调研 + 三条铁律 + 四层阻断方案（F16） | `docs/plans/06-testing-quality-roadmap.md` |
| 5.0.1 | G0 @skip-g0 跳过理由机制（为 L1-L3 @skip 模式铺路） | `gate-checklists/test-checklist.md` |
| 5.1 | L0 硬阻断：PreToolUse hook（test-gate-block.sh）exit 2 拦截 RED commit + Archon red-gate 节点 | `config-templates/default/hooks/test-gate-block.sh` · `config-templates/default/settings.json` · `archon/auto-execute-afk.yaml` |
| 5.1.1 | C0.7 if-count/length===0→return 检测（Skip Test 硬阻断） | `scripts/test-gate.sh` · `gate-checklists/test-checklist.md` |
| 5.1.2 | C0.8 断言强度门禁（全局比率+单文件操作-断言匹配+操作行级蒙面检测） | `scripts/test-gate.sh` · `gate-checklists/test-checklist.md` |
| 5.1.3 | C0.9 代码覆盖率秒检（vitest/jest coverage 解析+阈值比较） | `scripts/test-gate.sh` · `gate-checklists/test-checklist.md` |
| 5.1.4 | C0.3 测试配置文件排除（playwright/vitest/jest/webpack/vite config） | `scripts/test-gate.sh` |
| 5.1.5 | 强断言正则完整覆盖（数值比较+Playwright web-first matchers 共12种） | `scripts/test-gate.sh` |
| 5.1.6 | v3.2 tickets:reviewed 独立阶段（advisory→显式Gate） | `config-templates/default/hooks/stage-tracker.sh` · `docs/design/gate-design.md` |
| 5.1.7 | 社区调研——四层渐进硬化模型+6维对标 | `docs/plans/06-testing-quality-roadmap.md` |
| 5.7 | **stage-gate-block.sh**——PreToolUse 按 .devflow/stage 阻断越阶段操作（stage < tdd:done 禁写非测试文件，exit 2 硬阻断） | `config-templates/default/hooks/stage-gate-block.sh` · `config-templates/default/settings.json` |
| 5.8 | **文件级阶段锁定**——GREEN 窗口（stage>=tdd:done + 最后commit RED）禁改测试文件（G1反作弊 exit 2 硬阻断）+ 断言最终形式标准化 + ADR-009 |
| 5.9 | **stage-verify.sh**——过渡门禁验证，阶段推进前校验产物质量（非仅检测存在）+ 阶段跳跃反向验证 + green-gate exit 1 + 死循环检测 |
| 5.3 | **ASI 五级量表知识文档**——断言强度指数正式文档（5级+场景矩阵+C0.8映射+G0关系） | `knowledge/12-断言强度指数.md` | `config-templates/default/hooks/stage-gate-block.sh` · `knowledge/09-测试质量宪法.md` · `docs/decisions/009-file-level-phase-locking.md` |

### 待办（按四层模型排序）

| # | 事项 | 来源 | 优先级 | 层 | 阻塞条件 |
|:--|------|------|:--:|:--:|------|



| 5.4 | L3 独立会话审查——另一 session 跑 /review-cc-cli | F16+调研 | P2 | 四 | 5.7 落地后 |
| 5.2 | C5 报告增加测试分类（烟雾/API契约/UI交互/错误态） | F3 | P2 | — | — |
| 5.5 | @skip 理由机制推广到 C7/G0 之外的门禁 | F16 | P2 | — | 5.1 落地后 |
| 5.6 | PreToolUse hook 拦截未完成 `/characterize` 的 `[legacy]` ticket | 5.3 原 | P2 | 二 | 阶段二试点稳定后 |

### 2026-08-05 优先级路线（基于 20+ 来源调研）

五层防护模型：Spec-First → User-Path E2E → Mutation Gate → Independent Verify → CI Quality Gate。DevFlow 已完成 Layer 1/2/5 大部分，Layer 3（G0）半覆盖，Layer 4（独立审查）待建。

| 优先级 | # | 事项 | 投入 | 堵什么漏洞 |
|:--:|:--|------|:--:|------|
| **S1 立即** | 5.10 | ✅ G0 硬性化——g0-inject.sh 成功后写 `.devflow/.g0-passed` 标记；stage-verify.sh `implement:done` I4 检查标记存在且比 RED commit 新，未跑 G0 不推进 | ~15行 | Agent 跳过 G0 → 假 GREEN 漏网 |
| **S2 短期** | 5.4-Lite | 独立审查最低成本版——implement:done 强制 /code-review 产物 + stage-verify 检测 `.devflow/code-review-report.md` | ~20行 | Agent 自审自代码 → 恒真断言无人发现 |
| **S3 中期** | 8.5 | G0 全自动化——RED commit 后自动触发 g0-inject.sh 关键路径，结果写入 trace | ~30行 | G0 靠人记 → 忘跑 |
| 远期 | 5.4-Full | L3 完整独立审查——另一 session 跑 /review-cc-cli | 流程设计 | 同模型审查回声效应 |
| 远期 | 8.3 | G4 独立 verifier prompt | prompt 设计 | 7 种假 GREEN 手段 #3/#5 |

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

## 阶段八：GREEN 侧验证体系

**状态**：🔵 进行中
**触发事件**：UMES3 持续数月"测试全 GREEN → 人工一戳基本功能走不通"。2026-08-01 综合调研（12 篇来源）确认：AI agent 在 /implement 阶段存在 7 种制造假 GREEN 的手段，现有门禁仅覆盖 1 种。
**ADR**：[008-green-side-gate-architecture](../decisions/008-green-side-gate-architecture.md)

**设计摘要**：门禁体系从 RED 单侧扩展为 RED+GREEN 双侧。GREEN 侧五层验证模型：秒检(diff)→规则注入(prompt)→DONE 重检→独立验证→自主验收。P0 落地 G1+G2（覆盖 7 种假 GREEN 中的 4 种）。

### 已完成

| # | 产出 | 文件 |
|:--|------|------|
| 8.0 | 根因调研 + 社区最佳实践综合 | `docs/research/ai-false-green-root-cause-analysis-20260801.md` |
| 8.0.1 | ADR-008：GREEN 侧门禁设计原则 | `docs/decisions/008-green-side-gate-architecture.md` |
| 8.0.2 | G0 自动化脚本 g0-inject.sh（5步自动化+5策略+dev-server编译等待+硬阻断） | `scripts/g0-inject.sh` |
| 8.0.3 | G0 级别升级（⚠️警告→❌硬阻断）+ test-checklist 同步 | `gate-checklists/test-checklist.md` |
| 8.0.4 | G0 策略4跳过JSX + 策略5优先非render函数 | `scripts/g0-inject.sh` |
| 8.1.1 | green-gate.sh 纳入 install.sh 部署管线 | `install.sh` |
| 8.1.2 | settings 智能合并替代 jq `*` 数组覆盖 | `scripts/merge-settings.py` |

### 待办

| # | 事项 | 来源 | 优先级 | 阻塞条件 |
|:--|------|------|:--:|------|
| 8.1 | G1：双注入点反作弊规则（stage-tracker tdd:done + workflow-gate） | F17 | P0 | ✅ 已实施 |
| 8.2 | G2：green-gate.sh diff 秒检脚本（G2.1测试文件修改+G2.2空数据+G2.3 skip/only） | F17 | P0 | ✅ 已实施 |
| 8.3 | G4：独立 verifier prompt——新 context 逐条 AC 对照 diff | F17 | P1 | 8.1/8.2 落地后 |
| 8.4 | G5：GREEN G0——/implement 完成后破坏一条逻辑→确认有测试变红→恢复（g0-inject.sh 已实现自动化+5策略+dev-server等待+硬阻断；G5流程集成+单测/集成优先待完善） | F17 | P1 | 8.3 落地后 |
| 8.5 | G8：Knight Rider 夜间自主验收（独立 agent 驱动实际应用） | F17 | P2 | 需 harness 开发 |

---

## 变更记录

| 日期 | 版本 | 变更 |
|------|:--:|------|
| 2026-08-06 | v2.13 | 5.10 G0 硬性化——g0-inject.sh 成功后写 `.devflow/.g0-passed` 标记；stage-verify.sh implement:done I4 检查标记存在且比 RED commit 新；未跑 G0 不推进 implement:done |
| 2026-08-05 | v2.12 | 2026-08 综合调研（20+来源）→ 五层防护模型 + S1/S2/S3 优先级路线 + F26-F28 Inbox |
| 2026-08-05 | v2.11 | 5.3 ASI 五级量表知识文档——5级+场景决策矩阵+C0.8映射+G0关系 + test-checklist C0.8 级别同步（警告→硬阻断）|
| 2026-08-04 | v2.10 | 5.9 stage-verify.sh——过渡门禁验证 + 阶段跳跃反向验证 + green-gate exit 1 + 死循环检测 |
| 2026-08-04 | v2.9 | 5.8 文件级阶段锁定——GREEN 窗口禁改测试（G1 硬阻断）+ 断言最终形式标准化 + ADR-009 |
| 2026-08-04 | v2.8 | C0.8 三级检查全部升级为 FAIL=1 硬阻断——弱断言占比/文件级/行级不再仅警告 |
| 2026-08-04 | v2.7 | 5.7 stage-gate-block.sh 落地——PreToolUse exit 2 按阶段阻断越级写入，四层硬化模型第一层完成 |
| 2026-08-04 | v2.6 | 阶段五重写——社区对标(6维)+四层渐进硬化模型+5.7-5.9新增。行业调研(20+来源)写入。F22入Inbox |
| 2026-08-01 | v2.5 | C0.7-C0.9 新增 + G0 自动化(g0-inject.sh) + G1/G2 落地 + v3.2 tickets:reviewed + 多轮正则修复(Playwright matchers/数值比较/非贪婪) |
| 2026-08-01 | v2.4 | 阶段八新建——GREEN 侧验证体系。假 GREEN 根因调研 + ADR-008。F17 入 Inbox |
| 2026-07-31 | v2.3 | 5.1 L0 硬阻断 ✅：test-gate-block.sh（PreToolUse exit 2）+ settings.json 模板 + Archon red-gate 节点 + implement prompt 嵌入 |
| 2026-07-31 | v2.2 | 阶段四 ✅ 关闭（8 项完成）。阶段五重写：CI/CD 自动化 → 强制执行硬化（三条铁律+四层阻断模型）。4.3 迁入阶段五。F16 纳入设计原则 |
| 2026-07-31 | v2.1 | Inbox 新增 F13（测试数据工厂）、F14（G0 首次闭环）、F15（hook 提醒修复）。阶段四 4.2.5（G0 首次闭环）已完成 |
| 2026-07-30 | v2.0 | 重构为 7 阶段 + Inbox + ADR 006/007。合并 P1 差距分析、P2 验证发现、UMES3 反馈、P3 远期全部待办 |
| 2026-07-30 | v1.1 | P0/P1/P2 完成标记 + 待验证清单 |
| 2026-07-30 | v1.0 | 初始版本（基于 UMES3 E2E 调研） |

## 关联资源

- [测试分层策略调研](../references/testing-layering-research.md)
- [特征测试最佳实践调研](../references/characterization-tests-research.md)
- [P1 差距分析](~/.claude/plans/char-test-p1-gap-analysis.md)
- [UMES3 流程反馈 2026-07-30](/home/dou/projects/UMES3/memory/process-feedback-session-20260730.md)
