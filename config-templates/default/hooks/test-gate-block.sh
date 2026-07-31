#!/bin/bash
# test-gate-block.sh — L0 硬阻断：拦截 git commit "TDD: RED" → 运行 test-gate.sh
# 部署到 ~/.claude/hooks/，由 settings.json PreToolUse Bash matcher 触发
#
# 逻辑：
# 1. 仅拦截 Bash 工具 + git commit 含 "TDD: RED"
# 2. 项目无 .devflow/scripts/test-gate.sh → 放行
# 3. 运行 test-gate.sh（C0.1-C0.6 秒检）
# 4. 通过 → exit 0 / 不通过 → exit 2（硬阻断，Claude Code 唯一可靠阻断机制）
#
# 社区三条铁律之三：不能失败的检查不是检查。advisory 警告 = 不存在。

set -euo pipefail

TOOL_NAME="$1"
TOOL_INPUT="$2"
WORKSPACE="${WORKSPACE:-$(pwd)}"

# ── 仅拦截 Bash 工具 ──
[ "$TOOL_NAME" = "Bash" ] || exit 0

# ── 提取命令内容（jq 优先，正确处理 JSON 转义引号）──
TOOL_COMMAND=""
if command -v jq >/dev/null 2>&1; then
    TOOL_COMMAND=$(echo "$TOOL_INPUT" | jq -r '.command // empty' 2>/dev/null || true)
else
    # fallback: grep 提取（不处理转义引号，对简单命令够用）
    TOOL_COMMAND=$(echo "$TOOL_INPUT" | grep -oP '"command"\s*:\s*"\K[^"\\]*(?:\\.[^"\\]*)*' | head -1 || true)
fi
[ -n "$TOOL_COMMAND" ] || exit 0

# ── 仅拦截 git commit 含 "TDD: RED" ──
if ! echo "$TOOL_COMMAND" | grep -qE 'git\s+(commit|ci)\s+.*TDD:\s*RED'; then
    exit 0
fi

# ── 项目无 test-gate.sh → 放行 ──
TEST_GATE="$WORKSPACE/.devflow/scripts/test-gate.sh"
[ -f "$TEST_GATE" ] || exit 0

# ── 运行 test-gate.sh ──
if bash "$TEST_GATE" 2>&1; then
    exit 0
fi

# ── 硬阻断 ──
cat >&2 <<'EOF'

⛔ L0 硬阻断: test-gate.sh 未通过（exit 2 — 不可绕过）

  C0.1-C0.6 提交前秒检未全部通过：
  • C0.1 调试残留（test.only / describe.only / page.pause）
  • C0.2 恒真断言（toBeGreaterThanOrEqual(0) / toBeTruthy / toBeDefined）
  • C0.3 硬编码端口（localhost:XXXX）
  • C0.4 固定延时（waitForTimeout / setTimeout > 999ms）
  • C0.5 测试发现（0 tests = PASS(0) 真空通过 → 阻断）
  • C0.6 try/catch 包裹 expect（腐烂断言高风险）

  修复上述问题后重新提交。详细规则: ~/.claude/gate-checklists/test-checklist.md §C0

EOF
exit 2
