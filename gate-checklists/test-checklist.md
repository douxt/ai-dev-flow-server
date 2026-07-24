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

## /tdd → /implement 转换检查

> /tdd 提交前逐条确认。不通过 → 不允许启动 /implement。

```
[ ] 所有测试已执行且全部失败（🔴），无跳过、无忽略
[ ] 失败原因 = 功能未实现（NotImplementedError/501），非语法错误/配置错误/import 失败
[ ] RED commit 已提交，message 含 "TDD: RED"
[ ] git diff RED-commit 仅含测试文件 + stub，无实现逻辑
```
