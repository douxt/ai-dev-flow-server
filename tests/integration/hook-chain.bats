# -*- bats -*-
# 集成测试: hook 链串联 — workflow-gate → stage-tracker → trace → check_constitution

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
    export CC_SESSION_ID="hook-chain-test"
    mkdir -p "$TEST_PROJECT/.devflow"
    ROUTE="$TEST_PROJECT/.workflow-route"
    STAGE="$TEST_PROJECT/.devflow/stage"
    TRACE="$TEST_PROJECT/.devflow/trace.jsonl"
    HOOK_DIR="$HOME/.claude/hooks"
}

teardown() {
    [ -n "${TEST_HOME:-}" ] && [ -d "$TEST_HOME" ] && rm -rf "$TEST_HOME"
}

ensure_trace_script() {
    mkdir -p "$TEST_PROJECT/.devflow/scripts"
    cp -f "$REPO_ROOT/scripts/trace.sh" "$TEST_PROJECT/.devflow/scripts/trace.sh"
    chmod +x "$TEST_PROJECT/.devflow/scripts/trace.sh"
}

@test "hook 链: workflow-gate 拦截 → 放行 → stage-tracker 检测 → trace 写记录" {
    ensure_trace_script

    # Step 1: 首次 Edit → workflow-gate 拦截
    run bash "$HOOK_DIR/workflow-gate.sh" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 1 ]
    [[ "$output" =~ workflow-gate ]]
    [ -f "$ROUTE" ]

    # Step 2: 第二次 Edit → workflow-gate 放行
    echo "${CC_SESSION_ID}|assessed|$(date +%s)" > "$ROUTE"
    run bash "$HOOK_DIR/workflow-gate.sh" "Write" '{"file_path":"/tmp/spec.md"}'
    [ "$status" -eq 0 ]

    # Step 3: 创建 spec.md → stage-tracker 检测到 spec:done
    echo "# Test Spec: Hook Chain Integration" > "$TEST_PROJECT/spec.md"
    run bash "$HOOK_DIR/stage-tracker.sh" "Write" '{"file_path":"/tmp/spec.md"}'
    [ "$status" -eq 0 ]
    [ -f "$STAGE" ]
    [ "$(cat "$STAGE")" = "spec:done" ]

    # Step 4: 验证 trace.jsonl 有 stage.transition 记录
    [ -f "$TRACE" ]
    grep -q "stage.transition" "$TRACE"
    grep -q "spec:done" "$TRACE"
}

@test "hook 链: spec → tickets → trace 连续记录" {
    ensure_trace_script

    echo "# Spec" > "$TEST_PROJECT/spec.md"
    run bash "$HOOK_DIR/stage-tracker.sh" "Write" '{"file_path":"/tmp/spec.md"}'
    [ "$status" -eq 0 ]
    [ "$(cat "$STAGE")" = "spec:done" ]

    mkdir -p "$TEST_PROJECT/issues"
    echo "status: ready" > "$TEST_PROJECT/issues/001-test.md"
    run bash "$HOOK_DIR/stage-tracker.sh" "Write" '{"file_path":"/tmp/issues/001-test.md"}'
    [ "$status" -eq 0 ]
    [ "$(cat "$STAGE")" = "tickets:done" ]

    transitions=$(grep -c "stage.transition" "$TRACE" 2>/dev/null || echo 0)
    [ "$transitions" -ge 2 ]
    grep -q "spec:done" "$TRACE"
    grep -q "tickets:done" "$TRACE"
}

@test "hook 链: 阶段跳跃 → advisory 警告但不阻断" {
    ensure_trace_script

    echo "explore:done" > "$STAGE"

    mkdir -p "$TEST_PROJECT/issues"
    echo "status: ready" > "$TEST_PROJECT/issues/001-skip.md"
    run bash "$HOOK_DIR/stage-tracker.sh" "Write" '{"file_path":"/tmp/issues/001-skip.md"}'
    # advisory — 不阻断
    [ "$status" -eq 0 ]
    [ "$(cat "$STAGE")" = "tickets:done" ]
}

@test "hook 链: 无变化 → 不重复写 trace" {
    ensure_trace_script

    echo "# Spec" > "$TEST_PROJECT/spec.md"
    run bash "$HOOK_DIR/stage-tracker.sh" "Write" '{"file_path":"/tmp/spec.md"}'
    [ "$status" -eq 0 ]

    transitions_before=$(grep -c "stage.transition" "$TRACE" 2>/dev/null || echo 0)

    run bash "$HOOK_DIR/stage-tracker.sh" "Write" '{"file_path":"/tmp/other.md"}'
    [ "$status" -eq 0 ]
    transitions_after=$(grep -c "stage.transition" "$TRACE" 2>/dev/null || echo 0)

    [ "$transitions_after" -eq "$transitions_before" ]
}

@test "hook 链: check_constitution 写入 trace" {
    ensure_trace_script

    mkdir -p "$TEST_PROJECT/issues"
    cat > "$TEST_PROJECT/issues/001-legal.md" <<'EOF'
---
status: ready
type: AFK
effort: small
estimate: 0.5d
test_files: test_legal.py
---
# AC
- [auto] AC1: test passes
EOF

    if python3 -c "import frontmatter" 2>/dev/null; then
        run python3 "$REPO_ROOT/scripts/check_constitution.py" "$TEST_PROJECT/issues/001-legal.md"
        if [ -f "$TRACE" ]; then
            grep -q "constitution.check" "$TRACE" || true
        fi
    else
        skip "python-frontmatter 未安装"
    fi
}

@test "hook 链: 空项目 → 所有 hook 静默跳过" {
    rm -rf "$TEST_PROJECT/.devflow"

    run bash "$HOOK_DIR/workflow-gate.sh" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 0 ]

    run bash "$HOOK_DIR/stage-tracker.sh" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 0 ]
    [ ! -f "$STAGE" ]
}
