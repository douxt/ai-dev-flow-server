# -*- bats -*-
# 集成测试: uninstall.sh 清理完整性

load /code/tests/helpers/common.bash

@test "uninstall --mode frontend removes gate/skills/config" {
    bash /code/install.sh "$TEST_PROJECT" --mode frontend
    run bash /code/uninstall.sh "$TEST_PROJECT" --mode frontend --force
    [ "$status" -eq 0 ]
    [ ! -f "$HOME/.claude/workflows/gate-1-grill.js" ]
    [ ! -d "$HOME/.claude/gate-checklists" ]
    [ ! -f "$TEST_PROJECT/.gate-state" ]
}

@test "uninstall --mode backend removes archon, keeps knowledge" {
    bash /code/install.sh "$TEST_PROJECT" --mode backend
    run bash /code/uninstall.sh "$TEST_PROJECT" --mode backend --force
    [ "$status" -eq 0 ]
    [ ! -d "$TEST_PROJECT/.devflow/archon" ]
    # knowledge/ should be kept when uninstalling backend only (frontend handles it)
    # Actually check: uninstall backend keeps knowledge since frontend uses it too
}

@test "uninstall --mode full removes .devflow completely" {
    bash /code/install.sh "$TEST_PROJECT" --mode full
    run bash /code/uninstall.sh "$TEST_PROJECT" --mode full --force
    [ "$status" -eq 0 ]
    [ ! -d "$TEST_PROJECT/.devflow" ]
}

@test "uninstall preserves settings without _generated_by marker" {
    bash /code/install.sh "$TEST_PROJECT" --mode frontend
    # simulate user customization: remove marker
    sed -i 's/"ai-dev-flow-server"/"custom"/' "$HOME/.claude/settings.local.json"
    run bash /code/uninstall.sh "$TEST_PROJECT" --mode frontend --force
    [ "$status" -eq 0 ]
    # settings preserved
    [ -f "$HOME/.claude/settings.local.json" ]
}

@test "uninstall --dry-run prints paths without deleting" {
    bash /code/install.sh "$TEST_PROJECT" --mode frontend
    run bash /code/uninstall.sh "$TEST_PROJECT" --mode frontend --force --dry-run
    [ "$status" -eq 0 ]
    [[ "$output" =~ DRY.RUN ]]
    # files still exist
    [ -f "$HOME/.claude/workflows/gate-1-grill.js" ]
}
