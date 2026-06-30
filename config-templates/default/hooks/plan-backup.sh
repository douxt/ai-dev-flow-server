#!/bin/bash
# plan-backup.sh — PostToolUse 钩子，Edit/Write 计划文件时自动 git 备份
# 所有 git 操作为 best-effort：备份失败不影响主流程，错误静默跳过
# BYPASS_WT_CHECK=1 仅豁免备份仓库（非 worktree 目录）的 commit 拦截
set -euo pipefail

# 先提取路径再决定是否继续（非 plan 文件免去后续 IO）
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""' 2>/dev/null || true)
[ -z "$FILE" ] && exit 0

case "$FILE" in
  $HOME/.claude/plans/*.md) ;;
  *) exit 0 ;;
esac

BACKUP_DIR="$HOME/.claude/plans/.git-backup"
mkdir -p "$BACKUP_DIR"

if [ ! -d "$BACKUP_DIR/.git" ]; then
  git -C "$BACKUP_DIR" init --quiet
  git -C "$BACKUP_DIR" config user.name "Claude Plan Backup"
  git -C "$BACKUP_DIR" config user.email "noreply@local"
fi

# 定点添加（非 git add .），防并发竞争 + 安全面收窄 + O(1) 性能
cp "$FILE" "$BACKUP_DIR/$(basename "$FILE")" 2>/dev/null || true
git -C "$BACKUP_DIR" add "$(basename "$FILE")" 2>/dev/null
BYPASS_WT_CHECK=1 git -C "$BACKUP_DIR" commit -m "$(date -Iseconds) — $(basename "$FILE")" 2>/dev/null || true

# 软上限：超 500 个 commit 后 squash 为单 commit + 后续增量
COMMIT_COUNT=$(git -C "$BACKUP_DIR" rev-list --count HEAD 2>/dev/null || echo 0)
if [ "$COMMIT_COUNT" -gt 500 ]; then
  git -C "$BACKUP_DIR" checkout --orphan squash 2>/dev/null || true
  BYPASS_WT_CHECK=1 git -C "$BACKUP_DIR" commit -m "squash: $(date -Iseconds) — 达到 500 上限自动压缩" 2>/dev/null || true
fi

exit 0
