# -*- bats -*-
# 集成测试: --no-config / --no-skills

load /code/tests/helpers/common.bash

@test "--no-config skips settings + hooks" {
    run bash /code/install.sh "$TEST_PROJECT" --mode frontend --no-config
    [ "$status" -eq 0 ]
    [ ! -f "$HOME/.claude/settings.local.json" ]
    [ ! -f "$HOME/.claude/hooks/file-guard.sh" ]
    # workflows + gate-state still installed
    [ -f "$HOME/.claude/workflows/gate-1-grill.js" ]
    [ -f "$TEST_PROJECT/.gate-state" ]
}

@test "--no-skills skips CC skill installation" {
    run bash /code/install.sh "$TEST_PROJECT" --mode frontend --no-skills
    [ "$status" -eq 0 ]
    [ -f "$HOME/.claude/settings.local.json" ]
    # CC skills (non-gate) should be absent
    [ ! -d "$HOME/.claude/skills/to-prd" ]
    [ ! -d "$HOME/.claude/skills/caveman" ]
    # gate skills still installed
    [ -d "$HOME/.claude/skills/gate-1-grill" ]
}

@test "--no-config --no-skills only installs workflows + gate-state" {
    run bash /code/install.sh "$TEST_PROJECT" --mode frontend --no-config --no-skills
    [ "$status" -eq 0 ]
    [ -f "$HOME/.claude/workflows/gate-1-grill.js" ]
    [ -f "$TEST_PROJECT/.gate-state" ]
    [ ! -f "$HOME/.claude/settings.local.json" ]
    [ ! -d "$HOME/.claude/skills/to-prd" ]
}
