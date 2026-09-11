# -*- bats -*-
# 单元测试: spec-gate hook — docs/specs 出口门禁（形式轴）+ check_constitution --spec 冒烟

setup() {
    REPO_ROOT="${REPO_ROOT:-$(cd "$BATS_TEST_DIRNAME/../.." && pwd)}"
    TEST_DIR=$(mktemp -d)
    export WORKSPACE="$TEST_DIR"
    HOOK="$REPO_ROOT/config-templates/default/hooks/spec-gate.sh"
    mkdir -p "$TEST_DIR/.devflow/scripts" "$TEST_DIR/docs/specs"
    cp "$REPO_ROOT/scripts/check_constitution.py" "$TEST_DIR/.devflow/scripts/"
    cp "$REPO_ROOT/scripts/trace.sh" "$TEST_DIR/.devflow/scripts/"
    printf 'warn\n' > "$TEST_DIR/.devflow/spec-gate-mode"
    : > "$TEST_DIR/.devflow/spec-gate-baseline"
    GOOD='# good
## Risks
- r1
- r2
- r3
- r4
- r5

- [x] [auto] AC1: 响应小于200ms

## Spec 质量宪法合规表

| # | 规则 | 状态 | 证据 |
|---|------|:----:|------|
| 1 | 章节完整 | ✅ | a |
| 2 | Risks | ✅ | b |
| 3 | 定量 AC | ✅ | c |
| 4 | 异常路径 | ✅ | d |
| 5 | 接口签名 | ✅ | e |
'
    BAD='# bad spec
没有任何宪法结构
'
}

