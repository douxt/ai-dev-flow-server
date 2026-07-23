# -*- bats -*-
# 集成测试: 逃生机制 — ~/.claude/.emergency-bypass 全 hook 放行

setup() {
    REPO_ROOT="${REPO_ROOT:-$(cd "$BATS_TEST_DIRNAME/../.." && pwd)}"
    TEST_HOME=$(mktemp -d)
    TEST_PROJECT="$TEST_HOME/project"
    mkdir -p "$TEST_PROJECT"
    cd "$TEST_PROJECT"
    git init
    git config user.email "test@devflow.test"
    git config user.name "DevFlow Test"
    BYPASS_WT_CHECK=1 git commit --allow-empty -m "init"
    export HOME="$TEST_HOME"

    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    export WORKSPACE="$TEST_PROJECT"
    export CC_SESSION_ID="escape-test"
    mkdir -p "$TEST_PROJECT/.devflow"
    HOOK_DIR="$HOME/.claude/hooks"
    BYPASS="$HOME/.claude/.emergency-bypass"
}

teardown() {
    [ -n "${TEST_HOME:-}" ] && [ -d "$TEST_HOME" ] && rm -rf "$TEST_HOME"
}

@test "escape: 逃生文件存在 → workflow-gate 放行（无 route 也不拦截）" {
    mkdir -p "$HOME/.claude"
    touch "$BYPASS"

    run bash "$HOOK_DIR/workflow-gate.sh" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 0 ]
    [ ! -f "$TEST_PROJECT/.workflow-route" ]
}

@test "escape: 逃生文件存在 → workflow-gate 放行（Bash 写入重定向）" {
    mkdir -p "$HOME/.claude"
    touch "$BYPASS"

    run bash "$HOOK_DIR/workflow-gate.sh" "Bash" '{"command":"echo hello > /tmp/out.txt"}'
    [ "$status" -eq 0 ]
}

@test "escape: 逃生文件不存在 → workflow-gate 正常拦截" {
    rm -f "$BYPASS"

    run bash "$HOOK_DIR/workflow-gate.sh" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 1 ]
    [[ "$output" =~ workflow-gate ]]
}

@test "escape: 逃生文件创建后立即生效" {
    rm -f "$BYPASS"
    run bash "$HOOK_DIR/workflow-gate.sh" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 1 ]

    mkdir -p "$HOME/.claude"
    touch "$BYPASS"

    run bash "$HOOK_DIR/workflow-gate.sh" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 0 ]
}

@test "escape: 逃生文件删除后恢复拦截" {
    mkdir -p "$HOME/.claude"
    touch "$BYPASS"
    run bash "$HOOK_DIR/workflow-gate.sh" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 0 ]

    rm -f "$BYPASS"
    rm -f "$TEST_PROJECT/.workflow-route"
    run bash "$HOOK_DIR/workflow-gate.sh" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 1 ]
}

@test "escape: 所有修改类工具均放行（Edit + Write + Bash 写入）" {
    mkdir -p "$HOME/.claude"
    touch "$BYPASS"

    run bash "$HOOK_DIR/workflow-gate.sh" "Edit" '{"file_path":"/tmp/test.txt","old_string":"a","new_string":"b"}'
    [ "$status" -eq 0 ]

    run bash "$HOOK_DIR/workflow-gate.sh" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 0 ]

    run bash "$HOOK_DIR/workflow-gate.sh" "Bash" '{"command":"sed -i s/old/new/ /tmp/f.txt"}'
    [ "$status" -eq 0 ]
}

@test "escape: stage-tracker 在逃生模式下行为不变" {
    mkdir -p "$TEST_PROJECT/.devflow/scripts"
    cp -f "$REPO_ROOT/scripts/trace.sh" "$TEST_PROJECT/.devflow/scripts/trace.sh"
    chmod +x "$TEST_PROJECT/.devflow/scripts/trace.sh"

    echo "# Escape Spec" > "$TEST_PROJECT/spec.md"
    run bash "$HOOK_DIR/stage-tracker.sh" "Write" '{"file_path":"/tmp/spec.md"}'
    [ "$status" -eq 0 ]
    [ "$(cat "$TEST_PROJECT/.devflow/stage")" = "spec:done" ]
}
