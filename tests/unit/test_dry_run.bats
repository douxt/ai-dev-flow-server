# -*- bats -*-
# 测试 dry_run 模式

setup() {
    source /code/install.sh
    TEST_DIR=$(mktemp -d)
}

teardown() {
    [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
}

@test "DRY_RUN=true: dry_run does not execute" {
    DRY_RUN=true
    run dry_run "touch $TEST_DIR/should_not_exist"
    [ "$status" -eq 0 ]
    [ ! -f "$TEST_DIR/should_not_exist" ]
}

@test "DRY_RUN=true: maybe_cp only prints dry-run message" {
    DRY_RUN=true
    echo "x" > "$TEST_DIR/src"
    run maybe_cp "$TEST_DIR/src" "$TEST_DIR/dst"
    [ "$status" -eq 0 ]
    [[ "$output" =~ DRY-RUN ]]
    [ ! -f "$TEST_DIR/dst" ]
}

@test "DRY_RUN=false: normal write works" {
    DRY_RUN=false
    echo "x" > "$TEST_DIR/src"
    run maybe_cp "$TEST_DIR/src" "$TEST_DIR/dst"
    [ "$status" -eq 0 ]
    [ -f "$TEST_DIR/dst" ]
}
