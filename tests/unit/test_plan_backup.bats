# -*- bats -*-
# 测试 plan-backup.sh hook 行为

setup() {
    BACKUP_DIR="$HOME/.claude/plans/.git-backup"
    rm -rf "$BACKUP_DIR"
}

teardown() {
    rm -rf "$BACKUP_DIR"
}

@test "plan-backup: creates git repo and commits on plan file Edit" {
    PLAN="$HOME/.claude/plans/test-plan.md"
    mkdir -p "$(dirname "$PLAN")"
    echo "# test" > "$PLAN"
    echo "{\"tool_input\":{\"file_path\":\"$PLAN\"}}" \
      | bash /code/config-templates/default/hooks/plan-backup.sh
    [ -d "$BACKUP_DIR/.git" ]
    [ -f "$BACKUP_DIR/test-plan.md" ]
}

@test "plan-backup: ignores non-plan files" {
    echo '{"tool_input":{"file_path":"/tmp/not-a-plan.md"}}' \
      | bash /code/config-templates/default/hooks/plan-backup.sh
    [ ! -d "$BACKUP_DIR/.git" ]
}

@test "plan-backup: appends commits on subsequent edits" {
    PLAN="$HOME/.claude/plans/test-plan.md"
    mkdir -p "$(dirname "$PLAN")"
    echo "# v1" > "$PLAN"
    echo "{\"tool_input\":{\"file_path\":\"$PLAN\"}}" \
      | bash /code/config-templates/default/hooks/plan-backup.sh
    echo "# v2" > "$PLAN"
    echo "{\"tool_input\":{\"file_path\":\"$PLAN\"}}" \
      | bash /code/config-templates/default/hooks/plan-backup.sh
    COUNT=$(git -C "$BACKUP_DIR" rev-list --count HEAD 2>/dev/null || echo 0)
    [ "$COUNT" -eq 2 ]
}
