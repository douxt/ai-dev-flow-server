#!/bin/bash
set -e

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VERSION_FILE="$HOME/.claude/.review-cc-cli-version"
FORCE=false

case "${1:-}" in
  --force|-f) FORCE=true ;;
  --help|-h)
    echo "用法: bash scripts/install.sh [--force]"
    echo ""
    echo "部署 settings-review.json + rubrics 到 ~/.claude/"
    echo ""
    echo "  --force  强制覆盖，即使目标是 symlink"
    echo "  --help   显示此帮助"
    echo ""
    echo "部署后，可通过 npx skills update review-cc-cli 更新 SKILL.md，"
    echo "然后重新运行本脚本同步配置。"
    exit 0
    ;;
esac

# ── 版本追踪 ──
if git -C "$SKILL_DIR" rev-parse --git-dir &>/dev/null; then
  VERSION=$(git -C "$SKILL_DIR" rev-parse --short HEAD)
else
  VERSION=$(date -r "$SKILL_DIR/SKILL.md" +%Y%m%d-%H%M%S 2>/dev/null || echo "unknown")
fi

if [ -f "$VERSION_FILE" ]; then
  OLD_VERSION=$(cat "$VERSION_FILE")
  if [ "$OLD_VERSION" = "$VERSION" ]; then
    echo "==> 配置已是最新（$VERSION），跳过"
    exit 0
  fi
  echo "==> 检测到版本更新：$OLD_VERSION → $VERSION"
fi

# ── settings-review.json ──
echo "==> Deploying settings-review.json..."
mkdir -p "$HOME/.claude"

TARGET="$HOME/.claude/settings-review.json"
if [ -L "$TARGET" ] && [ "$FORCE" != "true" ]; then
  SYMLINK_TARGET=$(readlink "$TARGET")
  echo "   ⚠️  $TARGET 是 symlink → $SYMLINK_TARGET"
  echo "   symlink 部署需手动管理，跳过。使用 --force 强制覆盖。"
elif [ "$FORCE" = "true" ] || [ ! -e "$TARGET" ]; then
  cp "$SKILL_DIR/config/settings-review.json" "$TARGET"
  echo "   ✅ settings-review.json"
else
  cp "$SKILL_DIR/config/settings-review.json" "$TARGET"
  echo "   ✅ settings-review.json"
fi

# ── rubrics ──
echo "==> Deploying rubrics..."
mkdir -p "$HOME/.claude/review-rubrics"

SKIPPED_RUBRICS=0
for src in "$SKILL_DIR/rubrics/"*.md; do
  name=$(basename "$src")
  dest="$HOME/.claude/review-rubrics/$name"
  if [ -L "$dest" ] && [ "$FORCE" != "true" ]; then
    ((SKIPPED_RUBRICS++)) || true
    continue
  fi
  cp "$src" "$dest"
done

if [ "$SKIPPED_RUBRICS" -gt 0 ]; then
  echo "   ⚠️  $SKIPPED_RUBRICS 个 rubric 是 symlink，已跳过。使用 --force 强制覆盖。"
fi
echo "   ✅ rubrics/"

# ── 写版本文件 ──
echo "$VERSION" > "$VERSION_FILE"

echo ""
echo "✅ review-cc-cli 配置部署完成（$VERSION）"
echo "   在 Claude Code 中执行 /review-cc-cli 即可使用。"
echo "   更新 skill 后（npx skills update review-cc-cli）请重新运行本脚本。"
