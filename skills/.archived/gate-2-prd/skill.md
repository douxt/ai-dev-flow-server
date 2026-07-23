---
name: gate-2-prd
description: Gate 2 — 产出 PRD，调用 /to-prd + 9 项出口检查
---

# Gate 2: 产出 PRD

**全程与用户交互，不 spawn 子代理。**

## 执行

1. 调用 gate-preflight 检查进度
2. Read ~/.claude/gate-checklists/gate-2-prd.md，按步骤交互执行
3. 每步等待用户确认后才继续
