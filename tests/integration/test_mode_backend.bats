# -*- bats -*-
# 集成测试: --mode backend 完整流程

load /code/tests/helpers/common.bash

@test "backend mode installs archon/scripts/scheduler, not frontend" {
    run bash /code/install.sh "$TEST_PROJECT" --mode backend --scheduler cron
    [ "$status" -eq 0 ]

    # archon + scripts 存在
    [ -f "$TEST_PROJECT/.devflow/archon/dispatch.sh" ]
    [ -f "$TEST_PROJECT/.devflow/archon/reconciler.sh" ]
    [ -d "$TEST_PROJECT/.devflow/scripts" ]

    # logs/ 存在
    [ -d "$TEST_PROJECT/logs" ]

    # knowledge/ 存在
    [ -d "$TEST_PROJECT/.devflow/knowledge" ]

    # config.yaml 含后端段
    grep -q '^dispatch:' "$TEST_PROJECT/.devflow/config.yaml"
    grep -q '^review:' "$TEST_PROJECT/.devflow/config.yaml"
    grep -q '^notify:' "$TEST_PROJECT/.devflow/config.yaml"

    # frontend 组件不存在
    [ ! -d "$HOME/.claude/workflows" ]
    [ ! -f "$TEST_PROJECT/.gate-state" ]
    [ ! -f "$HOME/.claude/settings.local.json" ]

    # root 段输出含 scheduler 指令
    [[ "$output" =~ systemctl|sudo\ crontab|crontab ]]
}
