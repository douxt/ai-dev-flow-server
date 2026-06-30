#!/bin/bash
# sync-skills.sh — 从 ~/.claude/skills/ 重新同步 skills-cache/
# 用法: cd skills-cache/ && bash sync-skills.sh
set -euo pipefail

SKILLS_DIR="${SKILLS_DIR:-$HOME/.claude/skills}"
[ -d "$SKILLS_DIR" ] || { echo "❌ $SKILLS_DIR 不存在"; exit 1; }

SKILLS=(caveman diagnose grill-me grill-with-docs handoff
  improve-codebase-architecture prototype review-cc-cli
  setup-matt-pocock-skills tdd to-issues to-prd triage
  write-a-skill zoom-out)

for s in "${SKILLS[@]}"; do
  if [ -d "$SKILLS_DIR/$s" ]; then
    rm -rf "./$s"
    cp -rL "$SKILLS_DIR/$s" "./$s"
    echo "  ✅ $s"
  else
    echo "  ⚠️  $s 不在 $SKILLS_DIR"
  fi
done

CC_VERSION=$(claude --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "unknown")
cat > .version << EOF
{"cc_version":"$CC_VERSION","sync_date":"$(date -I)","skill_count":${#SKILLS[@]}}
EOF
echo "✅ 同步完成（CC $CC_VERSION, ${#SKILLS[@]} skills）"
