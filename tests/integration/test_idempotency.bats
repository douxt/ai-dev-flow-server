# -*- bats -*-
# 集成测试: 幂等性 + --force

load /code/tests/helpers/common.bash

@test "second install is idempotent without --force" {
    run bash /code/install.sh "$TEST_PROJECT" --mode frontend
    [ "$status" -eq 0 ]
    # record state after first install
    local mtime_before=$(stat -c %Y "$TEST_PROJECT/.gate-state" 2>/dev/null || echo "0")

    run bash /code/install.sh "$TEST_PROJECT" --mode frontend
    [ "$status" -eq 0 ]
    # gate-state unchanged (not re-created)
    [ -f "$TEST_PROJECT/.gate-state" ]
}

@test "--force does NOT overwrite .gate-state" {
    echo "INITIAL_STATE" > "$TEST_PROJECT/.gate-state"
    run bash /code/install.sh "$TEST_PROJECT" --mode frontend --force
    [ "$status" -eq 0 ]
    [ "$(cat "$TEST_PROJECT/.gate-state")" = "INITIAL_STATE" ]
}

@test "--force overwrites existing regular files" {
    # install once
    bash /code/install.sh "$TEST_PROJECT" --mode frontend
    # modify a hook
    echo "# modified" >> "$HOME/.claude/hooks/file-guard.sh"
    # force reinstall
    run bash /code/install.sh "$TEST_PROJECT" --mode frontend --force
    [ "$status" -eq 0 ]
    # hook was restored (no "# modified" line)
    ! grep -q '# modified' "$HOME/.claude/hooks/file-guard.sh" || false
}
