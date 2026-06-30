# -*- bats -*-
# 回归测试: chmod glob 不创建字面量文件（R1 #7 / R2 #8）

setup() {
    TEST_DIR=$(mktemp -d)
}

teardown() {
    [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
}

@test "chmod glob on empty dir does not create literal *.py file" {
    cd "$TEST_DIR"
    # 模拟: 在空目录执行 chmod +x *.py 不应创建字面量 *.py 文件
    local before=$(ls -1 | wc -l)
    for f in *.py; do [ -f "$f" ] && chmod +x "$f"; done 2>/dev/null || true
    local after=$(ls -1 | wc -l)
    [ "$before" -eq "$after" ]
    [ ! -f "$TEST_DIR/*.py" ]
}

@test "chmod glob with existing .py files sets permissions" {
    cd "$TEST_DIR"
    echo "print(1)" > test1.py
    echo "print(2)" > test2.py
    for f in *.py; do [ -f "$f" ] && chmod +x "$f"; done
    [ -x "$TEST_DIR/test1.py" ]
    [ -x "$TEST_DIR/test2.py" ]
}

@test "update mode: chmod checks file existence per-file" {
    cd "$TEST_DIR"
    echo "print(1)" > existing.py
    for f in existing.py missing.py; do [ -f "$f" ] && chmod +x "$f" || true; done
    [ -x "$TEST_DIR/existing.py" ]
    [ ! -f "$TEST_DIR/missing.py" ]
}
