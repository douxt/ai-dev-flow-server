---
name: gate-3-issues
description: Gate 3 — 拆解 Issue，调用 /to-issues + 16 项出口检查
---

# Gate 3: 拆解 Issue

**全程与用户交互，不 spawn 子代理。**

## 执行

1. 调用 gate-preflight 检查进度
2. Read ~/.claude/gate-checklists/gate-3-issues.md，按步骤交互执行
3. 每步等待用户确认后才继续
