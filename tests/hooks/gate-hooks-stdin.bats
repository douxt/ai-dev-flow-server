# -*- bats -*-
# stdin JSON 协议行为测试 — 三门禁 + file-guard
# 背景：2026-08-27 UMES3 缺陷报告——旧模板 hook 用 $1/$2 取参而 CC PreToolUse 是
# stdin JSON 传参，真实调用 100% 失效；旧 bats 同样用 $1/$2 测试，与坏实现"一致错"全绿。
# 本文件按真实协议（printf JSON | hook）验证，并做拦截/放行两侧断言。
# 仅 GNU grep 环境（ubuntu 镜像）运行——修复版依赖 grep -oP。

setup() {
    REPO_ROOT="${REPO_ROOT:-$(cd "$BATS_TEST_DIRNAME/../.." && pwd)}"
    TEST_DIR=$(mktemp -d)
    export WORKSPACE="$TEST_DIR"
    HOOKS="$REPO_ROOT/config-templates/default/hooks"
    SID="stdin-test-$$-$BATS_TEST_NUMBER"
    cd "$TEST_DIR"
}

teardown() {
    rm -rf "$TEST_DIR"
}

# call_hook <script> <json> → 退出码存入 RC
call_hook() {
    RC=0
    printf '%s' "$2" | bash "$HOOKS/$1" >/dev/null 2>&1 || RC=$?
}

json_edit() {
    printf '{"tool_name":"Edit","tool_input":{"file_path":"%s"},"session_id":"%s","cwd":"%s"}' "$1" "$SID" "$TEST_DIR"
}

# ── workflow-gate ──

@test "workflow-gate: stdin 首次 Edit 无 route → exit 2 拦截" {
    mkdir -p .devflow   # 修复版前置：仅在有 .devflow/ 的工作区生效
    call_hook workflow-gate.sh "$(json_edit "$TEST_DIR/src/a.ts")"
    [ "$RC" -eq 2 ]
}

@test "workflow-gate: stdin 同 session 第二次 → 放行" {
    mkdir -p .devflow
    call_hook workflow-gate.sh "$(json_edit "$TEST_DIR/src/a.ts")"
    call_hook workflow-gate.sh "$(json_edit "$TEST_DIR/src/b.ts")"
    [ "$RC" -eq 0 ]
}

@test "workflow-gate: stdin 非 Edit/Write 工具 → 放行" {
    call_hook workflow-gate.sh "{\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"ls\"},\"session_id\":\"$SID\",\"cwd\":\"$TEST_DIR\"}"
    [ "$RC" -eq 0 ]
}

# ── stage-gate-block ──

@test "stage-gate: 无 stage 文件 → 放行" {
    call_hook stage-gate-block.sh "$(json_edit "$TEST_DIR/src/a.ts")"
    [ "$RC" -eq 0 ]
}

@test "stage-gate: pre-tdd 写实现源文件 → exit 2" {
    mkdir -p .devflow && echo "spec:done" > .devflow/stage
    call_hook stage-gate-block.sh "$(json_edit "$TEST_DIR/src/a.ts")"
    [ "$RC" -eq 2 ]
}

@test "stage-gate: pre-tdd 写文档 → 放行" {
    mkdir -p .devflow && echo "spec:done" > .devflow/stage
    call_hook stage-gate-block.sh "$(json_edit "$TEST_DIR/docs/x.md")"
    [ "$RC" -eq 0 ]
}

@test "stage-gate: pre-tdd 写测试文件 → 放行（/tdd 阶段合法）" {
    mkdir -p .devflow && echo "spec:done" > .devflow/stage
    call_hook stage-gate-block.sh "$(printf '{"tool_name":"Write","tool_input":{"file_path":"%s/tests/a.test.ts"},"session_id":"%s","cwd":"%s"}' "$TEST_DIR" "$SID" "$TEST_DIR")"
    [ "$RC" -eq 0 ]
}

