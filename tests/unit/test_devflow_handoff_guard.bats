# -*- bats -*-
# 单元测试: devflow role switch handoff 保护

setup() {
    TEST_HOME=$(mktemp -d)
    PROJECT="$TEST_HOME/project"
    mkdir -p "$PROJECT/.devflow/scripts" "$PROJECT/.devflow/templates/roles/agent-b" "$PROJECT/.devflow/templates/roles"
    mkdir -p "$PROJECT/.claude" "$PROJECT/_handoff/outbox/agent-b" "$PROJECT/_handoff/inbox/agent-b"

    cat > "$PROJECT/.devflow/config.yaml" << 'EOF'
project:
  name: test-project
mode: full
role: agent-b
EOF

    cat > "$PROJECT/.claude/CLAUDE.md" << 'EOF'
# 项目规则
<!-- ai-dev-flow-server -->
agent-b content
<!-- ai-dev-flow-server end -->
EOF

    # 模板文件
    echo "base content" > "$PROJECT/.devflow/templates/CLAUDE.md.base.append"
    echo "owner content
<!-- ai-dev-flow-server end -->" > "$PROJECT/.devflow/templates/roles/owner.append"
    echo "agent-b content
<!-- ai-dev-flow-server end -->" > "$PROJECT/.devflow/templates/roles/agent-b/CLAUDE.md.append"

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

@test "switch from agent-b with pending outbox rejects" {
    echo "pending msg" > "$PROJECT/_handoff/outbox/agent-b/pending.md"
    run devflow role switch owner
    [ "$status" -ne 0 ]
    [[ "$output" =~ 待处理 ]]
    grep -q "role: agent-b" "$PROJECT/.devflow/config.yaml"
}

@test "switch from agent-b with pending inbox rejects" {
    echo "pending reply" > "$PROJECT/_handoff/inbox/agent-b/reply.md"
    run devflow role switch owner
    [ "$status" -ne 0 ]
    [[ "$output" =~ 待处理 ]]
}

@test "switch from agent-b with empty handoff dirs succeeds" {
    run devflow role switch owner
    [ "$status" -eq 0 ]
    grep -q "role: owner" "$PROJECT/.devflow/config.yaml"
    [ ! -d "$PROJECT/_handoff" ]
}

@test "switch to agent-b creates handoff and AGENTS.md" {
    # start as owner
    sed -i 's/role: agent-b/role: owner/' "$PROJECT/.devflow/config.yaml"
    echo "owner content
<!-- ai-dev-flow-server end -->" > "$PROJECT/.claude/CLAUDE.md.append"

    run devflow role switch agent-b
    [ "$status" -eq 0 ]
    [ -d "$PROJECT/_handoff/outbox/agent-b" ]
    [ -d "$PROJECT/_handoff/inbox/agent-b" ]
    [ -f "$PROJECT/AGENTS.md" ]
}
