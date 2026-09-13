#!/bin/bash
# C 臂专属：g0 结果门禁（fail-to-pass 同款思想）——commit 前全套测试必须绿
# PreToolUse(Bash)：拦截 git commit；测试不过 → exit 2。不检查过程（有无 RED commit/阶段），只看结果。
set -uo pipefail
_STDIN=$(command -v jq >/dev/null 2>&1 && cat || true)
CMD=$(printf '%s' "$_STDIN" | jq -r '.tool_input.command // empty' 2>/dev/null || true)
[ -n "$CMD" ] || exit 0
[[ "$CMD" =~ (^|[[:space:];&|])git[[:space:]].*commit ]] || exit 0
CWD=$(printf '%s' "$_STDIN" | jq -r '.cwd // empty' 2>/dev/null || true)
REPO="${CWD:-$(pwd)}"
TCMD="${G0_TEST_CMD:?g0-enforce: G0_TEST_CMD 未注入}"
cd "$REPO" || exit 0
if ! eval "$TCMD" >/dev/null 2>&1; then
    cat >&2 <<EOF

⛔ g0-enforce: 提交被拒——测试未全绿（结果门禁，exit 2）

  本仓验收只看结果：任何 commit 必须让全量测试通过。
  没有测试的改动、或测试仍失败的改动，不允许进入历史。
  先补测试并修到绿，再提交。

EOF
    exit 2
fi
exit 0
