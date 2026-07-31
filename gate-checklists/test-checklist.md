# TDD 门禁检查清单

> 触发：/tdd 完成后（每个 ticket）
> 对应 v3.2 implement 阶段入口条件
> 用途：确保 TDD RED 阶段不可绕过、不可造假

## 硬性规则

| # | 规则 | 说明 |
|:-:|------|------|
| R1 | 测试先于实现 | git log 中测试文件 commit 必须早于实现文件 commit |
| R2 | 每个 `[auto]` AC 有对应测试 | "所有" = ticket 中 `[auto]` AC 数量，非模糊的"全部" |
| R3 | 不可跳过 | 简单改动可跳过 spec 评审，但不可跳过 TDD RED 阶段 |
| R4 | 逐 ticket 提交 | 每个 ticket 独立完成 RED → GREEN，不攒批 |
| R5 | Stub 返回"未实现"信号 | NotImplementedError（Python）/ 501 + error body（HTTP）/ `throw new Error('Not implemented')`（JS），不许用 404 或空响应冒充 🔴 |

## 检查项

| # | 检查项 | 对应规则 |
|:-:|--------|:---:|
| T1 | 每个 `[auto]` AC 有对应的失败测试，断言具体可验证 | R2 |
| T2 | grep `NotImplemented` / `501` / `Not implemented` 在 stub 中能找到明确信号 | R5 |
| T3 | 每个测试文件含 ticket ID 引用（`# ticket-NNN`），可追溯 | — |
| T4 | `git log --oneline` 中测试 commit 在实现 commit 之前 | R1 |
| T5 | `[human-verify]` AC 在测试文件中有 TODO 注释标注，不遗漏 | — |
| T6 | 测试按接缝分层：API 契约测试使用最高可用 seam，不穿透实现细节 | 测试宪法 |
| T7 | 断言/交互不在条件分支内静默跳过，且无恒真断言 — `expect`/`click`/`check` 不包裹在 `if (count() > 0)` 中；禁止 `toBeGreaterThanOrEqual(0)`/`typeof toBe('number')`/`>=0 toBeTruthy` | — |
| T8 | E2E 测试覆盖完整用户链路 — Action 走 UI（click/fill/submit），不绕过 UI 直接调 API 执行被测行为；Setup/Teardown 中 API 调用合法 | — |
| R7 | 分层一致性 — 对照 spec §Testing 的分层分配（S13 批准的层级），/tdd 的接缝选择与之一致；如有偏离需在测试文件中注释记录理由 | — |

## 通过条件

T1-T4 + T7 + T8 + R7 必须通过。T5-T6 为 advisory 警告。

## 签出检查（/implement 前逐条确认）

```
[ ] ticket AC 的 [auto] 项已全部映射到失败测试 → 运行测试 → 🔴
[ ] Stub 返回明确"未实现"信号，非空/404/默认值
[ ] 测试文件含 ticket ID
[ ] 测试 commit 已提交（非暂存区）
[ ] 确认无跳过意图——不是先写实现再补测试
[ ] R7: 对照 spec §Testing 分层分配，确认 /tdd 接缝选择与之一致（偏离有注释理由）
[ ] G0: 已完成故障注入验证——核心路径测试在代码破坏后正确失败
[ ] C0.5: 测试发现数 > 0 — 确认测试真的被框架发现（非 PASS(0) 真空通过）
[ ] C0.4: 固定延时已扫描——waitForTimeout 标记处已人工确认必要
```

## C0: 提交前秒检

> RED commit 前，AI 跑 5 条检查（4 grep + 1 执行验证），秒级完成。不通过 → 修复后再提交。

| # | 检查 | 命令 | 标准 |
|:--|------|------|:--:|
| C0.1 | 无调试残留 | `grep -rn "test\.only\|describe\.only\|it\.only\|page\.pause" tests/ --exclude-dir=characterization` | 零命中（characterization/ 目录排除） |
| C0.2 | 无恒真断言 | `grep -rn "toBeGreaterThanOrEqual(0)\|typeof.*toBe('number')\|BeTruthy" tests/ --exclude-dir=characterization` | 零命中（characterization/ 目录排除） |
| C0.3 | 无硬编码端口 | `grep -rn "localhost:[0-9]\{4\}" tests/ --exclude-dir=characterization` | 零命中（characterization/ 目录排除） |
| C0.5 | 测试实际执行 | 运行测试框架的 discovery 命令确认测试被发现：Playwright `npx playwright test --list`、pytest `--collect-only`、Jest `--listTests`、PHPUnit `--list-tests` | 发现数 > 0，且 ≥ 预期 RED 测试数（无静默跳过） |
| C0.4 | 无固定延时 | `grep -rn "waitForTimeout\|page\.waitForTimeout\|setTimeout.*[0-9]\{4,\}" tests/ --exclude-dir=characterization` | ⚠️ 警告级——标记后人工判断；必要的 waitForTimeout（如等待动画完成）标注理由放行 |

