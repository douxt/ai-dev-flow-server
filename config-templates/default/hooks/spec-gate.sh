#!/bin/bash
# spec-gate.sh — PostToolUse hook：docs/specs/**.md 产物结构自查（形式正确性轴，ADR 见 docs/decisions/）
# 与 stage-gate 正交：stage-gate 管"什么时候准写"，本钩子管"写出来的东西齐不齐"
# 通道语义：warn = stdout JSON additionalContext（stderr 必须留空，exit 0 的 stderr 模型不可见）
#           block = exit 2 + stderr 回灌模型（写入不回撤，事后门禁）
# 降级契约：checker 缺失/崩溃/旧版无 --spec 能力 → 一律静默放行 + spec-gate.degraded 事件，
#           绝不把内部错误解读为缺项（rc>=2 或非 {"mode":"spec"} 输出 = 降级）

set -uo pipefail

hb() {  # 心跳：trace.sh 可用则委托，否则裸写；两者都失败不阻断
    if [ -f "$WORKSPACE/.devflow/scripts/trace.sh" ]; then
        bash "$WORKSPACE/.devflow/scripts/trace.sh" "$@" 2>/dev/null || true
    elif [ -d "$WORKSPACE/.devflow" ]; then
        printf '{"event":"%s","ts":"%s"}\n' "$1" "$(date -Iseconds)" >> "$WORKSPACE/.devflow/trace.jsonl" 2>/dev/null || true
    fi
}

