# -*- bats -*-
# 集成测试: --mode frontend 完整流程

load /code/tests/helpers/common.bash

@test "frontend mode installs gate/skills/config, not backend" {
    run bash /code/install.sh "$TEST_PROJECT" --mode frontend
    [ "$status" -eq 0 ]

    # gate workflows 存在
    [ -f "$HOME/.claude/workflows/gate-1-grill.js" ]
    [ -f "$HOME/.claude/workflows/gate-2-prd.js" ]

    # gate-checklists 存在
    [ -f "$HOME/.claude/gate-checklists/gate-1-grill.md" ]

    # gate skills 存在
    [ -d "$HOME/.claude/skills/gate-1-grill" ]
    [ -d "$HOME/.claude/skills/gate-preflight" ]

    # CC skills 已安装
    [ -d "$HOME/.claude/skills/to-prd" ]

    # settings 含 _generated_by
    grep -q '"ai-dev-flow-server"' "$HOME/.claude/settings.local.json"

    # hooks 已安装
    [ -f "$HOME/.claude/hooks/file-guard.sh" ]

    # .gate-state 已创建
    [ -f "$TEST_PROJECT/.gate-state" ]

    # config.yaml 不含后端段 (R1 #2 回归)
    ! grep -q '^dispatch:' "$TEST_PROJECT/.devflow/config.yaml" || false
    ! grep -q '^review:' "$TEST_PROJECT/.devflow/config.yaml" || false
    ! grep -q '^notify:' "$TEST_PROJECT/.devflow/config.yaml" || false

    # 后端组件不存在
    [ ! -d "$TEST_PROJECT/.devflow/archon" ]
    [ ! -d "$TEST_PROJECT/logs" ]

    # knowledge/ 存在（全 mode 共享）
    [ -d "$TEST_PROJECT/.devflow/knowledge" ]
}
