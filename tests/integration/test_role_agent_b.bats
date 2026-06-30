# -*- bats -*-
# 集成测试: --role agent-b 安装（向后兼容）

load /code/tests/helpers/common.bash

@test "agent-b install: CLAUDE.md has base + agent-b constraints" {
    run bash /code/install.sh "$TEST_PROJECT" --role agent-b
    [ "$status" -eq 0 ]
    [ -f "$TEST_PROJECT/.claude/CLAUDE.md" ]
    grep -q "Gate 流程\|Issue 状态机" "$TEST_PROJECT/.claude/CLAUDE.md"
    grep -q "Agent B 行为边界" "$TEST_PROJECT/.claude/CLAUDE.md"
    grep -q "协作通道" "$TEST_PROJECT/.claude/CLAUDE.md"
}

@test "agent-b install: _handoff/ created" {
    bash /code/install.sh "$TEST_PROJECT" --role agent-b
    [ -d "$TEST_PROJECT/_handoff/outbox/agent-b" ]
    [ -d "$TEST_PROJECT/_handoff/inbox/agent-b" ]
    [ -d "$TEST_PROJECT/_handoff/archive" ]
}

@test "agent-b install: AGENTS.md created" {
    bash /code/install.sh "$TEST_PROJECT" --role agent-b
    [ -f "$TEST_PROJECT/AGENTS.md" ]
    grep -q "Agent B" "$TEST_PROJECT/AGENTS.md"
}

@test "agent-b install: no hardcoded OpenLobby" {
    bash /code/install.sh "$TEST_PROJECT" --role agent-b
    ! grep -q "OpenLobby" "$TEST_PROJECT/.claude/CLAUDE.md"
    ! grep -q "OpenLobby" "$TEST_PROJECT/_handoff/README.md"
    ! grep -q "OpenLobby" "$TEST_PROJECT/AGENTS.md"
}

@test "agent-b install: config.yaml role field set" {
    bash /code/install.sh "$TEST_PROJECT" --role agent-b
    grep -q "role: agent-b" "$TEST_PROJECT/.devflow/config.yaml"
}
