#!/bin/bash
# block-git-worktree.sh — 拦截 git worktree add/remove，强制使用 wt 工具
# matcher: Bash，排在 bash-firewall 之后
set -euo pipefail

INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || true)
[ -z "$CMD" ] && exit 0

case "$CMD" in
  *"git worktree add"*|*"git worktree remove"*|*"git worktree prune"*)
    >&2 echo ""
    >&2 echo "╔══════════════════════════════════════════════════════╗"
    >&2 echo "║  禁止直接使用 git worktree 命令                       ║"
    >&2 echo "║  请统一使用 wt 工具管理 worktree：                     ║"
    >&2 echo "║                                                      ║"
    >&2 echo "║  git worktree add    →  wt create <任务名>             ║"
    >&2 echo "║  git worktree remove →  wt cleanup <任务名>            ║"
    >&2 echo "║                                                      ║"
    >&2 echo "║  无 wt 环境时，手动创建 worktree 后仍需走 wt commit     ║"
    >&2 echo "╚══════════════════════════════════════════════════════╝"
    exit 2
    ;;
esac
exit 0
