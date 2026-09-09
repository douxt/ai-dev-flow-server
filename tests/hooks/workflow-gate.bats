# -*- bats -*-
# 单元测试: workflow-gate hook — PreToolUse 入口硬拦截

setup() {
    TEST_DIR=$(mktemp -d)
    export WORKSPACE="$TEST_DIR"
    mkdir -p "$TEST_DIR/.devflow"
    REPO_ROOT="${REPO_ROOT:-$(git -C "$BATS_TEST_DIRNAME/../.." rev-parse --show-toplevel 2>/dev/null || pwd)}"
    HOOK="$REPO_ROOT/config-templates/default/hooks/workflow-gate.sh"
    export CC_SESSION_ID="test-session-001"
    # DEFECT-002：HOME 沙箱（置于 REPO_ROOT/HOOK 解析后）——逃生文件 touch/rm 全落沙箱，不触碰真实 ~/.claude
    export HOME="$TEST_DIR/home"
    mkdir -p "$HOME/.claude"
}

teardown() {
    rm -f "$HOME/.claude/.emergency-bypass"
    [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
}

@test "route 缺失 → 拦截（首次 Edit/Write）" {
    run bash "$HOOK" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 2 ] # 修复：PreToolUse 阻断语义 exit 2（旧断言 1 = 无效拦截）
    [[ "$output" =~ workflow-gate ]]
    # 确认全局 route 已写入（用于下次放行；P1-1 起与 WORKSPACE 解耦）
    [ -f "$HOME/.claude/mem-state/workflow-route" ]
}

@test "route 新鲜（TTL 内）→ 放行，与 session_id 无关" {
    mkdir -p "$HOME/.claude/mem-state"
    echo "other-session-999|assessed|$(date +%s)" > "$HOME/.claude/mem-state/workflow-route"
    run bash "$HOOK" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 0 ]
}

@test "自身写入 .workflow-route → 放行（避免死锁）" {
    run bash "$HOOK" "Write" '{"file_path":"/tmp/.workflow-route"}'
    [ "$status" -eq 0 ]
}

@test "route 超 TTL → 重新拦截并刷新" {
    mkdir -p "$HOME/.claude/mem-state"
    echo "test-session-001|assessed|1700000000" > "$HOME/.claude/mem-state/workflow-route"
    touch -d '5 hours ago' "$HOME/.claude/mem-state/workflow-route"
    run bash "$HOOK" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 2 ]
    # 过期 route 被拦截路径重写为当前 session（mtime 刷新）
    grep -q "test-session-001" "$HOME/.claude/mem-state/workflow-route"
    ! grep -q "assessed" "$HOME/.claude/mem-state/workflow-route"
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
    [ ! -f "$HOME/.claude/mem-state/workflow-route" ]
}

@test "Bash 无写入重定向 → 不拦截" {
    run bash "$HOOK" "Bash" '{"command":"echo hello"}'
    [ "$status" -eq 0 ]
}

@test "Bash 有写入重定向 → 拦截" {
    run bash "$HOOK" "Bash" '{"command":"echo hello > /tmp/out.txt"}'
    [ "$status" -eq 2 ]
}

@test "无 .devflow/ 目录 → 跳过" {
    rm -rf "$TEST_DIR/.devflow"
    run bash "$HOOK" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 0 ]
}
