#!/bin/bash
# workflow-gate.sh — PreToolUse hook：首次修改文件前强制工作流评估
# 部署到 ~/.claude/hooks/，由 settings.json PreToolUse 触发
#
# 逻辑：
# 1. 逃生文件 ~/.claude/.emergency-bypass 存在 → 全部放行
# 2. 全局 route（~/.claude/mem-state/workflow-route）mtime 在 TTL 内 → 放行
# 3. route 缺失/过期 → 拦截一次，注入路由规则，写入 route 文件
#    （信任 agent 看到注入规则后会做评估；第二次调用放行）
#
# route 状态键演进（2026-09-09 UMES3 反馈 P1-1）：
#   旧 $WORKSPACE/.workflow-route + session_id 严格比对 → 会话跨目录（多根/worktree/
#   写 ~/.claude/plans）时每个 WORKSPACE 各一份 route，同会话连拦 4 次；压缩/子代理
#   换 sid 又反复拦（session_expired 噪音，f230245 已改 TTL）。现收为全局单文件+TTL：
#   与目录、session_id 双解耦。已接受的取舍：同 TTL 窗口内跨 .devflow 项目不再重新拦。
#   旧各工作区的 .workflow-route 为孤儿文件，不再读取。

set -euo pipefail

# Claude Code hook 协议：JSON 走 stdin。位置参数 $1/$2 仅保留给手动测试。
WS_CWD=""
if [ $# -ge 1 ] && [ -n "${1:-}" ]; then
    TOOL_NAME="$1"
    TOOL_INPUT="${2:-}"
    SESSION_ID="${CC_SESSION_ID:-unknown}"
else
    _STDIN=$(cat)
    command -v jq >/dev/null 2>&1 || exit 0   # jq 缺失 → 降级放行，不锁死会话
    TOOL_NAME=$(printf '%s' "$_STDIN" | jq -r '.tool_name // empty')
    TOOL_INPUT=$(printf '%s' "$_STDIN" | jq -r '(.tool_input // {}) | tostring')
    SESSION_ID=$(printf '%s' "$_STDIN" | jq -r '.session_id // "unknown"')
    WS_CWD=$(printf '%s' "$_STDIN" | jq -r '.cwd // empty')
fi
WORKSPACE="${WORKSPACE:-${WS_CWD:-$(pwd)}}"
# 全局单文件：评估状态与 WORKSPACE/session_id 解耦（命名沿袭 mem-state 会话态文件惯例）
ROUTE_FILE="$HOME/.claude/mem-state/workflow-route"
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

# ── 目标文件是 route（新旧路径形态）自身 → 放行（避免死锁） ──
if [ -n "$target_file" ] && echo "$target_file" | grep -q "workflow-route"; then
    exit 0
fi

# ── 仅在工作区有 .devflow/ 的项目中生效 ──
[ -d "$WORKSPACE/.devflow" ] || exit 0

# ── 当前 session_id（stdin JSON 提取，见文件头） ──
session_id="${SESSION_ID:-unknown}"

# ── route 存在且在新鲜期内 → 放行 ──
# 评估是"一次会话任务"级别的，与具体 session id / 工作目录均无关；
# TTL（f230245）解 session churn，全局路径（P1-1）解跨目录重复拦。
if [ -f "$ROUTE_FILE" ]; then
    route_ts=$(echo "$ROUTE_FILE" | xargs stat -c %Y 2>/dev/null || echo 0)
    now_ts=$(date +%s)
    ROUTE_TTL="${WORKFLOW_GATE_TTL:-14400}"   # 默认 4 小时
    if [ "$route_ts" -gt 0 ] && [ $((now_ts - route_ts)) -lt "$ROUTE_TTL" ]; then
        trace "gate.pass" reason="route_fresh" session_id="$session_id"
        exit 0
    fi
    trace "gate.block" reason="route_stale" age=$((now_ts - route_ts))
    rm -f "$ROUTE_FILE"
fi

# ── 首次拦截：注入路由规则 → 写入 route 文件（信任 agent 会做评估）→ 退出 ──
trace "gate.block" reason="first_edit" tool="$TOOL_NAME" session_id="$session_id"
mkdir -p "$(dirname "$ROUTE_FILE")" 2>/dev/null || true
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
  中型 → 自查 spec-checklist（S1-S13）+ Read knowledge/10 决策树选测试层级
  简单 → 跳过

TDD 前置（/to-tickets 后）:
  → Read knowledge/10 决策树，确认分层与 spec 一致（R7 + S13: E2E ≤ 15%）
	  → /tdd → C0 秒检（4 条 grep）→ C1-C5 预检 → C7 E2E 可信度
	  → RED commit → test-checklist 完整预检 + G0 故障注入 → 人工确认
	  → tdd:done 自动检测

	/implement 反作弊规则（GREEN 侧）:
	  🛑 不改测试、不硬编码（return {code:0,data:[]}）、GREEN commit 前跑 green-gate.sh + 全量测试 + AC 对照

AFK 自动重试（/implement 阶段）:
  填逻辑 → 测试失败 → 自动修复重试（最多 3 次）→ 超限 escalation

评估完成后重新执行即可。

EOF

exit 2
