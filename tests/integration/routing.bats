# -*- bats -*-
# 集成测试: CLAUDE.md 路由规则 + workflow-gate 拦截链验证

setup() {
    REPO_ROOT="${REPO_ROOT:-$(cd "$BATS_TEST_DIRNAME/../.." && pwd)}"
    TEST_HOME=$(mktemp -d)
    TEST_PROJECT="$TEST_HOME/project"
    mkdir -p "$TEST_PROJECT"
    cd "$TEST_PROJECT"
    git init
    git config user.email "test@devflow.test"
    git config user.name "DevFlow Test"
    BYPASS_WT_CHECK=1 git commit --allow-empty -m "init"
    export HOME="$TEST_HOME"
}

teardown() {
    [ -n "${TEST_HOME:-}" ] && [ -d "$TEST_HOME" ] && rm -rf "$TEST_HOME"
}

@test "CLAUDE.md 安装后包含路由评估三问" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    grep -q "评估三问" "$HOME/.claude/CLAUDE.md"
    grep -q "上下文窗口装得下吗" "$HOME/.claude/CLAUDE.md"
    grep -q "有现有文档" "$HOME/.claude/CLAUDE.md"
    grep -q "有雾吗" "$HOME/.claude/CLAUDE.md"
}

@test "CLAUDE.md 安装后包含路由表（6 路径）" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    grep -q "简单改动.*直接 /implement" "$HOME/.claude/CLAUDE.md"
    grep -q "Plan Mode.*grill-with-docs.*to-spec.*to-tickets.*implement" "$HOME/.claude/CLAUDE.md"
    grep -q "多会话大型.*/wayfinder" "$HOME/.claude/CLAUDE.md"
    grep -q "已有代码逆向规格" "$HOME/.claude/CLAUDE.md"
}

@test "CLAUDE.md 安装后包含核心命令表" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    grep -q "/grill-with-docs" "$HOME/.claude/CLAUDE.md"
    grep -q "/wayfinder" "$HOME/.claude/CLAUDE.md"
    grep -q "/to-spec" "$HOME/.claude/CLAUDE.md"
    grep -q "/to-tickets" "$HOME/.claude/CLAUDE.md"
    grep -q "/implement" "$HOME/.claude/CLAUDE.md"
    grep -q "/code-review" "$HOME/.claude/CLAUDE.md"
    grep -q "/research" "$HOME/.claude/CLAUDE.md"
}

@test "CLAUDE.md 安装后包含安全红线段" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    grep -q "安全红线" "$HOME/.claude/CLAUDE.md"
    grep -q "auth.*认证" "$HOME/.claude/CLAUDE.md"
    grep -q "payment.*支付" "$HOME/.claude/CLAUDE.md"
    grep -q "crypto.*加密" "$HOME/.claude/CLAUDE.md"
    grep -q "delete.*删除" "$HOME/.claude/CLAUDE.md"
    grep -q "permission.*权限" "$HOME/.claude/CLAUDE.md"
}

@test "CLAUDE.md 安装后包含引导词体系" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    grep -q "先想清楚再做" "$HOME/.claude/CLAUDE.md"
    grep -q "垂直切片" "$HOME/.claude/CLAUDE.md"
    grep -q "假设可证伪" "$HOME/.claude/CLAUDE.md"
    grep -q "证据不声称" "$HOME/.claude/CLAUDE.md"
    grep -q "不扩范围" "$HOME/.claude/CLAUDE.md"
    grep -q "每个 Bug 都是永久升级" "$HOME/.claude/CLAUDE.md"
}

@test "CLAUDE.md 安装后包含上下文预算" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    grep -q "上下文窗口.*40%" "$HOME/.claude/CLAUDE.md"
    grep -q "48K" "$HOME/.claude/CLAUDE.md"
}

@test "CLAUDE.md 安装后包含 worktree 强制规则" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    grep -q "Worktree 强制" "$HOME/.claude/CLAUDE.md"
    grep -q "wt create" "$HOME/.claude/CLAUDE.md"
    grep -q "wt cleanup" "$HOME/.claude/CLAUDE.md"
}

@test "CLAUDE.md 安装后包含模型路由建议" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    grep -q "模型路由建议" "$HOME/.claude/CLAUDE.md"
    grep -q "规划.*Opus" "$HOME/.claude/CLAUDE.md"
    grep -q "日常实现.*Sonnet" "$HOME/.claude/CLAUDE.md"
    grep -q "批量文件.*Haiku" "$HOME/.claude/CLAUDE.md"
}

