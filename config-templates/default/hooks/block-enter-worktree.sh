#!/bin/bash
# block-enter-worktree.sh — 拦截自动 EnterWorktree，强制人工手动创建
# 由 ai-dev-flow-server install.sh 部署到 ~/.claude/hooks/

# 允许人工显式调用 EnterWorktree（带 name 或 path 参数）
# PreToolUse hook 在 tool call 前触发，无法直接读取参数
# 此 hook 仅作审计记录，实际拦截由 settings.json 的 deny 规则完成
echo "[block-enter-worktree] $(date -Iseconds) — EnterWorktree called" >> "$HOME/.claude/logs/enter-worktree.log"
exit 0
