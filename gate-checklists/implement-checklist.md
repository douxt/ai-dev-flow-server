# implement 阶段出口检查清单

> 触发：/implement + /code-review 完成后
> 对应 v3.0 implement 阶段 → done 阶段转换
> 含内建 Maker-Checker + 独立子代理审查

## 检查项

| # | 检查项 | 方法 |
|:-:|--------|------|
| I1 | 所有 AC 逐条实现（[auto] 类全部通过测试） | grep AC + pytest |
| I2 | /code-review 完成（独立子代理审查 diff） | review 报告存在 |
| I3 | 测试不是假测试（有断言、覆盖边界） | 人工抽查 |
| I4 | 安全红线 PR 已标记（safety frontmatter → PR description） | 检查 PR body |
| I5 | 无越界文件（diff 文件全部在 ticket Scope:In 范围内） | 对比 scope |
| I6 | 认知债务解释已写入 PR（每个改动动机+影响） | 检查 PR description |
| I7 | PR 已创建并通过 CI | gh pr view |

## 通过条件

I1 + I2 + I7 必须通过。I3-I6 为 advisory 警告。

## 产物

- PR（含 /code-review 报告 + 认知债务解释 + safety 标记）
- `.devflow/stage` 更新为 `implement:done`
