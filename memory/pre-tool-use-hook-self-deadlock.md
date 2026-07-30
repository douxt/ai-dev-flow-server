---
name: pre-tool-use-hook-self-deadlock
description: PreToolUse 钩子拦截文件写入时，若自身状态文件也需写操作则会死锁
metadata: 
  node_type: memory
  type: project
  originSessionId: 7261588a-bc50-4125-85bb-ef05900cfb6c
---

**场景**：设计 workflow-gate PreToolUse hook，在 Edit/Write 前拦截检查 `.workflow-route` 是否存在。但该文件本身也需要通过工具写入 → 鸡生蛋，hook 永远不会让文件写成功。

**根因**：guard 机制的写依赖恰好落在自己拦截的通道上，形成递归死锁。

**解决**：hook 自己写状态文件（`fs.writeFileSync` 直写，不走 Edit/Write 工具），同时对该文件路径做豁免——检测到是自身的文件操作则放行。

**预防**：设计任何 PreToolUse 拦截时，先检查拦截代码本身是否需要写状态。需要 → 自写 + 路径豁免，不走被拦截的工具通道。

**Why:** guard 机制自我引用是 hook 开发中的结构性陷阱。
**How to apply:** 所有 PreToolUse hook 开发 checklist 第一项：检查自身状态文件写入路径。
