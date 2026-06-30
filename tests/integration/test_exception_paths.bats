# -*- bats -*-
# 集成测试: 异常路径 - gh/claude/jq 不可用时的降级

load /code/tests/helpers/common.bash

@test "gh auth failure does not block install" {
    gh() { return 1; }
    export -f gh
    run bash /code/install.sh "$TEST_PROJECT" --mode frontend
    [ "$status" -eq 0 ]
    [[ "$output" =~ 警告|跳过|gh ]]
}

@test "claude not found does not block install" {
    command() { local a; for a in "$@"; do [ "$a" = "claude" ] && return 1; done; builtin command "$@"; }
    export -f command
    run bash /code/install.sh "$TEST_PROJECT" --mode frontend
    [ "$status" -eq 0 ]
}

@test "jq not found warns but does not block install" {
    command() { local a; for a in "$@"; do [ "$a" = "jq" ] && return 1; done; builtin command "$@"; }
    export -f command
    run bash /code/install.sh "$TEST_PROJECT" --mode frontend
    [ "$status" -eq 0 ]
    [[ "$output" =~ jq ]]
}

@test "non-git repo exits non-zero" {
    local d=$(mktemp -d)
    run bash /code/install.sh "$d" --mode frontend
    [ "$status" -ne 0 ]
    rm -rf "$d"
}
