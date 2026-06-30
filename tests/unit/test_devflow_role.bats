# -*- bats -*-
# 单元测试: devflow role 命令

setup() {
    TEST_HOME=$(mktemp -d)
    PROJECT="$TEST_HOME/project"
    mkdir -p "$PROJECT/.devflow/scripts" "$PROJECT/.devflow/templates/roles/agent-b"
    mkdir -p "$PROJECT/.claude"

    # 写入 config.yaml
    cat > "$PROJECT/.devflow/config.yaml" << 'EOF'
project:
  name: test-project
mode: full
role: agent-b
EOF

    # 写入 CLAUDE.md 含 marker
    cat > "$PROJECT/.claude/CLAUDE.md" << 'EOF'
# 项目规则
<!-- ai-dev-flow-server -->
old content
<!-- ai-dev-flow-server end -->
EOF

    # 写入模板文件
    echo "base content" > "$PROJECT/.devflow/templates/CLAUDE.md.base.append"
    echo "owner content
<!-- ai-dev-flow-server end -->" > "$PROJECT/.devflow/templates/roles/owner.append"
    echo "developer content
<!-- ai-dev-flow-server end -->" > "$PROJECT/.devflow/templates/roles/developer.append"
    echo "agent-b content
<!-- ai-dev-flow-server end -->" > "$PROJECT/.devflow/templates/roles/agent-b/CLAUDE.md.append"
    echo "# AGENTS.md for __PROJECT__" > "$PROJECT/.devflow/templates/roles/agent-b/AGENTS.md"

    # Fake devflow
    cp /code/scripts/devflow "$PROJECT/.devflow/scripts/devflow"
    chmod +x "$PROJECT/.devflow/scripts/devflow"
    export HOME="$TEST_HOME"
    mkdir -p "$HOME/.local/bin"
    ln -sf "$PROJECT/.devflow/scripts/devflow" "$HOME/.local/bin/devflow"
    export PATH="$HOME/.local/bin:$PATH"
}

teardown() {
    [ -n "${TEST_HOME:-}" ] && [ -d "$TEST_HOME" ] && rm -rf "$TEST_HOME"
}

@test "devflow role reads current role" {
    run devflow role
    [ "$status" -eq 0 ]
    [[ "$output" =~ agent-b ]]
}

@test "devflow role switch changes role in config" {
    run devflow role switch owner
    [ "$status" -eq 0 ]
    grep -q "role: owner" "$PROJECT/.devflow/config.yaml"
}

@test "devflow role switch updates CLAUDE.md marker segment" {
    run devflow role switch developer
    [ "$status" -eq 0 ]
    grep -q "developer content" "$PROJECT/.claude/CLAUDE.md"
    ! grep -q "agent-b content" "$PROJECT/.claude/CLAUDE.md"
}

@test "devflow role switch is idempotent" {
    devflow role switch owner
    run devflow role switch owner
    [ "$status" -eq 0 ]
    grep -q "role: owner" "$PROJECT/.devflow/config.yaml"
}

@test "devflow role list shows all roles" {
    run devflow role list
    [ "$status" -eq 0 ]
    [[ "$output" =~ owner ]]
    [[ "$output" =~ developer ]]
    [[ "$output" =~ agent-b ]]
}

@test "devflow role switch with missing marker errors" {
    echo "# no marker" > "$PROJECT/.claude/CLAUDE.md"
    run devflow role switch owner
    [ "$status" -ne 0 ]
    [[ "$output" =~ 标记 ]]
}

@test "devflow role with missing role field defaults to agent-b" {
    sed -i '/^role:/d' "$PROJECT/.devflow/config.yaml"
    run devflow role
    [ "$status" -eq 0 ]
}
