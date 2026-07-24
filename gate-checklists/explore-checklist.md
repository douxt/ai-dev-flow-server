# explore 阶段出口检查清单

> 触发：/grill-with-docs 完成后（或直接跳过后）
> 对应 v3.2 explore 阶段 → spec 阶段转换

## 检查项

| # | 检查项 | 方法 |
|:-:|--------|------|
| E1 | 工作流评估已完成 | `.workflow-route` 文件存在 |
| E2 | 需求已明确表达 | Plan Mode 初稿 或 CONTEXT.md/spec/ADR 文件存在 |
| E3 | 核心约束已提及 | 技术栈、时限、质量要求在文档中可查 |
| E4 | 关键分歧已消除 | 无未关闭的 question/讨论项 |

## 通过条件

E1 + E2 必须通过。E3/E4 为 advisory 警告。

## 产物

- Plan Mode 初稿（plan.md）或 /grill-with-docs 对齐后的需求理解
- `.workflow-route` 文件（session_id|path|timestamp）
