# -*- bats -*-
# 单元测试: stage-verify.sh — 阶段推进前产物质量验证（stub 依赖）

setup() {
    REPO_ROOT="${REPO_ROOT:-$(cd "$BATS_TEST_DIRNAME/../.." && pwd)}"
    TEST_DIR=$(mktemp -d)
    export WORKSPACE="$TEST_DIR"
    mkdir -p "$TEST_DIR/.devflow/scripts" "$TEST_DIR/issues"
    # 复制被测脚本
    cp "$REPO_ROOT/scripts/stage-verify.sh" "$TEST_DIR/.devflow/scripts/"
    chmod +x "$TEST_DIR/.devflow/scripts/stage-verify.sh"
    VERIFY="$TEST_DIR/.devflow/scripts/stage-verify.sh"
    cd "$TEST_DIR"
    # git init（implement:done 需要）
    git init -q
    git config user.email "t@t"
    git config user.name "T"
}

teardown() {
    [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
}

# helper: stub check_constitution.py
stub_constitution() {
    local exit_code="$1"
    cat > "$TEST_DIR/.devflow/scripts/check_constitution.py" <<EOF
#!/usr/bin/env python3
import sys; sys.exit($exit_code)
EOF
    chmod +x "$TEST_DIR/.devflow/scripts/check_constitution.py"
}

# helper: stub test-gate.sh
stub_test_gate() {
    local exit_code="$1"
    cat > "$TEST_DIR/.devflow/scripts/test-gate.sh" <<EOF
#!/bin/bash
exit $exit_code
EOF
    chmod +x "$TEST_DIR/.devflow/scripts/test-gate.sh"
}

# helper: stub green-gate.sh
stub_green_gate() {
    local exit_code="$1"
    cat > "$TEST_DIR/.devflow/scripts/green-gate.sh" <<EOF
#!/bin/bash
exit $exit_code
EOF
    chmod +x "$TEST_DIR/.devflow/scripts/green-gate.sh"
}

# ═══════════════════════════════════════
# spec:done
# ═══════════════════════════════════════

@test "spec:done — 完整 spec → pass" {
    cat > "$TEST_DIR/spec.md" <<'MD'
## Testing
## Risks & Mitigations
| AC-01 | test | L1 | [auto] | desc | 1h |
MD
    run bash "$VERIFY" "spec:done"
    [ "$status" -eq 0 ]
    [[ "$output" == *"S1 non-empty: PASS"* ]]
    [[ "$output" == *"S2 sections"*"PASS"* ]]
}

@test "spec:done — 缺 Testing 段 → fail" {
    cat > "$TEST_DIR/spec.md" <<'MD'
## Risks & Mitigations
| AC-01 | test |
MD
    run bash "$VERIFY" "spec:done"
    [ "$status" -eq 1 ]
    [[ "$output" == *"S2 sections"*"FAIL"* ]]
}

@test "spec:done — 空文件 → fail" {
    touch "$TEST_DIR/spec.md"
    run bash "$VERIFY" "spec:done"
    [ "$status" -eq 1 ]
    [[ "$output" == *"S1 non-empty: FAIL"* ]]
}

# ═══════════════════════════════════════
# tickets:done
# ═══════════════════════════════════════

@test "tickets:done — constitution 全绿 → pass" {
    stub_constitution 0
    run bash "$VERIFY" "tickets:done"
    [ "$status" -eq 0 ]
    [[ "$output" == *"T1 constitution: PASS"* ]]
}

@test "tickets:done — constitution 失败 → fail" {
    stub_constitution 1
    run bash "$VERIFY" "tickets:done"
    [ "$status" -eq 1 ]
    [[ "$output" == *"T1 constitution: FAIL"* ]]
}

@test "tickets:done — 脚本缺失 → fail-open" {
    run bash "$VERIFY" "tickets:done"
    [ "$status" -eq 0 ]
    [[ "$output" == *"T1 constitution: PASS"*"跳过"* ]]
}

# ═══════════════════════════════════════
# tickets:reviewed
# ═══════════════════════════════════════

@test "tickets:reviewed — failed=0 → pass" {
    echo '{"total_failed":0,"scanned":1}' > "$TEST_DIR/.devflow/constitution-report.json"
    run bash "$VERIFY" "tickets:reviewed"
    [ "$status" -eq 0 ]
    [[ "$output" == *"R2 failed=0: PASS"* ]]
}

@test "tickets:reviewed — failed=2 → fail" {
    echo '{"total_failed":2,"scanned":1}' > "$TEST_DIR/.devflow/constitution-report.json"
    run bash "$VERIFY" "tickets:reviewed"
    [ "$status" -eq 1 ]
    [[ "$output" == *"R2 failed=2: FAIL"* ]]
}

@test "tickets:reviewed — 报告缺失 → fail" {
    run bash "$VERIFY" "tickets:reviewed"
    [ "$status" -eq 1 ]
    [[ "$output" == *"R1 report exists: FAIL"* ]]
}

@test "tickets:reviewed — 报告过期 → fail" {
    echo '{"total_failed":0,"scanned":1}' > "$TEST_DIR/.devflow/constitution-report.json"
    sleep 0.1
    echo "# new issue" > "$TEST_DIR/issues/new.md"
    run bash "$VERIFY" "tickets:reviewed"
    [ "$status" -eq 1 ]
    [[ "$output" == *"R3 staleness: FAIL"* ]]
}

@test "tickets:reviewed — 数量不一致 → fail" {
    echo '{"total_failed":0,"scanned":2}' > "$TEST_DIR/.devflow/constitution-report.json"
    run bash "$VERIFY" "tickets:reviewed"
    [ "$status" -eq 1 ]
    [[ "$output" == *"R4 count"*"FAIL"* ]]
}

# ═══════════════════════════════════════
# tdd:done
# ═══════════════════════════════════════

@test "tdd:done — test-gate 全绿 → pass" {
    stub_test_gate 0
    run bash "$VERIFY" "tdd:done"
    [ "$status" -eq 0 ]
    [[ "$output" == *"D1 test-gate: PASS"* ]]
}

@test "tdd:done — test-gate 失败 → fail" {
    stub_test_gate 1
    run bash "$VERIFY" "tdd:done"
    [ "$status" -eq 1 ]
    [[ "$output" == *"D1 test-gate: FAIL"* ]]
}

# ═══════════════════════════════════════
# implement:done
# ═══════════════════════════════════════

@test "implement:done — RED commit 存在 + stubs 全绿 → pass" {
    echo "// stub" > x.js && git add -A && git commit -q -m "TDD: RED — t1"
    stub_green_gate 0
    stub_test_gate 0
    run bash "$VERIFY" "implement:done"
    [ "$status" -eq 0 ]
    [[ "$output" == *"I1 RED commit: PASS"* ]]
    [[ "$output" == *"I2 green-gate: PASS"* ]]
}

@test "implement:done — 无 RED commit → fail" {
    stub_green_gate 0
    stub_test_gate 0
    run bash "$VERIFY" "implement:done"
    [ "$status" -eq 1 ]
    [[ "$output" == *"I1 RED commit: FAIL"* ]]
}

# ═══════════════════════════════════════
# 通用
# ═══════════════════════════════════════

@test "BYPASS → exit 0" {
    STAGE_VERIFY_BYPASS=1 run bash "$VERIFY" "spec:done" "tickets:done"
    [ "$status" -eq 0 ]
    [[ "$output" == *"跳过所有验证"* ]]
}

@test "多阶段串联 → 任一 fail 则 exit 1" {
    # spec pass, tickets fail
    cat > "$TEST_DIR/spec.md" <<'MD'
## Testing
## Risks & Mitigations
| AC-01 |
MD
    stub_constitution 1
    run bash "$VERIFY" "spec:done" "tickets:done"
    [ "$status" -eq 1 ]
    [[ "$output" == *"S2 sections"*"PASS"* ]]
    [[ "$output" == *"T1 constitution: FAIL"* ]]
}
