#!/bin/bash
# update.sh — 更新 .devflow/ 内容到已安装项目（保留 config.yaml 和 .gate-state）
# 用法: bash update.sh <项目路径>
set -euo pipefail

TARGET="${1:-}"
[ -z "$TARGET" ] && echo "用法: bash update.sh <项目路径>" && exit 1
TARGET=$(realpath "$TARGET" 2>/dev/null || echo "$TARGET")
SOURCE=$(cd "$(dirname "$0")" && pwd)

echo "── 更新 ai-dev-flow-server ──"
echo "  源: $SOURCE"
echo "  目标: $TARGET"

# 检查 www 是否可读
if [ ! -r "$SOURCE/archon/dispatch.sh" ]; then
    echo "❌ 源文件不可读，请以 www 用户运行: su - www -s /bin/bash"
    exit 1
fi
if [ ! -w "$TARGET/.devflow" ]; then
    echo "❌ 目标 .devflow/ 不可写"
    exit 1
fi

# 更新 archon/
echo "  archon/ ..."
cp "$SOURCE/archon/dispatch.sh" "$TARGET/.devflow/archon/"
cp "$SOURCE/archon/reconciler.sh" "$TARGET/.devflow/archon/"
cp "$SOURCE/archon/auto-execute-afk.yaml" "$TARGET/.devflow/archon/"
chmod +x "$TARGET/.devflow/archon/dispatch.sh" "$TARGET/.devflow/archon/reconciler.sh"

# 更新 scripts/
echo "  scripts/ ..."
cp "$SOURCE/scripts/"*.py "$TARGET/.devflow/scripts/"
chmod +x "$TARGET/.devflow/scripts/"*.py

# 更新 knowledge/
echo "  knowledge/ ..."
cp "$SOURCE/knowledge/"*.md "$TARGET/.devflow/knowledge/"

# 更新 workflows（到 www 用户的 CC 目录）
echo "  workflows/ ..."
cp "$SOURCE/workflows/"*.js "$HOME/.claude/workflows/"

echo "✅ 更新完成（config.yaml 和 .gate-state 不受影响）"
echo "  如需重启 timer: systemctl restart dispatch-$(basename "$TARGET").timer reconcile-$(basename "$TARGET").timer"
