# -*- bats -*-
# 单元测试: stage-gate-block hook — 双层阻断（pre-tdd + GREEN 窗口）

setup() {
    REPO_ROOT="${REPO_ROOT:-$(cd "$BATS_TEST_DIRNAME/../.." && pwd)}"
    TEST_DIR=$(mktemp -d)
    export WORKSPACE="$TEST_DIR"
    mkdir -p "$TEST_DIR/.devflow"
    HOOK="$REPO_ROOT/config-templates/default/hooks/stage-gate-block.sh"
    # 初始化 git
    cd "$TEST_DIR"
    git init -q
    git config user.email "test@test"
    git config user.name "Test"
}

teardown() {
    [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
}

# helper: 做 RED commit
make_red() {
    echo "// test" > "$TEST_DIR/test.js"
    git add -A
    git commit -q -m "TDD: RED — ticket 001"
}

# helper: 做 GREEN commit
make_green() {
    echo "// impl" > "$TEST_DIR/src.js"
    git add -A
    git commit -q -m "GREEN: ticket 001"
}

# ═══════════════════════════════════════
# GREEN 窗口阻断（5.8 新增）
# ═══════════════════════════════════════

@test "GREEN: stage=tdd:done + RED commit → 写测试文件 exit 2" {
    echo "tdd:done" > "$TEST_DIR/.devflow/stage"
    make_red
    run bash "$HOOK" "Write" "{\"file_path\":\"$TEST_DIR/tests/foo.test.ts\"}"
    [ "$status" -eq 2 ]
    [[ "$output" == *"GREEN 阶段"* ]]
}

@test "GREEN: stage=tdd:done + RED commit → 写实现文件 exit 0" {
    echo "tdd:done" > "$TEST_DIR/.devflow/stage"
    make_red
    run bash "$HOOK" "Write" "{\"file_path\":\"$TEST_DIR/src/foo.ts\"}"
    [ "$status" -eq 0 ]
}

@test "GREEN: stage=tdd:done + RED commit → 写配置文件 exit 0" {
    echo "tdd:done" > "$TEST_DIR/.devflow/stage"
    make_red
    run bash "$HOOK" "Write" "{\"file_path\":\"$TEST_DIR/README.md\"}"
    [ "$status" -eq 0 ]
}

@test "GREEN: stage=tdd:done + RED commit → 写新测试文件 exit 2" {
    echo "tdd:done" > "$TEST_DIR/.devflow/stage"
    make_red
    run bash "$HOOK" "Edit" "{\"file_path\":\"$TEST_DIR/e2e/new.test.ts\"}"
    [ "$status" -eq 2 ]
}

@test "GREEN: stage=tdd:done + 非RED commit → 写测试文件 exit 0" {
    echo "tdd:done" > "$TEST_DIR/.devflow/stage"
    make_green
    run bash "$HOOK" "Write" "{\"file_path\":\"$TEST_DIR/tests/foo.test.ts\"}"
    [ "$status" -eq 0 ]
}

@test "GREEN: stage=tdd:done + 无git → 写测试文件 exit 0" {
    echo "tdd:done" > "$TEST_DIR/.devflow/stage"
    run bash "$HOOK" "Write" "{\"file_path\":\"$TEST_DIR/tests/foo.test.ts\"}"
    [ "$status" -eq 0 ]
}

@test "GREEN: stage=implement:done + RED commit → 写测试 exit 2" {
    echo "implement:done" > "$TEST_DIR/.devflow/stage"
    make_red
    run bash "$HOOK" "Write" "{\"file_path\":\"$TEST_DIR/tests/foo.test.ts\"}"
    [ "$status" -eq 2 ]
}

@test "GREEN: RED 非最后 commit → 写测试 exit 0" {
    echo "tdd:done" > "$TEST_DIR/.devflow/stage"
    make_red
    make_green
    run bash "$HOOK" "Write" "{\"file_path\":\"$TEST_DIR/tests/foo.test.ts\"}"
    [ "$status" -eq 0 ]
}

@test "GREEN: stage=tdd:done + RED → 写 fixtures exit 2" {
    echo "tdd:done" > "$TEST_DIR/.devflow/stage"
    make_red
    run bash "$HOOK" "Edit" "{\"file_path\":\"$TEST_DIR/tests/fixtures/data.json\"}"
    [ "$status" -eq 2 ]
}

@test "GREEN: stage=tdd:done + RED → 写 __snapshots__ exit 2" {
    echo "tdd:done" > "$TEST_DIR/.devflow/stage"
    make_red
    run bash "$HOOK" "Write" "{\"file_path\":\"$TEST_DIR/src/__snapshots__/x.snap\"}"
    [ "$status" -eq 2 ]
}

# ═══════════════════════════════════════
# Pre-tdd 回归（5.7 行为）
# ═══════════════════════════════════════

@test "PRE: stage=spec:done → 写实现 exit 2" {
    echo "spec:done" > "$TEST_DIR/.devflow/stage"
    run bash "$HOOK" "Write" "{\"file_path\":\"$TEST_DIR/src/a.ts\"}"
    [ "$status" -eq 2 ]
}

@test "PRE: stage=spec:done → 写测试 exit 0" {
    echo "spec:done" > "$TEST_DIR/.devflow/stage"
    run bash "$HOOK" "Write" "{\"file_path\":\"$TEST_DIR/tests/a.test.ts\"}"
    [ "$status" -eq 0 ]
}

@test "PRE: 无 .devflow/stage → exit 0" {
    rm -f "$TEST_DIR/.devflow/stage"
    run bash "$HOOK" "Write" "{\"file_path\":\"$TEST_DIR/src/a.ts\"}"
    [ "$status" -eq 0 ]
}

@test "PRE: stage=spec:done + RED commit → 写实现 exit 2（pre-tdd 优先）" {
    echo "spec:done" > "$TEST_DIR/.devflow/stage"
    make_red
    run bash "$HOOK" "Write" "{\"file_path\":\"$TEST_DIR/src/a.ts\"}"
    [ "$status" -eq 2 ]
}

@test "PRE: 未知 stage + RED commit → 写实现 exit 2" {
    echo "unknown_stage" > "$TEST_DIR/.devflow/stage"
    make_red
    run bash "$HOOK" "Write" "{\"file_path\":\"$TEST_DIR/src/a.ts\"}"
    [ "$status" -eq 2 ]
}

@test "Bash 工具 → exit 0（不拦截）" {
    echo "spec:done" > "$TEST_DIR/.devflow/stage"
    make_red
    run bash "$HOOK" "Bash" '{"command":"echo hi"}'
    [ "$status" -eq 0 ]
}
