# -*- bats -*-
# 集成测试: --update 模式

load /code/tests/helpers/common.bash

@test "--update reads mode from config.yaml (frontend)" {
    bash /code/install.sh "$TEST_PROJECT" --mode frontend
    run bash /code/install.sh "$TEST_PROJECT" --update
    [ "$status" -eq 0 ]
    # frontend mode: 不装 archon
    [ ! -d "$TEST_PROJECT/.devflow/archon" ]
}

@test "--update reads mode from config.yaml (backend)" {
    bash /code/install.sh "$TEST_PROJECT" --mode backend
    run bash /code/install.sh "$TEST_PROJECT" --update
    [ "$status" -eq 0 ]
    # backend mode: 不装 workflows
    [ ! -d "$HOME/.claude/workflows" ]
}

@test "--update without config.yaml warns and falls back to full" {
    # no prior install, but create config.yaml without mode
    mkdir -p "$TEST_PROJECT/.devflow"
    echo "project: test" > "$TEST_PROJECT/.devflow/config.yaml"
    run bash /code/install.sh "$TEST_PROJECT" --update
    [ "$status" -eq 0 ]
    [[ "$output" =~ 默认|full ]]
}

@test "--force --update overwrites modified files" {
    bash /code/install.sh "$TEST_PROJECT" --mode frontend
    echo "# tampered" >> "$HOME/.claude/hooks/file-guard.sh"
    run bash /code/install.sh "$TEST_PROJECT" --force --update
    [ "$status" -eq 0 ]
    ! grep -q '# tampered' "$HOME/.claude/hooks/file-guard.sh" || false
}
