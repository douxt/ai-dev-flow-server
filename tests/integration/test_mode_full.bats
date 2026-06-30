# -*- bats -*-
# 集成测试: --mode full 完整流程

load /code/tests/helpers/common.bash

@test "full mode installs both frontend and backend components" {
    run bash /code/install.sh "$TEST_PROJECT" --mode full
    [ "$status" -eq 0 ]

    # frontend 组件
    [ -f "$HOME/.claude/workflows/gate-1-grill.js" ]
    [ -f "$HOME/.claude/gate-checklists/gate-1-grill.md" ]
    [ -d "$HOME/.claude/skills/gate-1-grill" ]
    [ -f "$HOME/.claude/settings.local.json" ]
    [ -f "$TEST_PROJECT/.gate-state" ]

    # backend 组件
    [ -f "$TEST_PROJECT/.devflow/archon/dispatch.sh" ]
    [ -d "$TEST_PROJECT/.devflow/scripts" ]
    [ -d "$TEST_PROJECT/logs" ]

    # config.yaml 含 mode: full
    grep -q 'mode:.*full' "$TEST_PROJECT/.devflow/config.yaml"
    grep -q '^dispatch:' "$TEST_PROJECT/.devflow/config.yaml"

    # knowledge/ 存在
    [ -d "$TEST_PROJECT/.devflow/knowledge" ]
}
