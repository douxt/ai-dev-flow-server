#!/bin/bash
# A/B 臂最小 stage 推进 shim：检测到 "TDD: RED" commit 且 stage=tickets:reviewed → 写 tdd:done
# 生产 stage-tracker 依赖 spec/tickets 产物链（headless 单票 run 不产出），此 shim 仅保留
# "RED 前置" 判定所需的最小推进，偏差声明见 scripts/e1/README.md
set -uo pipefail
_STDIN=$(cat)
command -v jq >/dev/null 2>&1 || exit 0
TOOL=$(printf '%s' "$_STDIN" | jq -r '.tool_name // empty')
[ "$TOOL" = "Bash" ] || exit 0
CWD=$(printf '%s' "$_STDIN" | jq -r '.cwd // empty')
STAGE_FILE="$CWD/.devflow/stage"
[ -f "$STAGE_FILE" ] || exit 0
grep -q "tickets:reviewed" "$STAGE_FILE" 2>/dev/null || exit 0
git -C "$CWD" log -1 --format=%s 2>/dev/null | grep -q "TDD: RED" || exit 0
printf 'tdd:done\n' > "$STAGE_FILE"
