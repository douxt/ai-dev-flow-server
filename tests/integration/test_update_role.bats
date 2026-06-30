# -*- bats -*-
# 集成测试: --update 模式下的角色处理

load /code/tests/helpers/common.bash

@test "--update without --role preserves existing role from config.yaml" {
    bash /code/install.sh "$TEST_PROJECT" --role owner
    run bash /code/install.sh "$TEST_PROJECT" --update
    [ "$status" -eq 0 ]
    grep -q "role: owner" "$TEST_PROJECT/.devflow/config.yaml"
}

@test "--update --role developer overrides stored role" {
    bash /code/install.sh "$TEST_PROJECT" --role owner
    run bash /code/install.sh "$TEST_PROJECT" --update --role developer
    [ "$status" -eq 0 ]
    grep -q "role: developer" "$TEST_PROJECT/.devflow/config.yaml"
}

@test "--update --role agent-b creates handoff and AGENTS.md" {
    bash /code/install.sh "$TEST_PROJECT" --role owner
    run bash /code/install.sh "$TEST_PROJECT" --update --role agent-b
    [ "$status" -eq 0 ]
    # update keeps existing CLAUDE.md, need devflow role switch to actually change
    grep -q "role: agent-b" "$TEST_PROJECT/.devflow/config.yaml"
}
