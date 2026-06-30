# -*- bats -*-
# 测试 config.yaml mode 字段解析（grep + sed 模式）

# 复用 install.sh 的解析逻辑
parse_mode() {
    local config="$1"
    echo "$config" | grep -E '^[[:space:]]*mode:[[:space:]]*[^[:space:]#]+' 2>/dev/null | head -1 | sed 's/^[[:space:]]*mode:[[:space:]]*//;s/[[:space:]]*#.*//;s/[[:space:]]*$//'
}

@test "mode: frontend" {
    result=$(parse_mode "mode: frontend")
    [ "$result" = "frontend" ]
}

@test "mode: backend" {
    result=$(parse_mode "mode: backend")
    [ "$result" = "backend" ]
}

@test "mode: full with inline comment" {
    result=$(parse_mode "mode: full  # this is full mode")
    [ "$result" = "full" ]
}

@test "no mode field returns empty" {
    result=$(parse_mode "project: my-project")
    [ -z "$result" ]
}

@test "mode with leading spaces" {
    result=$(parse_mode "  mode: frontend")
    [ "$result" = "frontend" ]
}

@test "mode with comment on separate line not matched" {
    result=$(parse_mode "# mode: backend
project: test")
    [ -z "$result" ]
}
