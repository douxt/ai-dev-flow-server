#!/bin/bash
# file-guard.sh — 拦截非 worktree 路径的 Edit/Write
# 由 ai-dev-flow-server install.sh 部署到 ~/.claude/hooks/

FILE="$1"
WORKSPACE="${WORKSPACE:-$(pwd)}"

# 允许 ~/.claude/ 下的配置写入
case "$FILE" in
    "$HOME/.claude/"*) exit 0 ;;
    "$HOME/.config/claude/"*) exit 0 ;;
esac

# 检查是否在 worktree 内
GIT_DIR=$(git -C "$WORKSPACE" rev-parse --git-dir 2>/dev/null || true)
if [ -n "$GIT_DIR" ]; then
    if echo "$GIT_DIR" | grep -q "worktrees"; then
        exit 0  # 在 worktree 内，允许
    fi
fi

# 检查目标路径是否在 worktree 内
case "$FILE" in
    *".claude/worktrees/"*) exit 0 ;;
esac

echo "⛔ file-guard: 禁止在主仓库目录下直接编辑文件"
echo "   请先创建 worktree: git worktree add .claude/worktrees/<name> -b feat/<name>"
exit 1
