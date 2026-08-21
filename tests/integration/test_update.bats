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

@test "--update generates AGENTS.md (fresh project without one)" {
    bash /code/install.sh "$TEST_PROJECT" --mode frontend
    run bash /code/install.sh "$TEST_PROJECT" --update
    [ "$status" -eq 0 ]
    [ -f "$TEST_PROJECT/AGENTS.md" ]
    grep -q "ai-dev-flow-server:AGENTS-START" "$TEST_PROJECT/AGENTS.md"
}

@test "--update AGENTS.md idempotent (no duplicate sections)" {
    bash /code/install.sh "$TEST_PROJECT" --mode frontend
    bash /code/install.sh "$TEST_PROJECT" --update
    run bash /code/install.sh "$TEST_PROJECT" --update
    [ "$status" -eq 0 ]
    [ "$(grep -c 'ai-dev-flow-server:AGENTS-START' "$TEST_PROJECT/AGENTS.md")" -eq 1 ]
}

@test "--update does not overwrite custom AGENTS.md (no marker)" {
    bash /code/install.sh "$TEST_PROJECT" --mode frontend
    echo "# my custom agents file" > "$TEST_PROJECT/AGENTS.md"
    run bash /code/install.sh "$TEST_PROJECT" --update
    [ "$status" -eq 0 ]
    grep -q "my custom agents file" "$TEST_PROJECT/AGENTS.md"
    ! grep -q "ai-dev-flow-server:AGENTS-START" "$TEST_PROJECT/AGENTS.md"
}
