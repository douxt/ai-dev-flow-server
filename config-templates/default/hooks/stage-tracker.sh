#!/bin/bash
# stage-tracker.sh — PostToolUse hook：产物检测 + 阶段追踪
# 检测关键产物文件，自动更新 .devflow/stage 状态
# 阶段约束为 advisory 警告，不硬拦截

set -euo pipefail

TOOL_NAME="$1"
TOOL_INPUT="$2"
WORKSPACE="${WORKSPACE:-$(pwd)}"
STAGE_FILE="$WORKSPACE/.devflow/stage"
TRACE_SCRIPT="$WORKSPACE/.devflow/scripts/trace.sh"

trace() { bash "$TRACE_SCRIPT" "$@" 2>/dev/null || true; }

# 仅在工作区有 .devflow/ 的项目中生效
[ -d "$WORKSPACE/.devflow" ] || exit 0

# 阶段检测：基于产物而非 skill 调用
detected_stage=""

# 检测 spec.md
if [ -f "$WORKSPACE/spec.md" ] && [ -s "$WORKSPACE/spec.md" ]; then
    detected_stage="spec:done"
fi

# 检测 issues/ 下是否有新文件（比 tickets 阶段更可靠）
if [ -d "$WORKSPACE/issues" ]; then
    issue_count=$(find "$WORKSPACE/issues" -maxdepth 1 -name "*.md" -type f 2>/dev/null | wc -l)
    if [ "$issue_count" -gt 0 ]; then
        detected_stage="tickets:done"
    fi
fi

# 检测 PR 是否已创建
if git -C "$WORKSPACE" log --oneline -1 2>/dev/null | grep -qiE "Merge pull request|\(#\d+\)"; then
    detected_stage="implement:done"
fi

# 无检测到任何阶段更新 → 跳过
[ -z "$detected_stage" ] && exit 0

# 读取上次记录
previous_stage=""
[ -f "$STAGE_FILE" ] && previous_stage=$(cat "$STAGE_FILE" 2>/dev/null || echo "")

# 无变化 → 跳过
[ "$detected_stage" = "$previous_stage" ] && exit 0

# 阶段顺序校验（仅在状态变化时做 advisory 警告）
stage_order="explore:done spec:done tickets:done implement:done done"
current_index=0
prev_index=0
i=1
for s in $stage_order; do
    [ "$s" = "$detected_stage" ] && current_index=$i
    [ "$s" = "$previous_stage" ] && prev_index=$i
    i=$((i + 1))
done

# 写入新阶段
echo "$detected_stage" > "$STAGE_FILE"
trace "stage.transition" from="$previous_stage" to="$detected_stage"

# 阶段跳跃 → advisory 警告
if [ "$current_index" -gt 0 ] && [ "$prev_index" -gt 0 ] && [ "$current_index" -gt "$((prev_index + 1))" ]; then
    trace "stage.skip" from="$previous_stage" to="$detected_stage" skipped="$((current_index - prev_index - 1))"
    cat >&2 <<EOF

⚠️  stage-tracker: 检测到阶段跳跃
   上一阶段: $previous_stage
   当前检测: $detected_stage
   建议: 确认中间阶段产物是否存在，缺失可能影响后续质量

EOF
    exit 0  # advisory — 不硬拦截
fi

# 正常推进
exit 0
