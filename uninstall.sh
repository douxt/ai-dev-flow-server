#!/bin/bash
# uninstall.sh — 从目标项目移除 ai-dev-flow-server
# 用法: bash uninstall.sh <项目路径>
set -euo pipefail

TARGET="${1:-}"
if [ -z "$TARGET" ]; then
    echo "❌ 需要指定目标项目路径"; echo "用法: bash uninstall.sh <项目路径>"; exit 1
fi

TARGET=$(realpath "$TARGET" 2>/dev/null || echo "$TARGET")
PROJECT=$(basename "$TARGET")

echo "⚠️  将从 $TARGET 移除 ai-dev-flow-server"
echo "   项目: $PROJECT"
echo ""
read -rp "确认继续？(y/N) " CONFIRM
[ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ] && echo "已取消" && exit 0

echo ""
echo "── 用户段清理 ──"

# 1. 移除 gate 脚本
echo "1. 移除 gate 脚本..."
rm -f "$HOME/.claude/workflows/gate-1-grill.js"
rm -f "$HOME/.claude/workflows/gate-2-prd.js"
rm -f "$HOME/.claude/workflows/gate-3-issues.js"
rm -f "$HOME/.claude/workflows/gate-4-review.js"
rm -f "$HOME/.claude/workflows/gate-5-prep.js"
rm -f "$HOME/.claude/workflows/gate-6-afk.js"
echo "  ✅ gate 脚本已移除"

# 2. 移除 .devflow/
echo "2. 移除 .devflow/ 目录..."
if [ -d "$TARGET/.devflow" ]; then
    rm -rf "$TARGET/.devflow"
    echo "  ✅ .devflow/ 已删除"
else
    echo "  ⚠️  .devflow/ 不存在"
fi

# 3. 移除 .gate-state
echo "3. 移除 .gate-state..."
if [ -f "$TARGET/.gate-state" ]; then
    rm -f "$TARGET/.gate-state"
    echo "  ✅ .gate-state 已删除"
else
    echo "  ⚠️  .gate-state 不存在"
fi

# 4. 从 CLAUDE.md 中移除 ai-dev-flow-server 片段
echo "4. 清理 CLAUDE.md..."
for md in "$TARGET/.claude/CLAUDE.md" "$TARGET/CLAUDE.md"; do
    if [ -f "$md" ] && grep -q "ai-dev-flow-server" "$md" 2>/dev/null; then
        # 删除从 <!-- ⚠️ 以下由 ai-dev-flow-server 到 <!-- ai-dev-flow-server end --> 的块
        sed -i '/<!-- ⚠️ 以下由 ai-dev-flow-server/,/<!-- ai-dev-flow-server end -->/d' "$md"
        echo "  ✅ $md 已清理"
    fi
done

echo ""
echo "── root 段（请以 root 身份执行）──"
echo ""
echo "# 停止并移除 timer"
echo "systemctl stop dispatch-${PROJECT}.timer reconcile-${PROJECT}.timer 2>/dev/null || true"
echo "systemctl disable dispatch-${PROJECT}.timer reconcile-${PROJECT}.timer 2>/dev/null || true"
echo "rm -f /etc/systemd/system/dispatch-${PROJECT}.service /etc/systemd/system/dispatch-${PROJECT}.timer"
echo "rm -f /etc/systemd/system/reconcile-${PROJECT}.service /etc/systemd/system/reconcile-${PROJECT}.timer"
echo "systemctl daemon-reload"
echo ""
echo "══════════════════════════════════════"
echo "用户段清理完成。执行 root 段后彻底移除。"
echo "══════════════════════════════════════"