## C1-C5 自动预检

> RED commit 后、人工确认前，AI 自动执行以下检查并输出结构化报告。
> 人工只需看报告结论确认，无需手动跑命令。
> **项目可追加扩展项（C6+），AI 执行完整清单。**

| # | 检查项 | 自动化命令 | 通过条件 |
|:--|:--|:--|:--|
| C1 | 全部失败 | ⚠️ 前提：C0.5 已确认测试被发现。0/0=100% 是真空通过，不可接受。运行测试套件（pytest/jest/phpunit/go test/...） | 全部 🔴，0 通过/跳过 |
| C2 | 原因正确 | 单元/API 层: grep `NotImplemented` / `501` / `Not implemented` 命中数；E2E 层: 以框架预期失败机制为准（如 Playwright `test.fail()`），不以 NotImplemented/501 为 RED 信号 | 单元/API: 命中数 = 测试数；E2E: 预期失败标记覆盖数 ≥ 预期 RED 数 |
| C3 | Commit 正确 | `git log -1 --format=%s` | 含 "TDD: RED" |
| C4 | 无实现混入 | `git diff HEAD~1 --stat` | 仅测试文件 + stub，无业务逻辑文件/目录 |
| C5 | AC 全覆盖 | 逐条 AC 输出对应测试名（`AC1→test_x, AC2→test_y, ...`） | 每条 `[auto]` AC 至少 1 个测试，未覆盖标 ⚠️ |

## C7: E2E 可信度

> 适用：以 Playwright/Cypress E2E 为主要测试手段的项目
> 触发：检测到 `tests/e2e/` 目录或 `playwright.config.*` / `cypress.config.*` 存在
> 级别：⚠️ 警告（需人工审查，不自动阻断——`apiCall` 在 Setup/Teardown 中合法）

| # | 检查项 | 检测方式 | 通过条件 |
|:--|--------|------|:--|
| C7.1 | Action 走 UI | grep `apiCall\|request\.post\|fetch.*action=` 在测试文件中标记 | 标记处经人工确认均为 Setup/Teardown（非 Action） |
| C7.2 | 完整链路 | 每条测试至少含 1 次 UI 交互（click/fill/check/selectOption）+ 1 次 expect UI 断言 | click/fill 数 ≥ 测试数 |
| C7.3 | 结果断言诚实 | 提交后断言 UI 变化（success message/列表新增/Modal 关闭），不只 `toBeVisible()` 无后续 | 0 条纯 toBeVisible 无业务结果断言 |

**C7 与 C2 的关系**：C2 检查 RED 信号来源是否正确，C7 检查 Action 路径是否诚实。两者互补——C2 确认测试"失败得对"，C7 确认测试"走的是用户的路"。

### C7 预检报告追加

```
[C7] E2E 可信度:
  C7.1 Action 走 UI: N 处 apiCall — N/N 确认 Setup/Teardown ✅
  C7.2 完整链路: N 交互 / N 测试 — ✅
  C7.3 结果断言: 0 条纯 toBeVisible — ✅
```

### C7 异常处理

- **C7.1 有 apiCall 在 Action 中** → ⚠️ 标记，人工判断是否需要改为 UI 交互；Setup/Teardown 中的 apiCall 标注理由后放行
- **C7.2 交互数 < 测试数** → ⚠️ 逐条检查，确认无纯 API 测试；如有则改为 UI 交互或标注 `@test:api-only` 并说明原因
- **C7.3 有纯 toBeVisible 断言** → ⚠️ 补充业务结果断言（ant-message 成功提示 / Modal 关闭 / 列表新增记录）

### 预检报告格式

```
⚡ C1-C5 自动预检报告 — ticket NNN

[C1] 测试执行: N/N 失败 🔴 — ✅ 全部失败
[C2] 失败原因: N/N 为 NotImplemented/501 — ✅ 原因正确
[C3] RED commit: <hash> "TDD: RED — ticket NNN" — ✅
[C4] 变更文件: test_ticket_NNN.py, stub.py — ✅ 仅测试+stub
[C5] AC→测试映射: AC1→test_1, AC2→test_2, AC3→test_3 — ✅ 3/3 覆盖
[C7] E2E 可信度: C7.1 N处apiCall全确认Setup ✅ / C7.2 完整链路 ✅ / C7.3 结果断言 ✅
[C0.5] 测试发现: N 条 → N ≥ 预期 ✅
[C0.4] 固定延时: N 处 waitForTimeout — N/N 确认必要 ✅
[G0] 故障注入: 目标test_X → 注入Y → RED ✅ → 恢复GREEN ✅
[CX] RED→GREEN 断言切换: 已从"预期失败"切换到"预期成功" — ✅

结论: 10/10 通过，等待人工确认
```

