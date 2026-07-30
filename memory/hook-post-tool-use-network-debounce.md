---
name: hook-post-tool-use-network-debounce
description: PostToolUse hook 的 5 秒预算约束——网络操作不能同步推，需三阶防抖
metadata: 
  node_type: memory
  created: 2026-07-29
  source: offline-scan
  origin_session: dfa6089a-1cfa-410b-b935-2f9ca706fa7f
  originSessionId: bfe4aa51-46f4-4abd-af2f-ba6f8cd145b1
---

**根因**：PostToolUse hook 在工具调用后注入，被 Harness 期望约 5 秒内返回。如果钩子做 git push、API 调用等网络操作，超时后 hook 返回但不保证执行完毕，而且可能被 Harness 认为"挂起"而触发告警。推远程在 WSL 下尤其不可控（Gitee/GitHub 都可能被墙）。

**解决**：三阶防抖架构——
1. 写时层（mem-backup）：PostToolUse 内只做本地 commit（毫秒级），检查 `.last-push` 戳距上次 >20 分钟 → `nohup` 后台异步推（不阻塞 hook）
2. 会话启动层（mem-session-start）：每次开会话补推积压（兜住写时层因断网/休眠未推的 commit）
3. 全量层（mem-scan）：每日懒触发扫描末尾全量双推
三层暴露窗口从 24h+ 收到分钟级，且全部后台化不拖交互。

**预防**：任何需要在 PostToolUse hook 中触发的远程操作，都采用"本地先做 + 防抖异步推送 + 后续环节兜底"的约定，不在 hook 内同步等网络。hooks 开发的通用模式：先区分同步必做（快/安全）和异步可缓（慢/不可靠），后者给防抖+兜底。

另见 [[post-tool-use-cannot-detect-skill-boundary]] — PostToolUse 的另一维度限制（颗粒度 = 单次工具调用，非 skill 级别）。