# 手动测试通道：位置参数 $1=tool_name $2=tool_input_json（与 stage-tracker 同契约）
if [ $# -ge 1 ] && [ -n "${1:-}" ]; then
    TOOL_NAME="$1"
    TOOL_INPUT="${2:-}"
    SESSION_ID="manual"
    WS_CWD=""
else
    _STDIN=$(cat)
    if ! command -v jq >/dev/null 2>&1; then
        [ -d "$WORKSPACE/.devflow" ] && hb "spec-gate.degraded" reason="jq-missing"
        exit 0
    fi
    TOOL_NAME=$(printf '%s' "$_STDIN" | jq -r '.tool_name // empty')
    TOOL_INPUT=$(printf '%s' "$_STDIN" | jq -r '(.tool_input // {}) | tostring')
    WS_CWD=$(printf '%s' "$_STDIN" | jq -r '.cwd // empty')
    SESSION_ID=$(printf '%s' "$_STDIN" | jq -r '.session_id // "anon"')
fi
# .cwd 兜底：钩子进程 PWD 是 CC 启动目录，跨 worktree/多根时会判错仓库（与 stage-tracker 同契约）
WORKSPACE="${WORKSPACE:-${WS_CWD:-$(pwd)}}"

[[ "$TOOL_NAME" =~ ^(Edit|Write)$ ]] || exit 0
[ -d "$WORKSPACE/.devflow" ] || exit 0

FILE_PATH=$(printf '%s' "$TOOL_INPUT" | jq -r '.file_path // empty' 2>/dev/null || true)
[ -n "$FILE_PATH" ] || exit 0
case "$FILE_PATH" in
    *..*) exit 0 ;;  # 含穿越段的非常规路径不处理（真实 tool_input 均为规范化绝对路径）
    "$WORKSPACE"/docs/specs/*.md) REL="${FILE_PATH#"$WORKSPACE"/}" ;;
    *) exit 0 ;;
esac

MODE="warn"
[ -f "$WORKSPACE/.devflow/spec-gate-mode" ] && MODE=$(tr -d ' \t\r\n' < "$WORKSPACE/.devflow/spec-gate-mode")
if [ "$MODE" = "off" ]; then
    hb "spec-gate.skip" reason="off" file="$REL"
    exit 0
fi

# 基线豁免：安装时存量 spec 按路径永久豁免（不依赖 mtime——PostToolUse 触发时 mtime 必为"刚刚"）
if [ -f "$WORKSPACE/.devflow/spec-gate-baseline" ] \
   && grep -qxF "$REL" "$WORKSPACE/.devflow/spec-gate-baseline" 2>/dev/null; then
    hb "spec-gate.skip" reason="baseline" file="$REL"
    exit 0
fi
# 人工豁免清单（模型不可写自身：文件内注释豁免已弃用）
if [ -f "$WORKSPACE/.devflow/spec-gate-exclude" ] \
   && grep -qxF "$REL" "$WORKSPACE/.devflow/spec-gate-exclude" 2>/dev/null; then
    hb "spec-gate.skip" reason="excluded" file="$REL"
    exit 0
fi

CHECKER="$WORKSPACE/.devflow/scripts/check_constitution.py"
if [ ! -f "$CHECKER" ]; then
    hb "spec-gate.degraded" reason="checker-missing" file="$REL"
    exit 0
fi
if ! command -v python3 >/dev/null 2>&1; then
    hb "spec-gate.degraded" reason="python3-missing" file="$REL"
    exit 0
fi

OUT=$(python3 "$CHECKER" --spec "$FILE_PATH" --json 2>/dev/null) && RC=$? || RC=$?
if [ "${RC:-1}" -ge 2 ]; then
    hb "spec-gate.degraded" reason="checker-rc-$RC" file="$REL"
    exit 0
fi
# 旧版 checker 无 --spec 会把参数当路径、rc=1 带 error 字段——按形状判降级，不误报缺项
CHECKER_MODE=$(printf '%s' "$OUT" | jq -r '.mode // empty' 2>/dev/null || true)
if [ "$CHECKER_MODE" != "spec" ]; then
    hb "spec-gate.degraded" reason="checker-no-spec-mode" file="$REL"
    exit 0
fi

FAILED=$(printf '%s' "$OUT" | jq -r '.failed // 0')
if [ "${FAILED:-0}" -eq 0 ]; then
    rm -f "$WORKSPACE/.devflow/.spec-gate-blocks" 2>/dev/null || true
    hb "spec-gate.pass" file="$REL"
    exit 0
fi

MISSING=$(printf '%s' "$OUT" | jq -r '[.checks[].desc] | join("；")')

# warn 台账：按日轮换 + 每 session 每文件封顶 3 次（缺项指纹去重已弃用：增量补写缺项集常变，防不住打断也放不过终态）
TODAY=$(date +%F)
LEDGER="$WORKSPACE/.devflow/.spec-gate-warned"
if [ -f "$LEDGER" ]; then
    grep "^$TODAY|" "$LEDGER" > "$LEDGER.tmp" 2>/dev/null || : > "$LEDGER.tmp"
    mv "$LEDGER.tmp" "$LEDGER"
fi
WARN_COUNT=$(grep -c "|$SESSION_ID|$REL\$" "$LEDGER" 2>/dev/null || true)
if [ "${WARN_COUNT:-0}" -ge 3 ] && [ "$MODE" = "warn" ]; then
    hb "spec-gate.skip" reason="warn-capped" file="$REL" session="$SESSION_ID"
    exit 0
fi
printf '%s|%s|%s\n' "$TODAY" "$SESSION_ID" "$REL" >> "$LEDGER"

if [ "$MODE" != "block" ]; then
    jq -n --arg ac "spec-gate（docs/specs 结构自查）未通过：$REL — $MISSING。请对照 ~/.claude/gate-checklists/spec-checklist.md 补齐（S1-S5 必过项），并在文末「Spec 质量宪法合规表」完成自查；若该文件不是 spec，请移出 docs/specs/ 或由人工加入 .devflow/spec-gate-exclude。" \
        '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $ac}}'
    hb "spec-gate.warn" file="$REL" session="$SESSION_ID" failed="$FAILED"
    exit 0
fi

# block：每次编辑都报（写入不回撤），连续 ≥3 次升级报人防死循环（.verify-blocks 同族模式）
BLOCKS_FILE="$WORKSPACE/.devflow/.spec-gate-blocks"
BLOCK_COUNT=0
[ -f "$BLOCKS_FILE" ] && BLOCK_COUNT=$(grep "^$REL:" "$BLOCKS_FILE" 2>/dev/null | cut -d: -f2 || true)
BLOCK_COUNT=$(( ${BLOCK_COUNT:-0} + 1 ))
printf '%s:%s\n' "$REL" "$BLOCK_COUNT" > "$BLOCKS_FILE"

{
    echo "spec-gate（硬阻断）：$REL 结构检查缺 $FAILED 项 — $MISSING"
    echo "对照 ~/.claude/gate-checklists/spec-checklist.md 补齐后重新保存；本次写入已落盘但不得进入下一阶段。"
    if [ "$BLOCK_COUNT" -ge 3 ]; then
        echo ""
        echo "⚠️  同一文件已连续阻断 ${BLOCK_COUNT} 次——请停下来确认：1) 是否理解缺项 2) 修复方向是否正确 3) 若门禁过严，报告给人而非绕过（豁免清单 .devflow/spec-gate-exclude 由人工维护）"
    fi
} >&2
hb "spec-gate.block" file="$REL" count="$BLOCK_COUNT"
exit 2