@test "stage-gate: GREEN 窗口改测试 → exit 2（G1 反作弊，函数定义序已修）" {
    git init -q .
    mkdir -p .devflow && echo "tdd:done" > .devflow/stage
    git add .devflow/stage && git -c user.email=t@t -c user.name=t commit -qm "TDD: RED a"
    call_hook stage-gate-block.sh "$(printf '{"tool_name":"Edit","tool_input":{"file_path":"%s/tests/a.test.ts"},"session_id":"%s","cwd":"%s"}' "$TEST_DIR" "$SID" "$TEST_DIR")"
    [ "$RC" -eq 2 ]
}

@test "stage-gate: GREEN 窗口改实现 → 放行" {
    git init -q .
    mkdir -p .devflow && echo "tdd:done" > .devflow/stage
    git add .devflow/stage && git -c user.email=t@t -c user.name=t commit -qm "TDD: RED a"
    call_hook stage-gate-block.sh "$(json_edit "$TEST_DIR/src/a.ts")"
    [ "$RC" -eq 0 ]
}

# ── stage-gate-block：多行 stage 存量（2026-09-09 UMES3 反馈 P0-1/P2-2）──

@test "stage-gate: 多行 stage 末行 implement:done + 写实现 → 放行（修复前永久误拦）" {
    mkdir -p .devflow
    printf 'explore:done\ngrill:done\nspec:done\ntickets:done\ntdd:done\nimplement:done\n' > .devflow/stage
    call_hook stage-gate-block.sh "$(json_edit "$TEST_DIR/src/a.ts")"
    [ "$RC" -eq 0 ]
}

@test "stage-gate: 多行 stage 末行 spec:done + 写实现 → exit 2 且报错为单行值+损坏提示" {
    mkdir -p .devflow
    printf 'explore:done\nspec:done\n' > .devflow/stage
    ERR=""
    RC=0
    ERR=$(printf '%s' "$(json_edit "$TEST_DIR/src/a.ts")" | bash "$HOOKS/stage-gate-block.sh" 2>&1 >/dev/null) || RC=$?
    [ "$RC" -eq 2 ]
    echo "$ERR" | grep -q '当前阶段: spec:done'
    ! echo "$ERR" | grep -q '当前阶段: explore:done'
    echo "$ERR" | grep -q '疑似多行损坏'
}

@test "stage-gate: stage 尾随空行 → 按末个非空行判定不退化" {
    mkdir -p .devflow
    printf 'spec:done\n\n\n' > .devflow/stage
    call_hook stage-gate-block.sh "$(json_edit "$TEST_DIR/src/a.ts")"
    [ "$RC" -eq 2 ]
}

# ── stage-tracker：无参 stdin 协议（2026-09-09 反馈 P0-2——修复前每次 exit 1）──

@test "stage-tracker: 无参 stdin + 有 spec.md → exit 0 且 stage 写为单行" {
    unset WORKSPACE   # 走 JSON .cwd 解析路径
    mkdir -p .devflow
    echo "# spec content" > spec.md
    call_hook stage-tracker.sh "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$TEST_DIR/spec.md\"},\"session_id\":\"$SID\",\"cwd\":\"$TEST_DIR\"}"
    [ "$RC" -eq 0 ]
    [ "$(wc -l < .devflow/stage)" -eq 1 ]
    [ "$(cat .devflow/stage)" = "spec:done" ]
}

@test "stage-tracker: 无参 stdin + 无 .devflow → 放行不写" {
    unset WORKSPACE
    echo "# spec content" > spec.md
    call_hook stage-tracker.sh "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$TEST_DIR/spec.md\"},\"session_id\":\"$SID\",\"cwd\":\"$TEST_DIR\"}"
    [ "$RC" -eq 0 ]
    [ ! -f .devflow/stage ]
}

