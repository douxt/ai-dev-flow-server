# -*- bats -*-
# merge-settings.py hooks 聚合去重回归（UMES3 问题五：同 matcher 多组三胞胎折叠）
# 真根因=模板/自定义 matcher 同名多组未聚合 → existing 被复制成 N 组（2026-09-02 实测）

setup() {
    REPO_ROOT="${REPO_ROOT:-$(git -C "$BATS_TEST_DIRNAME/../.." rev-parse --show-toplevel 2>/dev/null || pwd)}"
    MS="$REPO_ROOT/scripts/merge-settings.py"
    TEST_DIR=$(mktemp -d)
    command -v python3 >/dev/null || skip "python3 不可用"
}

teardown() {
    [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
}

# 生成 JSON 的 python helper
gen() { # gen <file> <python表达式字符串构造 dict>
    python3 -c "import json,sys; json.dump($2, open(sys.argv[1],'w'))" "$TEST_DIR/$1"
}

run_merge() { # run_merge <existing> <template> → 输出 json 到 stdout
    python3 "$MS" "$TEST_DIR/$1" "$TEST_DIR/$2" "$TEST_DIR/out.json" && cat "$TEST_DIR/out.json"
}

hook() { echo '{"type":"command","command":"bash /h/'$1'.sh"}'; }

@test "同 matcher 三胞胎 3 组 → 折叠为 1 组且 basename 唯一" {
    gen ex.json "{'hooks':{'PostToolUse':[{'matcher':'Edit|Write','hooks':[$(hook a),$(hook b),$(hook c)]}]*3}]}}"
    gen tpl.json "{'hooks':{'PostToolUse':[{'matcher':'Edit|Write','hooks':[$(hook a),$(hook b),$(hook c)]}]}}
"
    run run_merge ex.json tpl.json
    [ "$status" -eq 0 ]
    groups=$(echo "$output" | python3 -c "import json,sys; d=json.load(sys.stdin); print(sum(1 for g in d['hooks']['PostToolUse'] if g['matcher']=='Edit|Write'))")
    hooks=$(echo "$output" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len([g for g in d['hooks']['PostToolUse'] if g['matcher']=='Edit|Write'][0]['hooks']))")
    [ "$groups" = "1" ]
    [ "$hooks" = "3" ]
}

@test "模板同 matcher 多组（3 组 Edit|Write）→ 输出 1 组含全部模板 hook" {
    gen ex.json "{'hooks':{'PostToolUse':[{'matcher':'Edit|Write','hooks':[$(hook a)]}]}]}"
    gen tpl.json "{'hooks':{'PostToolUse':[{'matcher':'Edit|Write','hooks':[$(hook x)]},{'matcher':'Edit|Write','hooks':[$(hook y)]},{'matcher':'Edit|Write','hooks':[$(hook z)]}]}}
"
    run run_merge ex.json tpl.json
    [ "$status" -eq 0 ]
    out=$(echo "$output" | python3 -c "
import json,sys
d=json.load(sys.stdin)
gws=[g for g in d['hooks']['PostToolUse'] if g['matcher']=='Edit|Write']
assert len(gws)==1, f'组数 {len(gws)}'
bns=sorted(__import__('os').path.basename(h['command']) for h in gws[0]['hooks'])
assert bns==['a.sh','x.sh','y.sh','z.sh'], bns
print('OK')")
    [ "$out" = "OK" ]
}

@test "自定义 matcher（模板无）挂多组重复 → 聚合成 1 组去重" {
    gen ex.json "{'hooks':{'PostToolUse':[{'matcher':'Edit|MultiEdit','hooks':[$(hook a),$(hook b)]},{'matcher':'Edit|MultiEdit','hooks':[$(hook a),$(hook b)]}]}}"
    gen tpl.json "{'hooks':{'PostToolUse':[{'matcher':'Edit|Write','hooks':[$(hook t)]}]}}
"
    run run_merge ex.json tpl.json
    [ "$status" -eq 0 ]
    out=$(echo "$output" | python3 -c "
import json,sys
d=json.load(sys.stdin)
gws=[g for g in d['hooks']['PostToolUse'] if g['matcher']=='Edit|MultiEdit']
assert len(gws)==1 and len(gws[0]['hooks'])==2, [len(gws), map(len,[g['hooks'] for g in gws])]
print('OK')")
    [ "$out" = "OK" ]
}

@test "既有语义回归：用户 hook 保留原位，模板新增插首位" {
    gen ex.json "{'hooks':{'PostToolUse':[{'matcher':'Edit|Write','hooks':[$(hook u1)]}]}}"
    gen tpl.json "{'hooks':{'PostToolUse':[{'matcher':'Edit|Write','hooks':[$(hook t1),$(hook t2)]}]}}
"
    run run_merge ex.json tpl.json
    out=$(echo "$output" | python3 -c "
import json,sys,os
d=json.load(sys.stdin)
hs=[os.path.basename(h['command']) for h in d['hooks']['PostToolUse'][0]['hooks']]
assert hs==['t1.sh','t2.sh','u1.sh'], hs   # 模板新增在前，用户原位在后
print('OK')")
    [ "$out" = "OK" ]
}
