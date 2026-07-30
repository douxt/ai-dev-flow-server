---
name: post-tool-use-cannot-detect-skill-boundary
description: "PostToolUse 在每个工具调用后触发，无法感知\"技能（skill）整体完成\""
metadata: 
  node_type: memory
  type: project
  originSessionId: 7261588a-bc50-4125-85bb-ef05900cfb6c
---

**场景**：试图用 PostToolUse hook 检测 `/to-spec` skill 何时整体完成，以便推进状态机。

**根因**：PostToolUse 的触发粒度是**单个工具调用**（每 Write/Edit/Read 一次就触发一次），不是 skill 级别。无法区分"skill 内的某个 Write"和"skill 已完成"。

**解决**：改用**产物文件检测**。hook 检查约定文件（如 `docs/spec/*.md`）的存在性和时间戳变化，而不是检测 skill 名称或调用边界。结合时间戳判断"有新产物"→ 推进阶段。

**预防**：在 Claude Code hook 架构中，任何"聚合级别推理"（检测流程阶段、判断任务完成）都用文件产物+时间戳做信号，不要依赖工具调用上下文。

**Why:** PostToolUse 无法跨越工具调用聚合为 skill 语义，hook 设计必须降级到文件系统信号。
**How to apply:** 所有 DevFlow 状态推进 hook 统一改用药产物文件检测模式。

另见 [[hook-post-tool-use-network-debounce]] — PostToolUse 的另一维度限制（~5s 预算，网络同步操作不可行）。
