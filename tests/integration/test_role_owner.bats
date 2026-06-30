# -*- bats -*-
# 集成测试: --role owner 安装

load /code/tests/helpers/common.bash

@test "owner install: CLAUDE.md has base content but no agent-b constraints" {
    run bash /code/install.sh "$TEST_PROJECT" --role owner
    [ "$status" -eq 0 ]
    [ -f "$TEST_PROJECT/.claude/CLAUDE.md" ]
    grep -q "__PROJECT__\|Gate 流程\|Issue 状态机\|计划文件管理" "$TEST_PROJECT/.claude/CLAUDE.md" || grep -q "全权" "$TEST_PROJECT/.claude/CLAUDE.md"
}

@test "owner install: no _handoff/ directory" {
    bash /code/install.sh "$TEST_PROJECT" --role owner
    [ ! -d "$TEST_PROJECT/_handoff" ]
}

@test "owner install: no AGENTS.md" {
    bash /code/install.sh "$TEST_PROJECT" --role owner
    [ ! -f "$TEST_PROJECT/AGENTS.md" ]
}

@test "owner install: config.yaml role field set" {
    bash /code/install.sh "$TEST_PROJECT" --role owner
    grep -q "role: owner" "$TEST_PROJECT/.devflow/config.yaml"
}
