# -*- bats -*-
# 单元测试: --role 参数

@test "--role owner accepted" {
    run bash /code/install.sh /tmp --role owner --dry-run
    [ "$status" -eq 0 ]
}

@test "--role developer accepted" {
    run bash /code/install.sh /tmp --role developer --dry-run
    [ "$status" -eq 0 ]
}

@test "--role agent-b accepted" {
    run bash /code/install.sh /tmp --role agent-b --dry-run
    [ "$status" -eq 0 ]
}

@test "--role with invalid value exits non-zero" {
    run bash /code/install.sh /tmp --role admin --dry-run
    [ "$status" -ne 0 ]
    [[ "$output" =~ 无效 ]]
}

@test "no --role defaults to agent-b" {
    run bash /code/install.sh /tmp --dry-run
    [ "$status" -eq 0 ]
    [[ "$output" =~ agent-b ]]
}