@test "stage-tracker: 多行 previous + 新产物 → 收敛为单行" {
    unset WORKSPACE
    mkdir -p .devflow issues
    printf 'explore:done\nspec:done\n' > .devflow/stage
    echo "# spec" > spec.md
    echo "# ticket" > issues/t1.md
    call_hook stage-tracker.sh "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$TEST_DIR/issues/t1.md\"},\"session_id\":\"$SID\",\"cwd\":\"$TEST_DIR\"}"
    [ "$RC" -eq 0 ]
    [ "$(wc -l < .devflow/stage)" -eq 1 ]
    [ "$(cat .devflow/stage)" = "tickets:done" ]
}

@test "stage-tracker: 原子写无 tmp 残留" {
    unset WORKSPACE
    mkdir -p .devflow
    echo "# spec" > spec.md
    call_hook stage-tracker.sh "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$TEST_DIR/spec.md\"},\"session_id\":\"$SID\",\"cwd\":\"$TEST_DIR\"}"
    [ "$RC" -eq 0 ]
    [ -z "$(ls .devflow/ | grep '\.tmp\.' || true)" ]
}

# ── test-gate-block ──

json_bash() {
    printf '{"tool_name":"Bash","tool_input":{"command":"%s"},"session_id":"%s","cwd":"%s"}' "$1" "$SID" "$TEST_DIR"
}

@test "test-gate-block: 非 RED commit → 放行" {
    call_hook test-gate-block.sh "$(json_bash 'git commit -m plain')"
    [ "$RC" -eq 0 ]
}

@test "test-gate-block: RED commit + gate 失败 → exit 2" {
    mkdir -p .devflow/scripts
    printf '#!/bin/bash\nexit 1\n' > .devflow/scripts/test-gate.sh
    call_hook test-gate-block.sh "$(json_bash 'git commit -m \"TDD: RED x\"')"
    [ "$RC" -eq 2 ]
}

@test "test-gate-block: RED commit + gate 通过 → 放行" {
    mkdir -p .devflow/scripts
    printf '#!/bin/bash\nexit 0\n' > .devflow/scripts/test-gate.sh
    call_hook test-gate-block.sh "$(json_bash 'git commit -m \"TDD: RED x\"')"
    [ "$RC" -eq 0 ]
}

# ── file-guard ──

@test "file-guard: settings.json 自保护 → exit 2（死代码复活验证）" {
    call_hook file-guard.sh "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$HOME/.claude/settings.json\"},\"cwd\":\"$TEST_DIR\"}"
    [ "$RC" -eq 2 ]
}

@test "file-guard: hooks/ 目录自保护 → exit 2" {
    call_hook file-guard.sh "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$HOME/.claude/hooks/x.sh\"},\"cwd\":\"$TEST_DIR\"}"
    [ "$RC" -eq 2 ]
}

@test "file-guard: .git-hooks/ 自保护 → exit 2" {
    call_hook file-guard.sh "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$HOME/.git-hooks/pre-commit\"},\"cwd\":\"$TEST_DIR\"}"
    [ "$RC" -eq 2 ]
}

@test "file-guard: .claude/plans 非保护路径 → 放行" {
    call_hook file-guard.sh "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$HOME/.claude/plans/x.md\"},\"cwd\":\"$TEST_DIR\"}"
    [ "$RC" -eq 0 ]
}

@test "file-guard: worktrees 路径 → 放行" {
    call_hook file-guard.sh "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$TEST_DIR/.claude/worktrees/a/x.ts\"},\"cwd\":\"$TEST_DIR\"}"
    [ "$RC" -eq 0 ]
}

@test "file-guard: 非 worktree 主仓库路径 → exit 2（原 exit 1 修正）" {
    call_hook file-guard.sh "{\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"$TEST_DIR/main-repo/x.ts\"},\"cwd\":\"$TEST_DIR\"}"
    [ "$RC" -eq 2 ]
}

@test "file-guard: \$1 手动兼容模式仍可用" {
    run bash "$HOOKS/file-guard.sh" "$TEST_DIR/main-repo/x.ts"
    [ "$status" -eq 2 ]
}
