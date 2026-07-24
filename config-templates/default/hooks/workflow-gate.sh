#!/bin/bash
# workflow-gate.sh — PreToolUse hook：首次修改文件前强制工作流评估
# 部署到 ~/.claude/hooks/，由 settings.json PreToolUse 触发
#
# 逻辑：
# 1. 逃生文件 ~/.claude/.emergency-bypass 存在 → 全部放行
# 2. .workflow-route 存在且 session_id 匹配 → 放行
# 3. .workflow-route 不存在 → 拦截一次，注入路由规则，写入 route 文件
#    （信任 agent 看到注入规则后会做评估；第二次调用放行）
# 4. session 不匹配的 route → 清理后重新评估

set -euo pipefail

TOOL_NAME="$1"
TOOL_INPUT="$2"
WORKSPACE="${WORKSPACE:-$(pwd)}"
ROUTE_FILE="$WORKSPACE/.workflow-route"
BYPASS_FILE="$HOME/.claude/.emergency-bypass"
TRACE_SCRIPT="$WORKSPACE/.devflow/scripts/trace.sh"

trace() { bash "$TRACE_SCRIPT" "$@" 2>/dev/null || true; }

# ── 逃生机制 ──
if [ -f "$BYPASS_FILE" ]; then
    trace "gate.bypass" reason="emergency_bypass_file" tool="$TOOL_NAME"
    exit 0
fi

# ── 仅拦截修改类工具 ──
case "$TOOL_NAME" in
    Edit|Write) ;;
    Bash)
        # 仅拦截有明显写入意图的 Bash 命令
        if ! echo "$TOOL_INPUT" | grep -qE '>\s*\S|tee\s+\S|sed\s+.*-i|>>|dd\s+of='; then
            exit 0
        fi
        ;;
    *) exit 0 ;;
esac

# ── 提取目标文件路径 ──
target_file=""
case "$TOOL_NAME" in
    Edit|Write)
        target_file=$(echo "$TOOL_INPUT" | grep -oP '"file_path"\s*:\s*"\K[^"]+' | head -1)
        ;;
    Bash)
        target_file=$(echo "$TOOL_INPUT" | grep -oP '>\s*\K\S+' | head -1)
        ;;
esac

# ── 目标文件是 .workflow-route 自身 → 放行（避免死锁） ──
if [ -n "$target_file" ] && echo "$target_file" | grep -q ".workflow-route"; then
    exit 0
fi

# ── 仅在工作区有 .devflow/ 的项目中生效 ──
[ -d "$WORKSPACE/.devflow" ] || exit 0

# ── 获取当前 session_id ──
session_id="${CC_SESSION_ID:-unknown}"

# ── .workflow-route 存在且 session_id 匹配 → 放行 ──
if [ -f "$ROUTE_FILE" ]; then
    route_content=$(cat "$ROUTE_FILE" 2>/dev/null || echo "")
    route_session=$(echo "$route_content" | cut -d'|' -f1)
    if [ "$route_session" = "$session_id" ]; then
        trace "gate.pass" reason="route_exists" session_id="$session_id"
        exit 0
    fi
    # session 不匹配 → 清理过期 route，继续拦截
    trace "gate.block" reason="session_expired" old_session="$route_session" current_session="$session_id"
    rm -f "$ROUTE_FILE"
fi

# ── 首次拦截：注入路由规则 → 写入 route 文件（信任 agent 会做评估）→ 退出 ──
trace "gate.block" reason="first_edit" tool="$TOOL_NAME" session_id="$session_id"
echo "${session_id}|pending|$(date +%s)" > "$ROUTE_FILE"

cat >&2 <<'EOF'

⛔ workflow-gate: 工作流评估未完成（首次拦截，路由规则已注入）

处理任何开发任务前，必须先做工作流评估：

📋 评估三问：
1. 上下文窗口装得下吗？ 否 → /wayfinder（~5%）
2. 有现有文档（CONTEXT.md / spec / ADR）？ 无 → 先进 Plan Mode 出初稿
3. 有雾吗？ 有雾 → /grill-with-docs | 无雾 → /to-spec
   简单改动 → 直接 /implement

推荐路径:
  默认 → Plan Mode → /grill-with-docs → /to-spec → 评审 → /to-tickets → /tdd → /implement(自动重试) → /code-review
  大型 → /wayfinder → /to-spec → /review-cc-cli（独立评审）→ /to-tickets → /tdd → /implement
  简单 → 直接 /implement

阶段追踪（自动，hook 驱动）:
  explore:done → spec:done → tickets:done → tdd:done → implement:done → done

Spec 评审（/to-spec 后）:
  大型任务 → /review-cc-cli --opus --rubric prd,plan --with ~/.claude/gate-checklists/spec-checklist.md spec.md
  中型 → 自查 spec-checklist（S1-S10）
  简单 → 跳过

TDD 前置（/to-tickets 后）:
  每个 ticket → /tdd → C1-C4 确认 → RED commit → tdd:done 自动检测

AFK 自动重试（/implement 阶段）:
  填逻辑 → 测试失败 → 自动修复重试（最多 3 次）→ 超限 escalation

评估完成后重新执行即可。

EOF

exit 1
