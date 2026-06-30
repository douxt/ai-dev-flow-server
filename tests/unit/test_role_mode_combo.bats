# -*- bats -*-
# 单元测试: --role × --mode 组合

@test "--role owner --mode frontend" {
    run bash /code/install.sh /tmp --role owner --mode frontend --dry-run
    [ "$status" -eq 0 ]
}

@test "--role owner --mode backend" {
    run bash /code/install.sh /tmp --role owner --mode backend --dry-run
    [ "$status" -eq 0 ]
}

@test "--role owner --mode full" {
    run bash /code/install.sh /tmp --role owner --mode full --dry-run
    [ "$status" -eq 0 ]
}

@test "--role developer --mode frontend" {
    run bash /code/install.sh /tmp --role developer --mode frontend --dry-run
    [ "$status" -eq 0 ]
}

@test "--role developer --mode backend" {
    run bash /code/install.sh /tmp --role developer --mode backend --dry-run
    [ "$status" -eq 0 ]
}

@test "--role developer --mode full" {
    run bash /code/install.sh /tmp --role developer --mode full --dry-run
    [ "$status" -eq 0 ]
}

@test "--role agent-b --mode frontend" {
    run bash /code/install.sh /tmp --role agent-b --mode frontend --dry-run
    [ "$status" -eq 0 ]
}

@test "--role agent-b --mode backend" {
    run bash /code/install.sh /tmp --role agent-b --mode backend --dry-run
    [ "$status" -eq 0 ]
}

@test "--role agent-b --mode full" {
    run bash /code/install.sh /tmp --role agent-b --mode full --dry-run
    [ "$status" -eq 0 ]
}