### 异常处理

- **C1 有通过/跳过** → 检查测试是否真的覆盖了对应 AC，未覆盖则补测试
- **C2 有非预期 RED 信号** — 单元/API: 非 NotImplemented 错误（ImportError/SyntaxError/配置错误）→ 修复测试代码后重新运行；E2E: 非 `test.fail()` 导致的失败（基础设施错误/配置错误）→ 修复后重新运行，不提交
- **C3 无 RED commit** → 立即 `git commit -m "TDD: RED — ticket NNN"`
- **C4 含业务逻辑文件** → `git reset HEAD~1`，仅保留测试+stub，重新提交
- **C5 有 AC 未覆盖** → 标注 ⚠️，人工判断是否需要补测试；`[human-verify]` AC 可无测试

## G0: 故障注入验证（测试有效性）

> 触发：C0-C7 全部通过后，`/implement` 标记 done 之前
> 原理：Reverse Mutation Testing — 不信任从未见过失败的测试（EuroSTAR 2026）
> ADR：[007-g0-reverse-mutation-testing](../../docs/decisions/007-g0-reverse-mutation-testing.md)
> 级别：⚠️ 警告（advisory，需人工审查——部分测试不适用故障注入）

| # | 步骤 | 操作 |
|:--|------|------|
| G0.1 | 选目标 | 选一条核心用户路径的测试（E2E 或集成测试） |
| G0.2 | 注入故障 | 在被测代码中改一个关键值（参数名/字段名/条件值），使功能必错 |
| G0.3 | 验证 RED | 跑该测试，**必须失败**。若仍通过 → 断言不够强 → 修复断言后重试 G0.2 |
| G0.4 | 恢复 | 撤销故障注入，测试重新 GREEN |

### 注入规则

| 层级 | 注入方式 | 示例 |
|------|---------|------|
| E2E | 改前端 handler 中的参数名/URL | `sale_id` → `saleId_typo` |
| API 集成 | 改后端 action 返回值字段名 | `code` → `status_code` |
| 单元 | 改函数返回值/条件分支 | `return items` → `return []` |

**注入的故障产生的影响必须是用户可感知的错误**（页面报错/数据不显示/操作失败）。若注入后测试仍通过（未感知到故障），则该测试断言不够强——修复断言后重新注入。

### 范围与豁免

- **范围**：每个 feature 选 1 条核心路径测试（不要求全覆盖）
- **豁免**：`[hotfix]` ticket 跳过 G0；数据迁移/配置变更 `[no-test]` 不适用

### G0 预检报告追加

```
[G0] 故障注入验证:
  G0.1 目标: test_bundle_create（核心路径）
  G0.2 注入: sale_id 参数名改为 saleId_typo
  G0.3 RED: 测试失败 — ✅（"参数缺失"）
  G0.4 恢复: 测试重新 GREEN — ✅
```

### G0 异常处理

- **G0.3 测试未失败** → ⚠️ 断言不够强——加强断言后重新 G0.2。常见原因：`toBeVisible()` 只检查存在性、`toBeDefined()` 只检查非空、成功和失败路径走同一个断言
- **G0.2 注入影响多条测试** → 只跑目标测试（`test.only`），不影响其他

**G0 与 C7 的关系**：C7 确保"走用户的路"，G0 确保"这条路有护栏"。C7 查路径，G0 查断言强度。两者互补——C7 保证 Action 真实，G0 保证 Assertion 有效。

## /tdd → /implement 转换检查（人工签出）

> 看完 AI 预检报告后逐条确认。不通过 → 不允许启动 /implement。

```
[ ] C1: 确认测试全部失败（🔴），无意外通过
[ ] C2: 确认失败原因 = 功能未实现，非语法/import 错误
[ ] C3: 确认 RED commit 已提交，message 含 "TDD: RED"
[ ] C4: 确认 RED commit 仅含测试+stub，无业务逻辑混入
[ ] C5: 确认 AC→测试映射完整，无遗漏的 [auto] AC
[ ] C7: (E2E 项目) 确认 Action 走 UI，apiCall 仅用于 Setup/Teardown
[ ] R7: 确认 /tdd 接缝选择与 spec §Testing 分层分配一致（偏离有注释理由）
[ ] G0: 确认故障注入验证通过——核心路径测试在代码破坏后正确失败
[ ] C0.4: 确认固定延时扫描通过——waitForTimeout 标记处已确认必要
```
