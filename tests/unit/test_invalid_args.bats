# -*- bats -*-
# 测试非法参数处理

@test "--mode with invalid value exits non-zero" {
    run bash /code/install.sh /tmp --mode desktop
    [ "$status" -ne 0 ]
    [[ "$output" =~ 无效 ]]
}

@test "missing project path exits non-zero" {
    run bash /code/install.sh
    [ "$status" -ne 0 ]
}

@test "non-existent project path exits non-zero" {
    run bash /code/install.sh /nonexistent/path/12345
    [ "$status" -ne 0 ]
}

@test "--help shows all new parameters" {
    run bash /code/install.sh --help
    [ "$status" -eq 0 ]
    [[ "$output" =~ --mode ]]
    [[ "$output" =~ --scheduler ]]
    [[ "$output" =~ --home ]]
    [[ "$output" =~ --dry-run ]]
    [[ "$output" =~ --force ]]
    [[ "$output" =~ --no-config ]]
    [[ "$output" =~ --no-skills ]]
}

@test "non-git repo path exits non-zero" {
    local d=$(mktemp -d)
    run bash /code/install.sh "$d"
    [ "$status" -ne 0 ]
    rm -rf "$d"
}
