#!/bin/bash
# trace.sh — 追加一行 JSON 事件到 .devflow/trace.jsonl
# 用法: trace.sh <event_type> <key=value> ...
# 例: trace.sh "stage.transition" from="explore:done" to="spec:done"
set -euo pipefail

WORKSPACE="${WORKSPACE:-$(pwd)}"
TRACE_FILE="$WORKSPACE/.devflow/trace.jsonl"

[ -d "$WORKSPACE/.devflow" ] || exit 0

event_type="${1:-unknown}"
shift 2>/dev/null || true

# 构建 JSON 对象
json_parts="\"event\":\"$event_type\",\"ts\":\"$(date -Iseconds)\""

# 解析 key=value 参数
for arg in "$@"; do
    key="${arg%%=*}"
    val="${arg#*=}"
    # JSON 转义：反斜杠 + 双引号
    val="${val//\\/\\\\}"
    val="${val//\"/\\\"}"
    json_parts="$json_parts,\"$key\":\"$val\""
done

# 追加行
mkdir -p "$(dirname "$TRACE_FILE")"
echo "{$json_parts}" >> "$TRACE_FILE"
