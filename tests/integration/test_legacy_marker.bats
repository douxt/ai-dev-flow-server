# -*- bats -*-
# 集成测试: 旧标记识别 — 含旧标记的 CLAUDE.md 被识别为已安装并跳过

load /code/tests/helpers/common.bash

@test "install skips when old marker present in CLAUDE.md" {
    mkdir -p "$TEST_PROJECT/.claude"
    echo "<!-- ⚠️ 以下由 ai-dev-flow-server install.sh 自动追加 -->" > "$TEST_PROJECT/.claude/CLAUDE.md"
    echo "old installed content" >> "$TEST_PROJECT/.claude/CLAUDE.md"

    run bash /code/install.sh "$TEST_PROJECT" --role developer
    [ "$status" -eq 0 ]
    [[ "$output" =~ 跳过 ]]
}

@test "install skips when new marker present in CLAUDE.md" {
    mkdir -p "$TEST_PROJECT/.claude"
    echo "<!-- ai-dev-flow-server -->" > "$TEST_PROJECT/.claude/CLAUDE.md"
    echo "some content" >> "$TEST_PROJECT/.claude/CLAUDE.md"

    run bash /code/install.sh "$TEST_PROJECT" --role developer
    [ "$status" -eq 0 ]
    [[ "$output" =~ 跳过 ]]
}
