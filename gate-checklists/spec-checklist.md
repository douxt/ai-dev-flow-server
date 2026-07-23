# spec 阶段出口检查清单

> 触发：/to-spec 完成后
> 对应 v3.0 spec 阶段 → tickets 阶段转换
> 对照宪法：Spec 质量宪法（11 项 + Ponytail + 三假设 + 5 级验证层级）

## 检查项

| # | 检查项 | 对应宪法 |
|:-:|--------|:---:|
| S1 | 六段齐全（Problem/Solution/US/Impl/Test/OOS） | #1 |
| S2 | Risks ≥5 + 缓解措施 | #2 |
| S3 | AC 定量可测（EARS 格式推荐） | #3 |
| S4 | 异常路径 4 类覆盖 | #4 |
| S5 | 外部依赖接口签名明确 | #5 |
| S6 | 工作量估算 ≤5d | #7 |
| S7 | Ponytail 四问已写入 §Decisions | P1-P4 |
| S8 | 三假设（技术/行为/边界）已审计 | H1-H3 |
| S9 | 验证方案标注等级（L1-L5） | 验证层级 |
| S10 | spec.md 存在且非空 | 产物检查 |

## 通过条件

S1-S5 + S10 必须通过。S6-S9 为 advisory 警告。

## 产物

- `spec.md`（含 Ponytail 四问 + 三假设审计 + 验证方案）
