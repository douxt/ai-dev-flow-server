# -*- bats -*-
# bash-firewall 豁免口径回归（2026-09-09 UMES3 反馈 P1-2 + 修复轮发现的顶层 .cwd 缺陷）
# 核心断言：Bash 通道对 *.md 的豁免与 file-guard Edit 通道一致；
# 相对路径目标按 hook JSON 顶层 .cwd 判基准。
# 仅 GNU grep 环境（ubuntu 镜像）运行。

setup() {
    REPO_ROOT="${REPO_ROOT:-$(cd "$BATS_TEST_DIRNAME/../.." && pwd)}"
    # 沙箱必须放 / 下而非 /tmp——firewall 豁免表含 /tmp/*，HOME 在 /tmp 会使
    # 所有 $HOME/projects/* 保护路径被豁免掉，拦截侧断言全部假绿
    TEST_DIR=$(mktemp -d /bf-XXXXXX)
    HOOKS="$REPO_ROOT/config-templates/default/hooks"
    # HOME 沙箱：PROTECTED_REPOS/BLOCK_LOG 均按 $HOME 展开，拦截副作用不落真实家目录
    export HOME="$TEST_DIR/home"
    mkdir -p "$HOME/.claude/logs" "$HOME/projects/UMES3/src" "$HOME/wt/proj/task/UMES3/src"
    SID="bf-test-$$-$BATS_TEST_NUMBER"
    cd "$TEST_DIR"
}

teardown() {
    rm -rf "$TEST_DIR"
}

# call_firewall <command> [cwd] → RC
call_firewall() {
    RC=0
    printf '{"tool_name":"Bash","tool_input":{"command":"%s"},"session_id":"%s","cwd":"%s"}' "$1" "$SID" "${2:-$TEST_DIR}" \
        | bash "$HOOKS/bash-firewall.sh" >/dev/null 2>&1 || RC=$?
}

@test "主仓 *.md 重定向 → 放行（Edit 通道同文件放行，口径必须一致——反馈原案 RULES.md）" {
    call_firewall "cat /etc/hostname >> $HOME/projects/UMES3/RULES.md"
    [ "$RC" -eq 0 ]
}

@test "相对路径目标 → 现状放行（sanitize_path 只收 / 与 ~ 开头，相对 token 被政策丢弃——已知防护漏拦，放宽须防误拦回归）" {
    call_firewall "cat /etc/hostname > src/a.ts" "$HOME/projects/UMES3"
    [ "$RC" -eq 0 ]
}

@test "~ 展开目标按主仓判定 → exit 2（.cwd/resolve 通道不回退）" {
    call_firewall "echo x > ~/projects/UMES3/src/c.ts"
    [ "$RC" -eq 2 ]
}

@test "顶层 .cwd 下相对写主仓 .md → 放行（豁免优先于路径判定）" {
    call_firewall "cat /etc/hostname > NOTES.md" "$HOME/projects/UMES3"
    [ "$RC" -eq 0 ]
}

@test "cp 进主仓 node_modules → 放行（依赖目录非源码资产）" {
    call_firewall "cp /tmp/x.js $HOME/projects/UMES3/react-scaffold/node_modules/"
    [ "$RC" -eq 0 ]
}

@test "主仓 package.json 重定向 → 仍拦截（口径守卫：豁免严格 *.md，不收 json/yaml）" {
    call_firewall "echo x > $HOME/projects/UMES3/package.json"
    [ "$RC" -eq 2 ]
}

@test "worktree 写源文件 → 放行" {
    call_firewall "echo x > $HOME/wt/proj/task/UMES3/src/a.ts"
    [ "$RC" -eq 0 ]
}

@test "主仓源文件绝对路径重定向 → exit 2（原行为不回退）" {
    call_firewall "echo x > $HOME/projects/UMES3/src/b.ts"
    [ "$RC" -eq 2 ]
}
