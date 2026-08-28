# -*- bats -*-
# 测试 plan-backup.sh hook 行为

setup() {
    # 宿主直接 bats 调试时 rm -rf 真实 $HOME/.claude/plans/.git-backup 属破坏性操作——HOME 沙箱化
    SANDBOX=$(mktemp -d)
    export HOME="$SANDBOX/home"
    mkdir -p "$HOME/.claude/plans"
    BACKUP_DIR="$HOME/.claude/plans/.git-backup"
}

teardown() {
    [ -n "${SANDBOX:-}" ] && [ -d "$SANDBOX" ] && rm -rf "$SANDBOX"
}

@test "plan-backup: creates git repo and commits on plan file Edit" {
    PLAN="$HOME/.claude/plans/test-plan.md"
    mkdir -p "$(dirname "$PLAN")"
    echo "# test" > "$PLAN"
    INPUT="{\"tool_input\":{\"file_path\":\"$PLAN\"}}" \
      bash /code/config-templates/default/hooks/plan-backup.sh
    [ -d "$BACKUP_DIR/.git" ]
    [ -f "$BACKUP_DIR/test-plan.md" ]
}

@test "plan-backup: ignores non-plan files" {
    INPUT='{"tool_input":{"file_path":"/tmp/not-a-plan.md"}}' \
      bash /code/config-templates/default/hooks/plan-backup.sh
    [ ! -d "$BACKUP_DIR/.git" ]
}

@test "plan-backup: appends commits on subsequent edits" {
    PLAN="$HOME/.claude/plans/test-plan.md"
    mkdir -p "$(dirname "$PLAN")"
    echo "# v1" > "$PLAN"
    INPUT="{\"tool_input\":{\"file_path\":\"$PLAN\"}}" \
      bash /code/config-templates/default/hooks/plan-backup.sh
    echo "# v2" > "$PLAN"
    INPUT="{\"tool_input\":{\"file_path\":\"$PLAN\"}}" \
      bash /code/config-templates/default/hooks/plan-backup.sh
    COUNT=$(git -C "$BACKUP_DIR" rev-list --count HEAD 2>/dev/null || echo 0)
    [ "$COUNT" -eq 2 ]
}
