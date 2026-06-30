# -*- bats -*-
# 集成测试: devflow role switch 3 向循环切换

load /code/tests/helpers/common.bash

@test "switch: agent-b → developer" {
    bash /code/install.sh "$TEST_PROJECT" --role agent-b
    export PATH="$HOME/.local/bin:$PATH"
    run devflow role switch developer
    [ "$status" -eq 0 ]
    grep -q "role: developer" "$TEST_PROJECT/.devflow/config.yaml"
    grep -q "developer" "$TEST_PROJECT/.claude/CLAUDE.md"
    [ ! -d "$TEST_PROJECT/_handoff" ]
    [ ! -f "$TEST_PROJECT/AGENTS.md" ]
}

@test "switch: developer → owner" {
    bash /code/install.sh "$TEST_PROJECT" --role agent-b
    export PATH="$HOME/.local/bin:$PATH"
    devflow role switch developer
    run devflow role switch owner
    [ "$status" -eq 0 ]
    grep -q "role: owner" "$TEST_PROJECT/.devflow/config.yaml"
    grep -q "全权" "$TEST_PROJECT/.claude/CLAUDE.md"
}

@test "switch: owner → agent-b" {
    bash /code/install.sh "$TEST_PROJECT" --role agent-b
    export PATH="$HOME/.local/bin:$PATH"
    devflow role switch owner
    run devflow role switch agent-b
    [ "$status" -eq 0 ]
    grep -q "role: agent-b" "$TEST_PROJECT/.devflow/config.yaml"
    grep -q "Agent B 行为边界" "$TEST_PROJECT/.claude/CLAUDE.md"
    [ -d "$TEST_PROJECT/_handoff/outbox/agent-b" ]
    [ -f "$TEST_PROJECT/AGENTS.md" ]
}

@test "switch: full cycle agent-b → developer → owner → agent-b" {
    bash /code/install.sh "$TEST_PROJECT" --role agent-b
    export PATH="$HOME/.local/bin:$PATH"
    devflow role switch developer
    devflow role switch owner
    run devflow role switch agent-b
    [ "$status" -eq 0 ]
    grep -q "role: agent-b" "$TEST_PROJECT/.devflow/config.yaml"
    [ -d "$TEST_PROJECT/_handoff/outbox/agent-b" ]
    [ -f "$TEST_PROJECT/AGENTS.md" ]
}
