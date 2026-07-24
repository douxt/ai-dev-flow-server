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

## 通过条件

T1-T4 必须通过。T5-T6 为 advisory 警告。

## 签出检查（/implement 前逐条确认）

```
[ ] ticket AC 的 [auto] 项已全部映射到失败测试 → 运行测试 → 🔴
[ ] Stub 返回明确"未实现"信号，非空/404/默认值
[ ] 测试文件含 ticket ID
[ ] 测试 commit 已提交（非暂存区）
[ ] 确认无跳过意图——不是先写实现再补测试
```

## C1-C5 自动预检

> RED commit 后、人工确认前，AI 自动执行以下 5 项检查并输出结构化报告。
> 人工只需看报告结论确认，无需手动跑命令。

| # | 检查项 | 自动化命令 | 通过条件 |
|:--|:--|:--|:--|
| C1 | 全部失败 | 运行测试套件（pytest/jest/phpunit/go test/...） | 全部 🔴，0 通过/跳过 |
| C2 | 原因正确 | 检查错误输出中 `NotImplemented` / `501` / `Not implemented` 命中数 | 命中数 = 测试数 |
| C3 | Commit 正确 | `git log -1 --format=%s` | 含 "TDD: RED" |
| C4 | 无实现混入 | `git diff HEAD~1 --stat` | 仅测试文件 + stub，无业务逻辑文件/目录 |
| C5 | AC 全覆盖 | 逐条 AC 输出对应测试名（`AC1→test_x, AC2→test_y, ...`） | 每条 `[auto]` AC 至少 1 个测试，未覆盖标 ⚠️ |

### 预检报告格式

```
⚡ C1-C5 自动预检报告 — ticket NNN

[C1] 测试执行: N/N 失败 🔴 — ✅ 全部失败
[C2] 失败原因: N/N 为 NotImplemented/501 — ✅ 原因正确
[C3] RED commit: <hash> "TDD: RED — ticket NNN" — ✅
[C4] 变更文件: test_ticket_NNN.py, stub.py — ✅ 仅测试+stub
[C5] AC→测试映射: AC1→test_1, AC2→test_2, AC3→test_3 — ✅ 3/3 覆盖

结论: 5/5 通过，等待人工确认
```

### 异常处理

- **C1 有通过/跳过** → 检查测试是否真的覆盖了对应 AC，未覆盖则补测试
- **C2 有非 NotImplemented 错误**（ImportError/SyntaxError/配置错误）→ 修复测试代码后重新运行，不提交
- **C3 无 RED commit** → 立即 `git commit -m "TDD: RED — ticket NNN"`
- **C4 含业务逻辑文件** → `git reset HEAD~1`，仅保留测试+stub，重新提交
- **C5 有 AC 未覆盖** → 标注 ⚠️，人工判断是否需要补测试；`[human-verify]` AC 可无测试

## /tdd → /implement 转换检查（人工签出）

> 看完 AI 预检报告后逐条确认。不通过 → 不允许启动 /implement。

```
[ ] C1: 确认测试全部失败（🔴），无意外通过
[ ] C2: 确认失败原因 = 功能未实现，非语法/import 错误
[ ] C3: 确认 RED commit 已提交，message 含 "TDD: RED"
[ ] C4: 确认 RED commit 仅含测试+stub，无业务逻辑混入
[ ] C5: 确认 AC→测试映射完整，无遗漏的 [auto] AC
```
