#!/bin/bash
# file-guard.sh — 拦截非 worktree 路径的 Edit/Write + 安全配置自保护
# 由 ai-dev-flow-server install.sh 部署到 ~/.claude/hooks/
#
# Claude Code hook 协议：JSON 走 stdin（PreToolUse）。位置参数 $1 仅保留给手动测试。
# 退出码：exit 2 = 阻断并把 stderr 注入给模型；exit 0/1 不阻断。

FILE=""
WORKSPACE="${WORKSPACE:-$(pwd)}"

if [ $# -ge 1 ] && [ -n "${1:-}" ]; then
    FILE="$1"
else
    _STDIN=$(cat)
    command -v jq >/dev/null 2>&1 || exit 0   # jq 缺失 → 降级放行，不锁死会话
    FILE=$(printf '%s' "$_STDIN" | jq -r '(.tool_input // {}).file_path // empty')
    _CWD=$(printf '%s' "$_STDIN" | jq -r '.cwd // empty')
    [ -n "$_CWD" ] && WORKSPACE="$_CWD"
fi

[ -z "$FILE" ] && exit 0

# ── 安全配置自保护（必须先于豁免，否则豁免 $HOME/.claude/* 把保护吞掉）──
case "$FILE" in
    "$HOME/.claude/settings.json"|\
    "$HOME/.claude/settings.local.json"|\
    "$HOME/.claude/hooks/"*|\
    "$HOME/.git-hooks/"*)
        echo "⛔ file-guard: settings.json / hooks/ / .git-hooks/ 属安全基础设施，禁止直接修改" >&2
        echo "   需变更请明确申请授权后经用户操作（模板源在仓库 config-templates/）" >&2
        exit 2 ;;
esac

# 允许 ~/.claude/ 下的其他配置写入
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

echo "⛔ file-guard: 禁止在主仓库目录下直接编辑文件" >&2
echo "   请先创建 worktree: git worktree add .claude/worktrees/<name> -b feat/<name>" >&2
exit 2