teardown() {
    [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
}

# 真实 stdin 协议调用（与 settings 注册形态一致，无位置参数）
call_sg() {  # call_sg <rel_path> [session] → 设 SG_OUT/SG_RC
    SG_FILE="$TEST_DIR/$1"
    mkdir -p "$(dirname "$SG_FILE")"
    [ -f "$SG_FILE" ] || printf 'x\n' > "$SG_FILE"
    printf '{"tool_name":"Write","tool_input":{"file_path":"%s"},"session_id":"%s","cwd":"%s"}' \
        "$SG_FILE" "${2:-s1}" "$TEST_DIR" > "$TEST_DIR/.stdin.json"
    SG_OUT=$(bash "$HOOK" < "$TEST_DIR/.stdin.json" 2>"$TEST_DIR/.stderr.txt") && SG_RC=$? || SG_RC=$?
}

mk_and_call() {  # mk_and_call <content> <rel_path> [session]
    mkdir -p "$(dirname "$TEST_DIR/$2")"
    printf '%s' "$1" > "$TEST_DIR/$2"
    call_sg "$2" "${3:-s1}"
}

# ── 反向：warn/block ──

@test "warn: 无合规表 spec → stdout 含 additionalContext 缺项，exit 0，stderr 留空" {
    mk_and_call "$BAD" docs/specs/bad.md
    [ "$SG_RC" -eq 0 ]
    [[ "$SG_OUT" == *additionalContext* ]]
    [[ "$SG_OUT" == *"合规表"* ]]
    [ ! -s "$TEST_DIR/.stderr.txt" ]
}

@test "block: 无合规表 spec → exit 2，stderr 列缺项" {
    printf 'block\n' > "$TEST_DIR/.devflow/spec-gate-mode"
    mk_and_call "$BAD" docs/specs/bad.md
    [ "$SG_RC" -eq 2 ]
    grep -q "合规表" "$TEST_DIR/.stderr.txt"
}

@test "block: 连续 3 次 → stderr 含人工介入升级提示" {
    printf 'block\n' > "$TEST_DIR/.devflow/spec-gate-mode"
    mk_and_call "$BAD" docs/specs/bad.md
    mk_and_call "$BAD" docs/specs/bad.md
    mk_and_call "$BAD" docs/specs/bad.md
    [ "$SG_RC" -eq 2 ]
    grep -q "人工介入\|报告给人" "$TEST_DIR/.stderr.txt"
}

# ── 正向 ──

@test "pass: 合规 spec → rc 0 无输出，trace 有 spec-gate.pass 心跳" {
    mk_and_call "$GOOD" docs/specs/good.md
    [ "$SG_RC" -eq 0 ]
    [ -z "$SG_OUT" ]
    grep -q '"spec-gate.pass"' "$TEST_DIR/.devflow/trace.jsonl"
}

# ── 零干扰 ──

@test "零干扰: docs/references/*.md 不触发" {
    mk_and_call "$BAD" docs/references/note.md
    [ "$SG_RC" -eq 0 ]
    [ -z "$SG_OUT" ]
    grep -q "spec-gate" "$TEST_DIR/.devflow/trace.jsonl" && return 1
    true
}

@test "零干扰: docs/specs/*.txt 非 md 不触发" {
    mk_and_call "$BAD" docs/specs/notes.txt
    [ "$SG_RC" -eq 0 ]
    [ -z "$SG_OUT" ]
}

@test "零干扰: 无 .devflow 目录 → rc 0 静默" {
    printf 'y\n' > "$TEST_DIR/docs/specs/keep.md"
    printf '{"tool_name":"Write","tool_input":{"file_path":"%s/docs/specs/keep.md"},"session_id":"s1","cwd":"%s"}' \
        "$TEST_DIR" "$TEST_DIR" > "$TEST_DIR/.stdin.json"
    OUT2=$(WORKSPACE="$TEST_DIR/nosuch" bash "$HOOK" < "$TEST_DIR/.stdin.json") && RC2=$? || RC2=$?
    [ "$RC2" -eq 0 ]
    [ -z "$OUT2" ]
}

@test "零干扰: Bash 工具事件不处理" {
    printf '{"tool_name":"Bash","tool_input":{"command":"cat x"},"session_id":"s1","cwd":"%s"}' "$TEST_DIR" > "$TEST_DIR/.stdin.json"
    OUT2=$(bash "$HOOK" < "$TEST_DIR/.stdin.json") && RC2=$? || RC2=$?
    [ "$RC2" -eq 0 ]
    [ -z "$OUT2" ]
}

@test "零干扰: 路径含 .. 穿越段不处理" {
    mkdir -p "$TEST_DIR/docs/elsewhere"
    printf 'x\n' > "$TEST_DIR/docs/elsewhere/a.md"
    call_sg "docs/specs/../elsewhere/a.md"
    [ "$SG_RC" -eq 0 ]
    [ -z "$SG_OUT" ]
}

@test "递归: docs/specs 嵌套子目录新 md 被管" {
    mk_and_call "$BAD" docs/specs/sub/deep/bad.md
    [[ "$SG_OUT" == *additionalContext* ]]
}

# ── 豁免机制 ──

@test "基线豁免: 存量路径在 baseline 清单 → 静默" {
    printf 'docs/specs/legacy.md\n' >> "$TEST_DIR/.devflow/spec-gate-baseline"
    mk_and_call "$BAD" docs/specs/legacy.md
    [ "$SG_RC" -eq 0 ]
    [ -z "$SG_OUT" ]
    grep -q '"baseline"' "$TEST_DIR/.devflow/trace.jsonl"
}

@test "exclude 豁免: 人工清单路径 → 静默且留痕" {
    printf 'docs/specs/research.md\n' > "$TEST_DIR/.devflow/spec-gate-exclude"
    mk_and_call "$BAD" docs/specs/research.md
    [ "$SG_RC" -eq 0 ]
    [ -z "$SG_OUT" ]
    grep -q '"excluded"' "$TEST_DIR/.devflow/trace.jsonl"
}

@test "off 开关: 软停 → 静默但保留 skip 心跳" {
    printf 'off\n' > "$TEST_DIR/.devflow/spec-gate-mode"
    mk_and_call "$BAD" docs/specs/bad.md
    [ "$SG_RC" -eq 0 ]
    [ -z "$SG_OUT" ]
    grep -q '"reason":"off"' "$TEST_DIR/.devflow/trace.jsonl"
}

# ── 台账 ──

@test "台账: 同 session 同文件第 4 次 warn 封顶静默（session 独立）" {
    mk_and_call "$BAD" docs/specs/bad.md s1
    mk_and_call "$BAD" docs/specs/bad.md s1
    mk_and_call "$BAD" docs/specs/bad.md s1
    mk_and_call "$BAD" docs/specs/bad.md s1
    [ -z "$SG_OUT" ]
    mk_and_call "$BAD" docs/specs/bad.md s2
    [[ "$SG_OUT" == *additionalContext* ]]
}

# ── 降级契约：崩溃绝不解读为缺项 ──

@test "降级: checker 缺失 → rc 0 静默 + degraded 事件" {
    rm "$TEST_DIR/.devflow/scripts/check_constitution.py"
    mk_and_call "$BAD" docs/specs/bad.md
    [ "$SG_RC" -eq 0 ]
    [ -z "$SG_OUT" ]
    grep -q '"checker-missing"' "$TEST_DIR/.devflow/trace.jsonl"
}

@test "降级: 旧版 checker 无 --spec（rc=1 error JSON）→ 按形状判降级不误报" {
    printf '#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps({"file":sys.argv[1],"error":"文件不存在"}))\nsys.exit(1)\n' \
        > "$TEST_DIR/.devflow/scripts/check_constitution.py"
    chmod +x "$TEST_DIR/.devflow/scripts/check_constitution.py"
    mk_and_call "$BAD" docs/specs/bad.md
    [ "$SG_RC" -eq 0 ]
    [ -z "$SG_OUT" ]
    grep -q '"checker-no-spec-mode"' "$TEST_DIR/.devflow/trace.jsonl"
}

@test "降级: checker 崩溃 rc=3 → 静默放行 + degraded 事件" {
    printf 'import sys\nsys.exit(3)\n' > "$TEST_DIR/.devflow/scripts/check_constitution.py"
    chmod +x "$TEST_DIR/.devflow/scripts/check_constitution.py"
    mk_and_call "$BAD" docs/specs/bad.md
    [ "$SG_RC" -eq 0 ]
    grep -q '"checker-rc-3"' "$TEST_DIR/.devflow/trace.jsonl"
}

# ── check_constitution --spec 单元冒烟（含 frontmatter 懒导入）──

@test "checker --spec: 不存在的文件 → rc 2（内部错误与业务缺项分离）" {
    run python3 "$TEST_DIR/.devflow/scripts/check_constitution.py" --spec /nonexistent-spec.md
    [ "$status" -eq 2 ]
}

@test "checker --spec: 不依赖 frontmatter 包（懒导入生效）" {
    printf '%s' "$BAD" > "$TEST_DIR/docs/specs/probe.md"
    # 以假 frontmatter 模块抛 ImportError 屏蔽真包：spec 模式必须照常产出 mode:spec JSON
    mkdir -p "$TEST_DIR/.shadow"
    printf 'raise ImportError("blocked for test")\n' > "$TEST_DIR/.shadow/frontmatter.py"
    run env PYTHONPATH="$TEST_DIR/.shadow" python3 "$TEST_DIR/.devflow/scripts/check_constitution.py" --spec "$TEST_DIR/docs/specs/probe.md" --json
    [ "$status" -eq 1 ]
    [[ "$output" == *'"mode": "spec"'* ]]
    [[ "$output" == *"合规表"* ]]
}

@test "checker ticket 冒烟: 不存在的 ticket → rc 1 error JSON（ticket 路径未破坏）" {
    run python3 "$TEST_DIR/.devflow/scripts/check_constitution.py" /nonexistent-ticket.md
    [ "$status" -eq 1 ]
    [[ "$output" == *"文件不存在"* ]]
    [[ "$output" != *'"mode"'* ]]
}

@test "checker 冒烟: 无参数 → rc 1 usage，含 --spec 用法行" {
    run python3 "$TEST_DIR/.devflow/scripts/check_constitution.py"
    [ "$status" -eq 1 ]
    [[ "$output" == *"--spec"* ]]
}

# ── 串联共存：与 stage-gate 互不污染 ──

@test "串联: 同一 stdin 喂 stage-gate-block 与 spec-gate，各 rc 独立且 stage 文件不被污染" {
    printf '%s' "$GOOD" > "$TEST_DIR/docs/specs/good.md"
    printf 'spec:done\n' > "$TEST_DIR/.devflow/stage"
    JSON=$(printf '{"tool_name":"Write","tool_input":{"file_path":"%s/docs/specs/good.md"},"session_id":"s1","cwd":"%s"}' "$TEST_DIR" "$TEST_DIR")
    printf '%s' "$JSON" | bash "$REPO_ROOT/config-templates/default/hooks/stage-gate-block.sh" && RC1=0 || RC1=$?
    printf '%s' "$JSON" | bash "$HOOK" >/dev/null && RC2=0 || RC2=$?
    [ "$RC1" -eq 0 ]
    [ "$RC2" -eq 0 ]
    [ "$(cat "$TEST_DIR/.devflow/stage")" = "spec:done" ]
}
