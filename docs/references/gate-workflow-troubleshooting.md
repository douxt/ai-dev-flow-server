# Gate 1 Workflow 自动化执行问题报告

> 日期: 2026-06-28 | 项目: cuotiben (错题本) | 报告人: Claude Code | 来源: `/home/www/cuotiben/docs/gate-1-workflow-issue.md`

## 现象

`gate-1-grill` skill 被触发后，Claude Code 自动调用了内置 `Workflow` 工具，生成 3 个子代理并行执行，全程无人机交互。结果连续 FAILED。

## 触发链路

```
用户: "开发流程怎么没走"
  → Claude Code: 找到 gate-1-grill skill
    → 调 Skill("gate-1-grill")
      → Skill 返回: "Invoke: Workflow({ name: 'gate-1-grill' })"
        → Claude Code: 调 Workflow({ name: 'gate-1-grill' })
          → 生成 3 个子代理并行跑
            → 子代理无法与用户对话 → FAILED
```

## 两个关键问题

### 问题 1: 指令模糊导致工具误用

Skill 返回的指令：

```
Invoke: Workflow({ name: "gate-1-grill" })
```

Claude Code 将 `Workflow` 理解为**内置多代理编排工具**（用于生成子代理并行执行自动化任务）。

但 Gate 1 的本质是**需求对齐**——需要跟用户反复对话、烤问、确认。子代理无法与用户交互，只能对着空气跑，必然失败。

**可能的预期行为**：`Workflow` 在这里可能指项目级的概念流程（如 `/workflows` 命令），而非 Claude Code 的内置 `Workflow` 工具。指令格式刚好同名，造成歧义。

### 问题 2: 缺少"任务→工具适配性"判断

Claude Code 看到 `Workflow({ name: ... })` 就机械执行，没有判断：
- 这个任务是否适合自动化代理执行？
- 是否需要人机对话？
- 是否应该换成直接与用户交互的方式？

Gate 1 (grill-me / 需求对齐) 需要人类用户参与决策，不属于可自动化任务。

## 额外发现

子代理运行时工作目录为 `/home/www/.agentlobby/lobby-manager/projects/student-problem-bank`（不存在），而非实际项目目录 `/home/www/cuotiben`。路径解析也存在偏差。

## 建议

1. **Skill 指令格式优化**：区分「调内置 Workflow 工具」和「走项目流程」两种语义，避免同名歧义
   - 例：内置工具用 `Workflow({ name: ... })`，项目流程用 `RunPhase: gate-1-grill` 或 `@workflow gate-1-grill`
2. **增加适配性检查**：Claude Code 执行 Workflow 前应判断：该 gate 是否适合自动化？是否需要用户交互？
   - Gate 1 (需求对齐) → 不适合自动化，应直接与用户对话
   - Gate 3 (拆 Issue) → 适合自动化子代理
   - Gate 4 (代码审查) → 适合自动化子代理
3. **路径上下文传递**：子代理应继承正确的项目工作目录，而非默认 session 目录
