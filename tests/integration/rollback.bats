# -*- bats -*-
# 集成测试: 回滚验证 — --update 后可恢复 v2.1 状态

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

@test "rollback: gate-state 备份可恢复原始内容" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full

    cat > "$TEST_PROJECT/.gate-state" <<'EOF'
gate-1: passed
gate-2: passed
gate-3: passed
EOF
    cp "$TEST_PROJECT/.gate-state" "$TEST_PROJECT/.gate-state.expected"

    run bash "$MIGRATE" "$TEST_PROJECT"
    [ "$status" -eq 0 ]

    [ -f "$TEST_PROJECT/.gate-state.v2.bak" ]
    diff "$TEST_PROJECT/.gate-state.expected" "$TEST_PROJECT/.gate-state.v2.bak"

    # 模拟回滚
    cp "$TEST_PROJECT/.gate-state.v2.bak" "$TEST_PROJECT/.gate-state.restored"
    diff "$TEST_PROJECT/.gate-state.expected" "$TEST_PROJECT/.gate-state.restored"
}

@test "rollback: 重复迁移覆盖旧备份" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full

    cat > "$TEST_PROJECT/.gate-state" <<'EOF'
gate-1: passed
EOF
    run bash "$MIGRATE" "$TEST_PROJECT"
    [ "$status" -eq 0 ]

    # 重置 gate-state
    cat > "$TEST_PROJECT/.gate-state" <<'EOF'
gate-1: passed
gate-2: passed
gate-3: passed
EOF
    rm -f "$TEST_PROJECT/.devflow/stage"

    run bash "$MIGRATE" "$TEST_PROJECT"
    [ "$status" -eq 0 ]

    grep -q "gate-3" "$TEST_PROJECT/.gate-state.v2.bak"
}

@test "rollback: .devflow/stage 删除后重新迁移正确还原" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full

    cat > "$TEST_PROJECT/.gate-state" <<'EOF'
gate-1: passed
gate-2: passed
gate-3: passed
gate-4: passed
EOF

    run bash "$MIGRATE" "$TEST_PROJECT"
    [ "$status" -eq 0 ]
    [ "$(cat "$TEST_PROJECT/.devflow/stage")" = "tickets:done" ]

    rm -f "$TEST_PROJECT/.devflow/stage"

    run bash "$MIGRATE" "$TEST_PROJECT"
    [ "$status" -eq 0 ]
    [ "$(cat "$TEST_PROJECT/.devflow/stage")" = "tickets:done" ]
}

@test "rollback: 迁移不删除原始 gate-state" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full

    cat > "$TEST_PROJECT/.gate-state" <<'EOF'
gate-1: passed
EOF

    run bash "$MIGRATE" "$TEST_PROJECT"
    [ "$status" -eq 0 ]

    [ -f "$TEST_PROJECT/.gate-state" ]
}

@test "rollback: --update 不破坏已安装 hook 文件" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full

    [ -f "$HOME/.claude/hooks/workflow-gate.sh" ]
    hook_checksum_before=$(sha256sum "$HOME/.claude/hooks/workflow-gate.sh" | cut -d' ' -f1)

    run bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --update
    [ "$status" -eq 0 ]

    hook_checksum_after=$(sha256sum "$HOME/.claude/hooks/workflow-gate.sh" | cut -d' ' -f1)
    [ "$hook_checksum_before" = "$hook_checksum_after" ]
}

@test "rollback: trace.jsonl migration 记录可审计" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full

    cat > "$TEST_PROJECT/.gate-state" <<'EOF'
gate-1: passed
gate-2: passed
EOF

    run bash "$MIGRATE" "$TEST_PROJECT"
    [ "$status" -eq 0 ]

    TRACE="$TEST_PROJECT/.devflow/trace.jsonl"
    [ -f "$TRACE" ]
    migration_event=$(grep "migration.v2_to_v3" "$TRACE" | tail -1)
    [[ "$migration_event" =~ "gate-state" ]]
    [[ "$migration_event" =~ "backup" ]]
}
