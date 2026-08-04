#!/bin/bash
# stage-gate-block.sh — PreToolUse hook：按 .devflow/stage 阻断越阶段写入
# 阶段 < tdd:done 时，禁止写实现源文件（强制先完成 /tdd RED 测试）
# exit 2 = 硬阻断（Claude Code 唯一可靠阻断机制）
#
# 逻辑：
# 1. 仅拦截 Edit/Write
# 2. 项目无 .devflow/stage → 放行（未初始化，不干扰）
# 3. stage >= tdd:done → 放行
# 4. 目标文件是测试/文档/配置 → 放行
# 5. 目标文件是实现代码 → exit 2 硬阻断

set -euo pipefail

TOOL_NAME="$1"
TOOL_INPUT="$2"
WORKSPACE="${WORKSPACE:-$(pwd)}"

# ── 仅拦截 Edit/Write ──
[[ "$TOOL_NAME" =~ ^(Edit|Write)$ ]] || exit 0

# ── 项目无 .devflow/ → 放行 ──
STAGE_FILE="$WORKSPACE/.devflow/stage"
[ -f "$STAGE_FILE" ] || exit 0

# ── 读取当前阶段 ──
current_stage=$(cat "$STAGE_FILE" 2>/dev/null || echo "")

# ── 阶段顺序 ──
stage_order="explore:done spec:done tickets:done tickets:reviewed tdd:done implement:done done"

# ── 计算当前阶段索引 ──
current_index=0
tdd_index=0
i=1
for s in $stage_order; do
    [ "$s" = "$current_stage" ] && current_index=$i
    [ "$s" = "tdd:done" ] && tdd_index=$i
    i=$((i + 1))
done

# ── 阶段 >= tdd:done → 放行（含 implement:done / done / 未知阶段）──
# 未知阶段（空或索引=0）视为未开始，仍需阻断
if [ "$current_index" -eq 0 ] || [ "$current_index" -ge "$tdd_index" ]; then
    # current_index=0 时 stage 文件存在但值不匹配 → 未知阶段，继续阻断
    [ "$current_index" -ge "$tdd_index" ] && exit 0
fi

# ── 阶段 < tdd:done，检查目标文件类型 ──

# 提取文件路径
FILE_PATH=""
if command -v jq >/dev/null 2>&1; then
    FILE_PATH=$(echo "$TOOL_INPUT" | jq -r '.file_path // empty' 2>/dev/null || true)
fi
[ -n "$FILE_PATH" ] || exit 0

# ── 测试文件检测 ──
is_test_file() {
    local f="$1"
    # 测试目录
    [[ "$f" =~ (^|/)(tests?|__tests__|e2e|spec|cypress)(/|$) ]] && return 0
    # 测试文件名模式：*.test.* / *.spec.*
    [[ "$f" =~ \.(test|spec)\.(ts|js|tsx|jsx|mjs|cjs)$ ]] && return 0
    # Python: test_*.py / *_test.py
    [[ "$f" =~ (^|/)test_[^/]+\.py$ ]] && return 0
    [[ "$f" =~ (^|/)[^/]+_test\.py$ ]] && return 0
    # PHP: *Test.php
    [[ "$f" =~ (^|/)[^/]+Test\.php$ ]] && return 0
    # Go: *_test.go
    [[ "$f" =~ (^|/)[^/]+_test\.go$ ]] && return 0
    # 测试辅助文件（__snapshots__ / fixtures / mocks / helpers）
    [[ "$f" =~ (^|/)(__snapshots__|fixtures?|mocks?|__mocks__|helpers?|test[-_]?(utils|helpers|data|fixtures?))(/) ]] && return 0
    return 1
}

# ── 文档/配置文件 → 始终放行 ──
is_config_file() {
    local f="$1"
    [[ "$f" =~ \.(md|json|yaml|yml|toml|cfg|ini|env|txt|csv|xml|html|css|scss|less|svg|png|jpg|gif|ico|woff2?|ttf|eot)$ ]] && return 0
    local bn
    bn=$(basename "$f")
    [[ "$bn" =~ ^(Makefile|Dockerfile|\.gitignore|\.dockerignore|\.env\.|README|LICENSE|CHANGELOG|\.editorconfig|\.prettierrc|\.eslintrc|\.stylelintrc) ]] && return 0
    # .devflow 内部文件
    [[ "$f" =~ (^|/)\.devflow/ ]] && return 0
    return 1
}

# ── 已知实现源文件扩展名（非测试/配置的其他代码文件）──
is_source_file() {
    local f="$1"
    [[ "$f" =~ \.(js|ts|jsx|tsx|mjs|cjs|py|php|go|java|rb|rs|vue|svelte|swift|kt|scala|cs|fsx|r|sql|sh|bash|zsh|fish|ps1|pl|pm|lua|dart|ex|exs|erl|hrl|clj|cljs|edn|elm|hs|lhs|nim|zig|cr|jl|rkt|scm|ss|dpr|pas|pp|bas|cls|frm|vba|vbs|bat|cmd)$ ]] && return 0
    # C/C++
    [[ "$f" =~ \.(c|cc|cpp|cxx|c\+|h|hpp|hh|hxx|h\+)$ ]] && return 0
    return 1
}

# ── 放行测试文件 ──
is_test_file "$FILE_PATH" && exit 0

# ── 放行文档/配置文件 ──
is_config_file "$FILE_PATH" && exit 0

# ── 非源文件 → 保守放行（避免误拦）──
is_source_file "$FILE_PATH" || exit 0

# ── 硬阻断 ──
cat >&2 <<EOF

⛔ stage-gate-block: 阶段不足，禁止写入实现文件（exit 2 — 不可绕过）

  当前阶段: ${current_stage:-"(未设置)"}
  需要达到: tdd:done（完成 /tdd RED 测试）
  被拦截文件: $FILE_PATH

  流程: explore:done → spec:done → tickets:done → tickets:reviewed → tdd:done → implement:done

  必须先完成 /tdd:
  1. 按 ticket AC 写失败测试 + stub
  2. bash .devflow/scripts/test-gate.sh（C0.1-C0.9 秒检）
  3. 运行测试确认 🔴 RED
  4. RED commit（message 含 "TDD: RED"）
  5. 系统自动检测 tdd:done 后，方可写实现文件

  这不是 bug——跳过 /tdd = 功能无测试覆盖。
  详情: ~/.claude/gate-checklists/test-checklist.md

EOF
exit 2
