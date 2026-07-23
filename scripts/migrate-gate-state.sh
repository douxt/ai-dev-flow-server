#!/bin/bash
# migrate-gate-state.sh — v2.1 .gate-state (9 Gate) → v3.0 .devflow/stage (5 阶段)
# 由 install.sh --update 自动调用
set -euo pipefail

PROJECT_DIR="${1:-$(pwd)}"
OLD_GATE="$PROJECT_DIR/.gate-state"
NEW_STAGE="$PROJECT_DIR/.devflow/stage"
BACKUP="$PROJECT_DIR/.gate-state.v2.bak"

# 无旧文件 → 跳过
[ -f "$OLD_GATE" ] || exit 0

echo "📋 检测到 v2.1 gate-state → 迁移到 v3.0 stage"

# 备份
cp "$OLD_GATE" "$BACKUP"
echo "   备份: $BACKUP"

# 9 Gate → 5 阶段映射
declare -A GATE_TO_STAGE=(
    ["gate-1"]="explore"
    ["gate-2"]="spec"
    ["gate-3"]="tickets"
    ["gate-4"]="tickets"
    ["gate-5"]="implement"
    ["gate-6"]="implement"
)

# 读取旧状态
last_passed=""
while IFS= read -r line; do
    for gate in gate-1 gate-2 gate-3 gate-4 gate-5 gate-6; do
        if echo "$line" | grep -q "$gate:.*passed"; then
            last_passed="${GATE_TO_STAGE[$gate]}"
        fi
    done
done < "$OLD_GATE"

# Gate 7（审查合并）和 Gate 8（复盘）无 workflow 脚本，不在此表中
# 如果 gate-6 通过了 → 映射到 implement 阶段

# 写入新阶段文件
mkdir -p "$(dirname "$NEW_STAGE")"
if [ -n "$last_passed" ]; then
    echo "${last_passed}:done" > "$NEW_STAGE"
    echo "   迁移完成: 最新通过阶段 → ${last_passed}:done"
else
    echo "explore:done" > "$NEW_STAGE"
    echo "   迁移完成: 无历史记录 → explore:done（默认起点）"
fi

# 追加 trace
TRACE_FILE="$PROJECT_DIR/.devflow/trace.jsonl"
mkdir -p "$(dirname "$TRACE_FILE")" 2>/dev/null || true
echo "{\"event\":\"migration.v2_to_v3\",\"ts\":\"$(date -Iseconds)\",\"from\":\"gate-state\",\"to\":\"stage\",\"backup\":\"$BACKUP\",\"result\":\"${last_passed:-explore}:done\"}" >> "$TRACE_FILE" 2>/dev/null || true

echo "✅ 迁移完成（旧文件保留在 $BACKUP，可安全删除）"
