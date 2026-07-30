---
name: matt-pocock-skill-routing-hierarchy
description: Matt Pocock v1.1 五个命令的正确路由层次——wayfinder 仅用于多会话大任务，grill-with-docs 需先有文档
metadata: 
  node_type: memory
  type: project
  originSessionId: 7261588a-bc50-4125-85bb-ef05900cfb6c
---

**场景**：设计 DevFlow 自动路由时，初始方案把 `/wayfinder` 设为多数任务的入口，被用户纠正。

**纠正链**：
1. 用户："单会话可完成，则要排除 wayfinder，有雾的话尽量用 grill-with-docs" → wayfinder 只用于 ~5% 多会话大任务，/grill-with-docs 才是 ~35% 标准路径的入口
2. 用户："grill-with-docs 的前提是先要有 doc" → 无现有文档时先进 Plan Mode 出初稿，再调 grill-with-docs

**最终路由层次**：
```
单会话？
  ├── 无文档 → Plan Mode 出初稿
  │   ├── 有雾 → /grill-with-docs → /to-spec → ...
  │   └── 无雾 → 直接 /to-spec → ...
  ├── 有文档 → /grill-with-docs → /to-spec → ...
  └── 简单改动 → 直接 /implement
多会话（~5%）→ /wayfinder → (可选 /research) → /to-spec → ...
```

**预防**：默认/default 倾向总是过用重型工具。设计任何 skill 路由时，先按任务规模分层：
轻量→单命令、标准→对话澄清+流水线、大型→多会话决策图。

**Why:** 初始方案把重型工具当默认入口，用户纠正后明确三层路由。
**How to apply:** DevFlow 自动路由按此层次设计，gate-6 派发前先判断任务规模。
