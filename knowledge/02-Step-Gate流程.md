# Step-Gate 开发流程规范 v3.0

> 基于 Matt Pocock v1.1 五命令体系 + DevFlow 基础设施约束。
> 9 Gate → 5 阶段，简化流程同时保留机器硬约束。

## 流程总图

```
                        ┌─────────────────┐
                        │  阶段 1: explore  │
                        │  Plan Mode 初稿   │  或跳过（有现有文档）
                        │  /grill-with-docs │  或跳过（需求已明确）
                        └────────┬────────┘
                                 │
                        ┌────────v────────┐
                        │  阶段 2: spec    │  /to-spec → spec.md
                        │  产出规格        │  含验证方案 + Ponytail 四问
                        └────────┬────────┘
                                 │
                        ┌────────v────────┐
                        │  阶段 3: tickets │  /to-tickets → issues/*.md
                        │  拆分工单        │  每 ticket ≤ 上下文窗口 40%
                        └────────┬────────┘
                                 │
                        ┌────────v────────┐
                        │  阶段 4: implement│  /implement → 代码+审查
                        │  实现 + 内建审查  │  /code-review → diff 审查
                        └────────┬────────┘
                                 │
                        ┌────────v────────┐
                        │  阶段 5: done    │  PR 合入 + 复盘
                        │  合并 + 复盘     │  自动提取教训 → CLAUDE.md
                        └─────────────────┘
```

## 阶段与 Skill 对照

| 阶段 | v3.0 Skill | 产出 | 基础设施约束 |
|------|-----------|------|-------------|
| explore | Plan Mode → /grill-with-docs | 需求理解/初稿 | workflow-gate hook 拦截（未评估不许写代码） |
| spec | /to-spec | spec.md（含验证方案） | stage-tracker hook 检测 spec.md → spec:done |
| tickets | /to-tickets | issues/*.md | check_constitution.py 自动检查 + 安全红线标记 |
| implement | /implement → /code-review | PR | stage-tracker 检测 PR → implement:done |
| done | — | 合入 + 教训 | 复盘半自动 → CLAUDE.md # Lessons |

## 流转规则

### 正向

5 阶段顺序依赖，前序阶段未完成（产出文件不存在），`stage-tracker` hook 输出 advisory 警告，不硬拦截。

**硬拦截仅在入口**：`workflow-gate` PreToolUse hook — agent 首次尝试 Edit/Write/Bash(修改类) 前，未完成工作流评估 → 拦截。

### 回退

| 触发条件 | 回退目标 | 操作 |
|---------|:------:|------|
| /grill-with-docs 发现需求理解偏差 | explore | 更新初稿/对齐上下文 |
| /to-tickets 检查不通过 | spec | 修正规格 |
| /code-review 审查不通过 | implement | 创建新 ticket → 重新 /implement |
| 复盘发现问题 | 对应阶段 | 视问题归属回退 |

### Ticket 状态机

```
backlog → ready → in_progress → done
```

| 状态 | 含义 | 谁操作 |
|------|------|:------:|
| `backlog` | 阻塞未解除 | 人 |
| `ready` | 可被 dispatch 抢占 | 人（通过宪法检查后） |
| `in_progress` | dispatch 正在消化 | dispatch.sh |
| `done` | 完成，PR 已合并 | 人 |

## 上下文预算

/to-tickets 拆分时，每个 ticket 内容不超过上下文窗口的 40%（~48K token），确保 agent 在智能区内工作。

## 角色与工具

| 环节 | 执行者 | 工具 | 产出 |
|------|:------:|------|------|
| 需求澄清 | 人+CC | Plan Mode + /grill-with-docs | 需求理解/初稿 |
| 规格 | 人+CC | /to-spec | spec.md |
| 拆工单 | 人+CC | /to-tickets | issues/*.md |
| 自动检查 | 机器 | check_constitution.py | 通过/不通过 + 安全红线标记 |
| 实现 | CC | /implement（内建 Maker-Checker） | 代码+测试 |
| 审查 | CC 子代理 | /code-review | review 报告 |
| AFK 自动执行 | dispatch.sh + Archon | auto-execute-afk.yaml | 代码+测试+PR |
| 终审 | 人 | PR review | PR 合入 |
| 复盘 | 人+CC | 扫描 PR review 意见 | CLAUDE.md 规则建议 |

## 附录 — 规范文件索引

| 文件 | 内容 | 引用于 |
|:----|------|:------:|
| `.devflow/knowledge/01-核心方法论.md` | AI 辅助编程方法论 v4.0 | explore, implement |
| `.devflow/knowledge/03-Spec质量宪法.md` | Spec 宪法（Ponytail + 三假设 + 验证层级） | spec |
| `.devflow/knowledge/04-Ticket质量宪法.md` | Ticket 宪法（窗口适配） | tickets |
| `.devflow/knowledge/05-脚本质量宪法.md` | 脚本宪法 12 项 | 保留 |
| `.devflow/knowledge/06-AFK脚本栈规范.md` | 服务器 AFK 管线规范 | implement |
| `.devflow/knowledge/07-Agent防护体系.md` | Agent 约束最佳实践 | 全局 |
| `.devflow/knowledge/08-安全红线宪法.md` | 安全红线 5 类 | tickets, implement |
