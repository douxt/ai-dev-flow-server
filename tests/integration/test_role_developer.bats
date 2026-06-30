# -*- bats -*-
# 集成测试: --role developer 安装

load /code/tests/helpers/common.bash

@test "developer install: CLAUDE.md has base + developer constraints" {
    run bash /code/install.sh "$TEST_PROJECT" --role developer
    [ "$status" -eq 0 ]
    [ -f "$TEST_PROJECT/.claude/CLAUDE.md" ]
    grep -q "Gate 流程\|Issue 状态机" "$TEST_PROJECT/.claude/CLAUDE.md"
    grep -q "developer" "$TEST_PROJECT/.claude/CLAUDE.md"
    grep -q "业务代码" "$TEST_PROJECT/.claude/CLAUDE.md"
    grep -q "管线文件" "$TEST_PROJECT/.claude/CLAUDE.md"
}

@test "developer install: no _handoff/ directory" {
    bash /code/install.sh "$TEST_PROJECT" --role developer
    [ ! -d "$TEST_PROJECT/_handoff" ]
}

@test "developer install: no AGENTS.md" {
    bash /code/install.sh "$TEST_PROJECT" --role developer
    [ ! -f "$TEST_PROJECT/AGENTS.md" ]
}

@test "developer install: config.yaml role field set" {
    bash /code/install.sh "$TEST_PROJECT" --role developer
    grep -q "role: developer" "$TEST_PROJECT/.devflow/config.yaml"
}