@test "CLAUDE.md 安装后包含 Git 操作约束" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    grep -q "禁止.*push --force" "$HOME/.claude/CLAUDE.md"
    grep -q "禁止.*commit --amend.*已推送" "$HOME/.claude/CLAUDE.md"
    grep -q "禁止直推.*master/main" "$HOME/.claude/CLAUDE.md"
}

@test "CLAUDE.md 安装后包含代码修改安全" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    grep -q "代码修改安全" "$HOME/.claude/CLAUDE.md"
    grep -q "修改前备份.*cp file file.bak" "$HOME/.claude/CLAUDE.md"
    grep -q "永不.*git checkout" "$HOME/.claude/CLAUDE.md"
}

@test "CLAUDE.md 安装后包含计划文件管理" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    grep -q "计划文件管理" "$HOME/.claude/CLAUDE.md"
    grep -q "ADR-NNN" "$HOME/.claude/CLAUDE.md"
    grep -q "已采纳.*已废弃" "$HOME/.claude/CLAUDE.md"
}

@test "CLAUDE.md 安装后包含 /wayfinder 使用边界" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    grep -q "✅ 该用" "$HOME/.claude/CLAUDE.md"
    grep -q "❌ 不该用" "$HOME/.claude/CLAUDE.md"
    grep -q "判断标准" "$HOME/.claude/CLAUDE.md"
}

@test "CLAUDE.md 安装后包含评估输出格式" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    grep -q "建议路径" "$HOME/.claude/CLAUDE.md"
}

@test "CLAUDE.md 安装后包含 spec 评审路由（分级）" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    grep -q "spec.*评审\|/review-cc-cli.*spec" "$HOME/.claude/CLAUDE.md"
    grep -q "大型.*独立评审" "$HOME/.claude/CLAUDE.md"
    grep -q "中型.*自查" "$HOME/.claude/CLAUDE.md"
}

@test "CLAUDE.md 安装后包含 TDD 前置步骤" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    grep -q "/tdd" "$HOME/.claude/CLAUDE.md"
    grep -q "RED.*GREEN\|TDD.*测试.*前置" "$HOME/.claude/CLAUDE.md"
}

@test "workflow-gate hook 已注册到 settings.json" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    grep -q "workflow-gate" "$HOME/.claude/settings.local.json"
}

@test "stage-tracker hook 已注册到 settings.json" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    grep -q "stage-tracker" "$HOME/.claude/settings.local.json"
}

@test "suggest-rules hook 已注册到 settings.json" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    grep -q "suggest-rules" "$HOME/.claude/settings.local.json"
}

# ── workflow-gate 行为测试 ──

@test "workflow-gate: 首次 Edit → 拦截 + 写入 route 文件" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    HOOK="$HOME/.claude/hooks/workflow-gate.sh"
    [ -f "$HOOK" ]

    export WORKSPACE="$TEST_PROJECT"
    export CC_SESSION_ID="routing-test-001"
    mkdir -p "$TEST_PROJECT/.devflow"

    run bash "$HOOK" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 1 ]
    [[ "$output" =~ workflow-gate ]]
    [ -f "$TEST_PROJECT/.workflow-route" ]
}

@test "workflow-gate: route 存在 → 第二次放行" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    HOOK="$HOME/.claude/hooks/workflow-gate.sh"

    export WORKSPACE="$TEST_PROJECT"
    export CC_SESSION_ID="routing-test-001"
    mkdir -p "$TEST_PROJECT/.devflow"

    echo "routing-test-001|assessed|1700000000" > "$TEST_PROJECT/.workflow-route"
    run bash "$HOOK" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 0 ]
}

@test "workflow-gate: 逃生文件 → 全部放行" {
    bash "$REPO_ROOT/install.sh" "$TEST_PROJECT" --mode full
    HOOK="$HOME/.claude/hooks/workflow-gate.sh"

    export WORKSPACE="$TEST_PROJECT"
    mkdir -p "$TEST_PROJECT/.devflow"
    mkdir -p "$HOME/.claude"
    touch "$HOME/.claude/.emergency-bypass"

    run bash "$HOOK" "Write" '{"file_path":"/tmp/test.txt"}'
    [ "$status" -eq 0 ]

    rm -f "$HOME/.claude/.emergency-bypass"
}
