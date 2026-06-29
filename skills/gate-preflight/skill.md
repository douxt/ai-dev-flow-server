---
name: gate-preflight
description: >
  Gate 启动前看门人。在任何 Gate 流程启动前强制检查进度、
  加载对应 checklist、确认用户交互模式。防止 Gate 被后台化。
---

# gate-preflight

在任何 Gate 流程启动前，强制做三件事：

## 1. 确认 Gate 进度

Read `.gate-state`，确认当前各 Gate 的状态：
- 目标 Gate 是否已 passed？→ 跳过
- 目标 Gate 是否 in_progress？→ 从断点继续
- 前序 Gate 是否全部 passed？→ 否则拒绝，告知用户先完成前序 Gate

## 2. 加载对应 Checklist

Read `~/.claude/gate-checklists/gate-N-xxx.md`（如不存在，Read 项目 `gate-checklists/` 目录下对应文件），确认步骤清单。

## 3. 告知用户交互模式

明确告知用户：
> 本 Gate 需要你逐项确认，我会等你回应后才继续下一步。
> 这不是自动脚本——我不会跳过任何需要你决策的步骤。

## 硬性规则

- 不做后台子代理
- 不自动连续执行多个步骤
- 不确定的判断询问用户，不自行决策
- 全程与用户交互
