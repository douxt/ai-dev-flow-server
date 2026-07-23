---
name: gate-1-grill
description: Gate 1 — 需求对齐，调用 /grill-me 全方位拷问
---

# Gate 1: 需求对齐

**全程与用户交互，不 spawn 子代理。**

## 执行

1. 调用 gate-preflight 检查进度
2. Read ~/.claude/gate-checklists/gate-1-grill.md，按步骤交互执行
3. 每步等待用户确认后才继续
