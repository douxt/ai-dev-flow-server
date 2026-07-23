# -*- bats -*-
# 集成测试: v2.1 gate-state → v3.0 stage 迁移

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
}

teardown() {
    [ -n "${TEST_HOME:-}" ] && [ -d "$TEST_HOME" ] && rm -rf "$TEST_HOME"
}

MIGRATE="$REPO_ROOT/scripts/migrate-gate-state.sh"

@test "migrate: 无旧 gate-state → 静默跳过" {
    run bash "$MIGRATE" "$TEST_PROJECT"
    [ "$status" -eq 0 ]
    [ ! -f "$TEST_PROJECT/.gate-state.v2.bak" ]
    [ ! -f "$TEST_PROJECT/.devflow/stage" ]
}

@test "migrate: gate-3 passed → 映射为 tickets:done" {
    cat > "$TEST_PROJECT/.gate-state" <<'EOF'
project: test
gates:
  gate-1: { status: passed }
  gate-2: { status: passed }
  gate-3: { status: passed }
EOF

    run bash "$MIGRATE" "$TEST_PROJECT"
    [ "$status" -eq 0 ]
    [ -f "$TEST_PROJECT/.gate-state.v2.bak" ]
    [ -f "$TEST_PROJECT/.devflow/stage" ]
    [ "$(cat "$TEST_PROJECT/.devflow/stage")" = "tickets:done" ]
}

@test "migrate: gate-4 passed → 映射为 tickets:done" {
    cat > "$TEST_PROJECT/.gate-state" <<'EOF'
project: test
gates:
  gate-1: { status: passed }
  gate-2: { status: passed }
  gate-3: { status: passed }
  gate-4: { status: passed }
EOF

    run bash "$MIGRATE" "$TEST_PROJECT"
    [ "$status" -eq 0 ]
    [ "$(cat "$TEST_PROJECT/.devflow/stage")" = "tickets:done" ]
}

@test "migrate: gate-5 passed → 映射为 implement:done" {
    cat > "$TEST_PROJECT/.gate-state" <<'EOF'
project: test
gates:
  gate-1: { status: passed }
  gate-2: { status: passed }
  gate-3: { status: passed }
  gate-4: { status: passed }
  gate-5: { status: passed }
EOF

    run bash "$MIGRATE" "$TEST_PROJECT"
    [ "$status" -eq 0 ]
    [ "$(cat "$TEST_PROJECT/.devflow/stage")" = "implement:done" ]
}

@test "migrate: gate-6 passed → 映射为 implement:done" {
    cat > "$TEST_PROJECT/.gate-state" <<'EOF'
project: test
gates:
  gate-1: { status: passed }
  gate-2: { status: passed }
  gate-3: { status: passed }
  gate-4: { status: passed }
  gate-5: { status: passed }
  gate-6: { status: passed }
EOF

    run bash "$MIGRATE" "$TEST_PROJECT"
    [ "$status" -eq 0 ]
    [ "$(cat "$TEST_PROJECT/.devflow/stage")" = "implement:done" ]
}

@test "migrate: gate-1 passed → 映射为 explore:done" {
    cat > "$TEST_PROJECT/.gate-state" <<'EOF'
project: test
gates:
  gate-1: { status: passed }
EOF

    run bash "$MIGRATE" "$TEST_PROJECT"
    [ "$status" -eq 0 ]
    [ "$(cat "$TEST_PROJECT/.devflow/stage")" = "explore:done" ]
}

@test "migrate: gate-2 passed → 映射为 spec:done" {
    cat > "$TEST_PROJECT/.gate-state" <<'EOF'
project: test
gates:
  gate-1: { status: passed }
  gate-2: { status: passed }
EOF

    run bash "$MIGRATE" "$TEST_PROJECT"
    [ "$status" -eq 0 ]
    [ "$(cat "$TEST_PROJECT/.devflow/stage")" = "spec:done" ]
}

@test "migrate: 无 passed gate → 默认为 explore:done" {
    cat > "$TEST_PROJECT/.gate-state" <<'EOF'
project: test
gates:
  gate-1: { status: pending }
  gate-2: { status: pending }
EOF

    run bash "$MIGRATE" "$TEST_PROJECT"
    [ "$status" -eq 0 ]
    [ "$(cat "$TEST_PROJECT/.devflow/stage")" = "explore:done" ]
}

@test "migrate: 生成备份文件内容与原始一致" {
    cat > "$TEST_PROJECT/.gate-state" <<'EOF'
project: test
gates:
  gate-1: { status: passed }
  gate-2: { status: passed }
  gate-3: { status: passed }
  gate-4: { status: passed }
EOF

    run bash "$MIGRATE" "$TEST_PROJECT"
    [ "$status" -eq 0 ]
    [ -f "$TEST_PROJECT/.gate-state.v2.bak" ]
    diff "$TEST_PROJECT/.gate-state" "$TEST_PROJECT/.gate-state.v2.bak"
}

@test "migrate: trace.jsonl 写入 migration.v2_to_v3 事件" {
    cat > "$TEST_PROJECT/.gate-state" <<'EOF'
project: test
gates:
  gate-1: { status: passed }
  gate-2: { status: passed }
EOF

    run bash "$MIGRATE" "$TEST_PROJECT"
    [ "$status" -eq 0 ]

    TRACE="$TEST_PROJECT/.devflow/trace.jsonl"
    [ -f "$TRACE" ]
    grep -q "migration.v2_to_v3" "$TRACE"
    grep -q "gate-state" "$TRACE"
}

@test "migrate: 空 gate-state 文件 → 默认 explore:done" {
    echo "" > "$TEST_PROJECT/.gate-state"

    run bash "$MIGRATE" "$TEST_PROJECT"
    [ "$status" -eq 0 ]
    [ "$(cat "$TEST_PROJECT/.devflow/stage")" = "explore:done" ]
}

@test "migrate: 旧格式 gate-state（key: value）处理不崩溃" {
    cat > "$TEST_PROJECT/.gate-state" <<'EOF'
gate-1: passed
gate-2: passed
gate-3: passed
EOF

    run bash "$MIGRATE" "$TEST_PROJECT"
    [ "$status" -eq 0 ]
    [ -f "$TEST_PROJECT/.devflow/stage" ]
}

@test "migrate: --update 流程自动触发迁移" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    # 手动写旧版 gate-state
    cat > "$TEST_PROJECT/.gate-state" <<'EOF'
gate-1: passed
gate-2: passed
gate-3: passed
gate-4: passed
EOF
    rm -f "$TEST_PROJECT/.devflow/stage"

    run bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --update
    [ "$status" -eq 0 ]
    [ -f "$TEST_PROJECT/.gate-state.v2.bak" ]
}
