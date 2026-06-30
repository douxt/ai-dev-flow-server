# -*- bats -*-
# 集成测试: devflow 部署验证

load /code/tests/helpers/common.bash

@test "devflow script copied to .devflow/scripts/devflow" {
    bash /code/install.sh "$TEST_PROJECT" --role developer
    [ -f "$TEST_PROJECT/.devflow/scripts/devflow" ]
    [ -x "$TEST_PROJECT/.devflow/scripts/devflow" ]
}

@test "devflow symlink created at ~/.local/bin/devflow" {
    bash /code/install.sh "$TEST_PROJECT" --role developer
    [ -L "$HOME/.local/bin/devflow" ]
}

@test "devflow symlink points to project script" {
    bash /code/install.sh "$TEST_PROJECT" --role developer
    local target=$(readlink "$HOME/.local/bin/devflow")
    [[ "$target" =~ .devflow/scripts/devflow ]]
}

@test "template files copied to .devflow/templates/" {
    bash /code/install.sh "$TEST_PROJECT" --role developer
    [ -f "$TEST_PROJECT/.devflow/templates/CLAUDE.md.base.append" ]
    [ -f "$TEST_PROJECT/.devflow/templates/roles/owner.append" ]
    [ -f "$TEST_PROJECT/.devflow/templates/roles/developer.append" ]
    [ -f "$TEST_PROJECT/.devflow/templates/roles/agent-b/CLAUDE.md.append" ]
    [ -f "$TEST_PROJECT/.devflow/templates/roles/agent-b/AGENTS.md" ]
}
