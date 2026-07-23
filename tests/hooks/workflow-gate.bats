# -*- bats -*-
# 单元测试: workflow-gate hook — PreToolUse 入口硬拦截

setup() {
    TEST_DIR=$(mktemp -d)
    export WORKSPACE="$TEST_DIR"
    mkdir -p "$TEST_DIR/.devflow"
    REPO_ROOT="${REPO_ROOT:-$(git -C "$BATS_TEST_DIRNAME/../.." rev-parse --show-toplevel 2>/dev/null || pwd)}"
    HOOK="$REPO_ROOT/config-templates/default/hooks/workflow-gate.sh"
    export CC_SESSION_ID="test-session-001"
}

teardown() {
    rm -f "$HOME/.claude/.emergency-bypass"
    [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
}

@test "route 缺失 → 拦截（首次 Edit/Write）" {
    run bash "$HOOK" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 1 ]
    [[ "$output" =~ workflow-gate ]]
    # 确认 route 文件已被写入（用于下次放行）
    [ -f "$TEST_DIR/.workflow-route" ]
}

@test "route 存在且 session 匹配 → 放行" {
    echo "test-session-001|assessed|1700000000" > "$TEST_DIR/.workflow-route"
    run bash "$HOOK" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 0 ]
}

@test "自身写入 .workflow-route → 放行（避免死锁）" {
    run bash "$HOOK" "Write" '{"file_path":"/tmp/.workflow-route"}'
    [ "$status" -eq 0 ]
}

@test "session 不匹配 → 拦截并清理过期 route" {
    echo "old-session-999|assessed|1700000000" > "$TEST_DIR/.workflow-route"
    run bash "$HOOK" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 1 ]
    # 过期 route 已被清理，新 route 已写入当前 session
    [ -f "$TEST_DIR/.workflow-route" ]
    ! grep -q "old-session-999" "$TEST_DIR/.workflow-route"
    grep -q "test-session-001" "$TEST_DIR/.workflow-route"
}

@test "逃生文件存在 → 全部放行" {
    mkdir -p "$HOME/.claude"
    touch "$HOME/.claude/.emergency-bypass"
    run bash "$HOOK" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 0 ]
}

@test "非 Edit/Write/Bash 修改类 → 不检查" {
    run bash "$HOOK" "Read" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 0 ]
    [ ! -f "$TEST_DIR/.workflow-route" ]
}

@test "Bash 无写入重定向 → 不拦截" {
    run bash "$HOOK" "Bash" '{"command":"echo hello"}'
    [ "$status" -eq 0 ]
}

@test "Bash 有写入重定向 → 拦截" {
    run bash "$HOOK" "Bash" '{"command":"echo hello > /tmp/out.txt"}'
    [ "$status" -eq 1 ]
}

@test "无 .devflow/ 目录 → 跳过" {
    rm -rf "$TEST_DIR/.devflow"
    run bash "$HOOK" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 0 ]
}
