# -*- bats -*-
# 集成测试: Docker 持久化 symlink

load /code/tests/helpers/common.bash

@test "Docker symlink: ~/.claude non-symlink dir with content → migrate" {
    # pre-create ~/.claude as a real directory with content
    mkdir -p "$HOME/.claude/existing"
    echo "old-data" > "$HOME/.claude/existing/file.txt"
    mkdir -p "$HOME/.config/claude"

    run bash /code/install.sh "$TEST_PROJECT" --mode frontend
    [ "$status" -eq 0 ]

    # ~/.claude should now be a symlink to ~/.config/claude
    [ -L "$HOME/.claude" ]

    # old content should be migrated to ~/.config/claude
    [ -f "$HOME/.config/claude/existing/file.txt" ]
}

@test "Docker symlink: ~/.claude already symlink → no-op" {
    mkdir -p "$HOME/.config/claude"
    ln -sfn "$HOME/.config/claude" "$HOME/.claude"

    run bash /code/install.sh "$TEST_PROJECT" --mode frontend
    [ "$status" -eq 0 ]
    [ -L "$HOME/.claude" ]
}

@test "Docker symlink: ~/.claude does not exist → create symlink" {
    [ ! -e "$HOME/.claude" ] || rm -rf "$HOME/.claude"
    mkdir -p "$HOME/.config/claude"

    run bash /code/install.sh "$TEST_PROJECT" --mode frontend
    [ "$status" -eq 0 ]
    [ -L "$HOME/.claude" ]
}

@test "Docker symlink: dotfiles are migrated (R1 #5 regression)" {
    mkdir -p "$HOME/.claude/sub"
    echo "hidden" > "$HOME/.claude/.hidden_file"
    mkdir -p "$HOME/.config/claude"

    run bash /code/install.sh "$TEST_PROJECT" --mode frontend
    [ "$status" -eq 0 ]

    # dotfile should be migrated
    [ -f "$HOME/.config/claude/.hidden_file" ]
}
