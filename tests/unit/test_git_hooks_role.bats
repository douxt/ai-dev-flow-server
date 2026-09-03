# -*- bats -*-
# v3.6 钩子角色门：pre-push(dst_ref 判定/双因子/删除与新建语义) + pre-commit + 全局串联 + update 刷新链
# 夹具 stdin 行格式 = git pre-push 协议: <src_ref> <src_oid> <dst_ref> <dst_oid>

setup() {
    REPO_ROOT="${REPO_ROOT:-$(git -C "$BATS_TEST_DIRNAME/../.." rev-parse --show-toplevel 2>/dev/null || pwd)}"
    PRE_PUSH="$REPO_ROOT/templates/pre-push"
    PRE_COMMIT="$REPO_ROOT/templates/pre-commit"
    CHAIN="$REPO_ROOT/templates/global-git-hooks/pre-push"
    T=$(mktemp -d)
    R="$T/repo"
    mkdir -p "$R/.devflow" "$R/.git/hooks"
    git -C "$R" init -q
    git -C "$R" -c user.email=t@t -c user.name=t commit -q --allow-empty -m init
    SHA=$(git -C "$R" rev-parse HEAD)
    Z=0000000000000000000000000000000000000000
    cp "$PRE_PUSH" "$R/.git/hooks/pre-push"
    cp "$PRE_COMMIT" "$R/.git/hooks/pre-commit"
    chmod +x "$R/.git/hooks/pre-push" "$R/.git/hooks/pre-commit"  # 生产由 install chmod_x 保证；git 只执行可 x 的 hook
}

teardown() { [ -n "${T:-}" ] && [ -d "$T" ] && rm -rf "$T"; }

set_role() { printf 'project:\n  name: t\nmode: backend\nrole: %s\n' "$1" > "$R/.devflow/config.yaml"; }

pp() { # pp <repo> [env assignments...] —— 喂 stdin 模拟 git 调 pre-push
    local repo="$1"; shift
    local line="$SRCDST"
    ( cd "$repo" && env "$@" bash .git/hooks/pre-push origin https://example.invalid/x.git <<< "$line" )
}

@test "缺省 role(agent-b) 直推 master → 拦截且文案含策略与出路" {
    SRCDST="refs/heads/master $SHA refs/heads/master $SHA"
    run pp "$R"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "policy: role=agent-b" ]]
    [[ "$output" != *"Agent B"* ]]
}

@test "role 带引号 + OWNER_SESSION=1 → 放行且 gitdir 留痕 owner-bypass（剥引号+trace 落位双验）" {
    set_role '"owner"'
    SRCDST="refs/heads/master $SHA refs/heads/master $SHA"
    run pp "$R" OWNER_SESSION=1
    [ "$status" -eq 0 ]
    grep -q '"event":"owner-bypass"' "$R/.git/devflow-trace.jsonl"
}

@test "role=owner 无 OWNER_SESSION → 拦截 + trace blocked" {
    set_role owner
    SRCDST="refs/heads/master $SHA refs/heads/master $SHA"
    run pp "$R"
    [ "$status" -eq 1 ]
    grep -q '"event":"blocked"' "$R/.git/devflow-trace.jsonl"
}

@test "绕过反例：从 ai/x 分支 push HEAD:master（v2 HEAD 判定洞）→ 仍拦" {
    git -C "$R" branch ai/x
    git -C "$R" checkout -q ai/x
    SRCDST="HEAD $SHA refs/heads/master $SHA"
    run pp "$R"
    [ "$status" -eq 1 ]
}

@test "删除行(src_oid 全零) dst=master → 放行；新建 dst=master(dst_oid 全零) → 拦截" {
    SRCDST="(delete) $Z refs/heads/master $Z"
    run pp "$R"; [ "$status" -eq 0 ]
    SRCDST="refs/heads/devlop $SHA refs/heads/master $Z"
    run pp "$R"; [ "$status" -eq 1 ]
}

@test "全局串联在 linked worktree 内生效（git-common-dir 版，v1 相对路径真空已修）" {
    set_role owner
    # .devflow 须被 git 跟踪——worktree checkout 从 commit 取文件（生产租户 .devflow 均在库内）
    # OWNER_SESSION=1：本仓钩子已是角色门版，跟踪 .devflow 属受保护提交（dogfood 放行）
    git -C "$R" add .devflow && OWNER_SESSION=1 git -C "$R" -c user.email=t@t -c user.name=t commit -q -m track-devflow
    WT="$T/wt"
    git -C "$R" worktree add -q --detach "$WT"
    SRCDST="refs/heads/devlop $SHA refs/heads/master $SHA"
    # 无 env：串联进仓钩子 → 拦截
    run bash -c "cd '$WT' && printf '%s\n' '$SRCDST' | bash '$CHAIN' origin url"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "policy: role=owner" ]]
}

@test "pre-commit 角色门：保护路径 owner+env 放行留痕 / agent-b 拦截新文案" {
    # agent-b（无 config.yaml role）
    echo x > "$R/.devflow/stage"; git -C "$R" add .devflow/stage
    run git -C "$R" -c user.email=t@t -c user.name=t commit -m test
    [ "$status" -ne 0 ]
    [[ "$(cat "$R/.git/devflow-trace.jsonl" 2>/dev/null)" == *'"hook":"pre-commit","event":"blocked"'* ]]
    # owner + env
    set_role owner
    OWNER_SESSION=1 git -C "$R" -c user.email=t@t -c user.name=t commit -q -m test
    [ -f "$R/.devflow/stage" ]
    grep -q '"event":"owner-bypass"' "$R/.git/devflow-trace.jsonl"
}

@test "update 刷新链：钩子模板变更经 --update 落仓+bak；worktree 目标跳过不崩" {
    command -v bats >/dev/null
    # 简化夹具：手工 config + 旧版钩子；HOME 必须沙箱（否则 update 段写真实 ~/.claude）
    printf 'project:\n  name: t\nmode: backend\nrole: owner\n' > "$R/.devflow/config.yaml"
    echo "#!/bin/bash" > "$R/.git/hooks/pre-push"   # 模拟旧版占位
    echo old > "$R/.git/hooks/pre-commit"
    HOME="$T" bash "$REPO_ROOT/install.sh" "$R" --update >/dev/null 2>&1
    cmp -s "$R/.git/hooks/pre-push" "$PRE_PUSH"
    ls "$R/.git/hooks/" | grep -q "pre-push.bak-"
    grep -q "hooks.change" "$R/.git/devflow-trace.jsonl"
    # worktree 目标（.git 是文件）→ 跳过不崩
    WT="$T/wt2"; git -C "$R" worktree add -q --detach "$WT"
    mkdir -p "$WT/.devflow"; cp "$R/.devflow/config.yaml" "$WT/.devflow/"
    run bash -c "HOME='$T' bash '$REPO_ROOT/install.sh' '$WT' --update"
    [ "$status" -eq 0 ]
    [ -f "$WT/.git" ]   # 确认这确实是 worktree 文件形态
}
