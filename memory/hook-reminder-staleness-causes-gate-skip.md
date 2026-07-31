---
name: hook-reminder-staleness-causes-gate-skip
description: stage-tracker/workflow-gate 提醒内容过期导致新增门禁不被执行——hook 是 AI 看到门禁的唯一入口，提醒编号必须与 checklist 同步
created: 2026-07-31
source: manual
metadata:
  type: project
  related:
    - gate-two-axis-architecture
    - devflow-v3-evolution-lessons
  reference: "config-templates/default/hooks/stage-tracker.sh, config-templates/default/hooks/workflow-gate.sh"
---

# Hook 提醒过期导致质量门禁不被执行

## 根因

门禁体系的约束链路是：

```
workflow-gate（首次拦截）→ stage-tracker（阶段切换提醒）→ AI 按提醒执行 → checklist
```

AI 在每个阶段切换时看到 hook 输出的提醒文本，按提醒中列出的门禁编号去查 checklist。如果提醒内容过期（编号是旧的），AI 自然不会执行新增的门禁。

具体案例：
- `spec:done` 提醒写"S1-S10"→ S11/S12/S13 被跳过
- `tickets:done` 提醒写"C0 + C1-C5"→ C7 被跳过
- `tdd:done` 提醒写"C0 + C1-C5"→ C7/G0 被跳过
- 三个提醒都没提决策树（knowledge/10）→ 分层选择不走决策树

## 后果

UMES3 v3.2 管线从未端到端走通——checklist 文件本身完整，但 AI 按提醒只执行了部分门禁。

## 解决

`stage-tracker.sh` 三处提醒全部补全：
- `spec:done`: S1-S10→S1-S13 + 决策树引用 + S11/S13 重点提示
- `tickets:done`: 加决策树入口段 + 3→4条grep + C0+C1-C5→C0+C1-C5+C7 + R7/C7 检查项
- `tdd:done`: 加 G0 完整四步流程 + R7 分层一致性 + C0+C1-C5→C0+C1-C5+C7+G0

`workflow-gate.sh` 注入文本同步更新：S1-S10→S1-S13 + 决策树 + C7/G0。

## 预防

- 每次新增门禁检查项时，同步检查 3 处 hook 提醒是否覆盖（spec:done / tickets:done / tdd:done）
- checklist 编号变更时，grep hook 文件确认引用是否同步
- 在 spec-checklist 的 review 路由表中加一条：确认 hook 提醒与实际通过条件一致
