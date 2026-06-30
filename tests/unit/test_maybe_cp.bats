# -*- bats -*-
# 测试 maybe_cp / maybe_cp_dir / maybe_mkdir

setup() {
    source /code/install.sh
    TEST_DIR=$(mktemp -d)
    SRC_DIR="$TEST_DIR/src"
    DST_DIR="$TEST_DIR/dst"
    mkdir -p "$SRC_DIR" "$DST_DIR"
    FORCE=false
    DRY_RUN=false
}

teardown() {
    [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
}

@test "maybe_cp: first copy creates file" {
    echo "hello" > "$SRC_DIR/test.txt"
    run maybe_cp "$SRC_DIR/test.txt" "$DST_DIR/test.txt"
    [ "$status" -eq 0 ]
    [ -f "$DST_DIR/test.txt" ]
}

@test "maybe_cp: second copy skips without --force" {
    echo "hello" > "$SRC_DIR/test.txt"
    maybe_cp "$SRC_DIR/test.txt" "$DST_DIR/test.txt"
    run maybe_cp "$SRC_DIR/test.txt" "$DST_DIR/test.txt"
    [ "$status" -eq 0 ]
    [[ "$output" =~ 跳过 ]]
}

@test "maybe_cp: --force overwrites existing" {
    echo "v1" > "$SRC_DIR/test.txt"
    echo "old" > "$DST_DIR/test.txt"
    FORCE=true
    run maybe_cp "$SRC_DIR/test.txt" "$DST_DIR/test.txt"
    [ "$status" -eq 0 ]
    [ "$(cat "$DST_DIR/test.txt")" = "v1" ]
}

@test "maybe_cp_dir: copies multiple files" {
    echo "a" > "$SRC_DIR/a.txt"
    echo "b" > "$SRC_DIR/b.txt"
    run maybe_cp_dir "$SRC_DIR" "$DST_DIR"
    [ "$status" -eq 0 ]
    [ -f "$DST_DIR/a.txt" ]
    [ -f "$DST_DIR/b.txt" ]
}

@test "maybe_mkdir: idempotent" {
    run maybe_mkdir "$TEST_DIR/sub"
    [ "$status" -eq 0 ]
    [ -d "$TEST_DIR/sub" ]
    run maybe_mkdir "$TEST_DIR/sub"
    [ "$status" -eq 0 ]
}
