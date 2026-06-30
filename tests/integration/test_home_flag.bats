# -*- bats -*-
# 集成测试: --home 覆盖 $HOME

load /code/tests/helpers/common.bash

@test "--home flag redirects .claude to custom path" {
    local CUSTOM_HOME="$TEST_HOME/custom_home"
    run bash /code/install.sh "$TEST_PROJECT" --mode frontend --home "$CUSTOM_HOME"
    [ "$status" -eq 0 ]

    # .claude/ 在 --home 指定路径下
    [ -f "$CUSTOM_HOME/.claude/settings.local.json" ]
    [ -f "$CUSTOM_HOME/.claude/workflows/gate-1-grill.js" ]

    # 不在 $TEST_HOME 下（未设 --home 的默认位置）
    [ ! -f "$TEST_HOME/.claude/settings.local.json" ]
}
