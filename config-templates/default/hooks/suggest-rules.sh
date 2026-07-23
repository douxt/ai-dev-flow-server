#!/bin/bash
# suggest-rules.sh — PostToolUse hook：检测待处理规则建议 → 提醒用户
# 部署到 ~/.claude/hooks/，由 settings.json PostToolUse 触发
set -euo pipefail

WORKSPACE="${WORKSPACE:-$(pwd)}"
SUGGESTIONS="$WORKSPACE/.devflow/rule-suggestions.md"
STAMP_FILE="$WORKSPACE/.devflow/.last_suggestion_reminder"

[ -d "$WORKSPACE/.devflow" ] || exit 0
[ -f "$SUGGESTIONS" ] || exit 0

# 去重：30 分钟内不重复提醒
if [ -f "$STAMP_FILE" ]; then
    last=$(cat "$STAMP_FILE" 2>/dev/null || echo 0)
    now=$(date +%s)
    [ $((now - last)) -lt 1800 ] && exit 0
fi

# 统计待处理建议（以 ## 开头的未标记 done 的条目）
pending=$(grep -cE '^##\s' "$SUGGESTIONS" 2>/dev/null || echo 0)
done_count=$(grep -cE '\[x\]' "$SUGGESTIONS" 2>/dev/null || echo 0)
remaining=$((pending - done_count))

if [ "$remaining" -gt 0 ]; then
    cat >&2 <<EOF

💡 self-learn: ${remaining} 条规则建议待处理
   查看: cat .devflow/rule-suggestions.md
   操作: 逐条评审后，将采纳的追加到 CLAUDE.md # Lessons，标记 [x]

EOF
    date +%s > "$STAMP_FILE" 2>/dev/null || true
fi

exit 0
