#!/bin/bash
# bash-firewall.sh — 拦截非 worktree 路径的 Bash 写操作（重定向/sed -i/heredoc/tee/cp/mv）
# 由 ai-dev-flow-server install.sh 部署到 ~/.claude/hooks/

CMD="$1"
WORKSPACE="${WORKSPACE:-$(pwd)}"

# 允许任意路径的只读操作
case "$CMD" in
    *">"*|*">>"*|*"2>"*|*"2>>"*|*"&>"*) ;;
    *"sed -i"*|*"sed -i.bak"*) ;;
    *"tee "*|*"cp "*|*"mv "*|*"mkdir "*|*"rm "*|*"chmod "*|*"chown "*) ;;
    *) exit 0 ;;  # 纯只读命令，放行
esac

# 允许 ~/.claude/ 路径写入
case "$CMD" in
    *"$HOME/.claude/"*|*"$HOME/.config/claude/"*|*"/tmp/"*) exit 0 ;;
esac

# 允许 worktree 路径写入
case "$CMD" in
    *".claude/worktrees/"*) exit 0 ;;
esac

echo "⛔ bash-firewall: 禁止在主仓库目录下执行写操作"
echo "   命令: $CMD"
exit 1
