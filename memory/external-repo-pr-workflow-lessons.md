---
name: external-repo-pr-workflow-lessons
description: 外部仓库提 PR 全流程踩坑——wt 隔离、CLA 匹配、ruff 格式化副作用、NAS 验证、patch 幂等
metadata: 
  node_type: memory
  created: 2026-07-28
  source: stop-hook
  origin_session: d45c2e4d-a6ae-493e-8747-87a3f477d892
  type: feedback
  originSessionId: d45c2e4d-a6ae-493e-8747-87a3f477d892
---

# 外部仓库 PR 全流程踩坑

**日期**: 2026-07-28
**PR**: langbot-app/LangBot #2362

## 1. wt + file-guard 对外部仓库的约束

file-guard 要求所有编辑走 wt 管理的 worktree。外部仓库（如 LangBot）需要：
- 创建 `.wtrepos` 文件（内容为该仓库路径）
- `wt -p <项目目录> create <任务名>` 创建 worktree（会自动放到 `~/wt/<项目>/<任务>/`）
- 手动 `git worktree add` 创建的 worktree 不被 file-guard 识别
- `BYPASS_WT_CHECK=1` 绕过 git commit 检查（wt commit 只支持简单操作）

## 2. CLA 签署 — commit 作者必须匹配 GitHub 账号

CLA bot 校验原理：commit author name 或 email 必须与 GitHub 账号关联。
- `gh api users/<username> --jq '.id'` 获取 GitHub 用户 ID
- GitHub noreply 邮箱格式：`<user_id>+<username>@users.noreply.github.com`（一定匹配）
- amend 后 force push + PR 评论 `recheck` 触发 CLA 重跑

## 3. ruff format 会改变代码布局

`ruff format` 将超长单行 `Image()` 调用拆成多行。如果 entrypoint patch 脚本用精确字符串匹配，ruff 格式化后的代码匹配不到旧模式。
- **预防**：patch 脚本做两层检测——① 旧模式（未修复）② `url=` 已存在（PR 版本或已 patch），两种都优雅跳过

## 4. NAS 验证 PR 代码的正确流程

- `scp` PR 文件到 NAS → `docker cp` 进容器 → 重启 → 发消息测
- 注意：entrypoint patch 与 PR 代码冲突时 patch 会报错但不阻塞启动
- `_log_gate` 输出到 `/tmp/silent_gate.log` 而非 stdout → 查 `docker exec cat /tmp/silent_gate.log`

## 5. LangBot CI 检查清单

- Ruff Lint & Format
- Unit Tests (3.11/3.12/3.13)
- Fast Integration Tests
- E2E Startup Tests
- Box Integration Tests
- Coverage Gate
- CLA Assistant

## 6. 跨平台 PR 盲改策略

- 每个 adapter 的 URL 变量在**同一行或上一行**已被用于 HTTP 下载 → 等价推导安全
- PR body 诚实标注：哪些已验证、哪些等价推导
- 维护者和社区覆盖剩余平台

## 7. 批量清理 worktree

- `git worktree list` 列清单
- 逐个检查 `git -C <path> status --short` 确认无改动
- `git worktree remove <path> --force` 批量清除
