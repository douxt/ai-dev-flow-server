# tickets 阶段出口检查清单

> 触发：/to-tickets 完成后 + check_constitution.py 检查通过
> 对应 v3.0 tickets 阶段 → implement 阶段转换
> 对照宪法：Ticket 质量宪法（15 项 + 安全红线）

## 检查项

| # | 检查项 | 来源 |
|:-:|--------|:---:|
| T1 | check_constitution.py 15 项全部通过（0 fail） | 自动 |
| T2 | 每 ticket ≤ 窗口 40%（~48K token） | #15 |
| T3 | 所有 AC 标注验证级别（[auto]/[human-verify]/[decision]） | 模板 |
| T4 | blocked_by 无循环依赖 | #9 |
| T5 | 安全红线标记已处理（auth/payment/crypto/delete/permission → safety frontmatter） | 08 宪法 |
| T6 | issues/ 目录下所有 .md 可解析 | 自动 |

## 通过条件

T1 + T2 必须通过。T3-T5 为 advisory 警告。

## 产物

- `issues/` 目录（每个 ticket ≤ 48K token，带 safety 标记）
- `check_constitution.py --batch issues/ --json` 全部通过
