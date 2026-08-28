# -*- bats -*-
# M0 stacks 知识保鲜（FEEDBACK-002）：green-gate G2.5 + install.sh reviewed_at 注入

setup() {
    TEST_DIR=$(mktemp -d)
    REPO_ROOT="${REPO_ROOT:-$(git -C "$BATS_TEST_DIRNAME/../.." rev-parse --show-toplevel 2>/dev/null || pwd)}"
    GG="$REPO_ROOT/scripts/green-gate.sh"
    INSTALL="$REPO_ROOT/install.sh"
    # fixture 项目：.devflow/scripts + .devflow/knowledge/stacks（green-gate 以 SCRIPT_DIR/.. 锚定）
    PROJ="$TEST_DIR/proj"
    mkdir -p "$PROJ/.devflow/scripts" "$PROJ/.devflow/knowledge/stacks/go"
    cp "$GG" "$PROJ/.devflow/scripts/green-gate.sh"
    # git fixture：G2.1 基线需 HEAD~1 存在 → 两个 commit
    git -C "$PROJ" init -q
    git -C "$PROJ" -c user.email=t@t -c user.name=t add -A
    git -C "$PROJ" -c user.email=t@t -c user.name=t commit -qm base
    echo x > "$PROJ/f.txt"
    git -C "$PROJ" -c user.email=t@t -c user.name=t add -A
    git -C "$PROJ" -c user.email=t@t -c user.name=t commit -qm second
    # 固定阈值防真实日期漂移，双镜像（busybox/GNU date）确定性
    export GREEN_GATE_REVIEW_THRESHOLD="2026-05-30"
}

teardown() {
    [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ] && rm -rf "$TEST_DIR"
}

make_md() { # make_md <reviewed_at 行内容|__NONE__>
    if [ "$1" = "__NONE__" ]; then
        printf '# t\n\n> 技术栈模块\n\nbody\n' > "$PROJ/.devflow/knowledge/stacks/go/a.md"
    else
        printf '# t\n\n> 技术栈模块\n> reviewed_at: %s\n> status: current\n\nbody\n' "$1" > "$PROJ/.devflow/knowledge/stacks/go/a.md"
    fi
}

@test "G2.5: reviewed_at 超阈值 → WARN 含文件名" {
    make_md "2026-01-01"
    run bash "$PROJ/.devflow/scripts/green-gate.sh"
    [[ "$output" =~ "栈知识超 90 天待重审: go/a.md (reviewed_at: 2026-01-01)" ]]
}

@test "G2.5: reviewed_at 在保鲜期 → 无提示" {
    make_md "2026-05-31"
    run bash "$PROJ/.devflow/scripts/green-gate.sh"
    [[ "$output" =~ "G2.5" ]]
    [[ ! "$output" =~ "待重审" ]]
}

@test "G2.5: 缺 reviewed_at 行（旧版模板）→ 不判不报" {
    make_md "__NONE__"
    run bash "$PROJ/.devflow/scripts/green-gate.sh"
    [[ ! "$output" =~ "待重审" ]]
}

@test "G2.5: 无 stacks 目录 → 跳过声明" {
    rm -rf "$PROJ/.devflow/knowledge/stacks"
    run bash "$PROJ/.devflow/scripts/green-gate.sh"
    [[ "$output" =~ "无 stacks 目录，跳过" ]]
}

@test "inject: 占位符被刷为当天且已审文件不覆写" {
    printf '# t\n\n> 技术栈模块\n> reviewed_at: __REVIEWED_AT__\n> status: current\n' > "$PROJ/placeholder.md"
    printf '# t\n\n> 技术栈模块\n> reviewed_at: 2026-01-01\n> status: current\n' > "$PROJ/reviewed.md"
    # 提取 install.sh 中的注入函数与 dry_run（不执行 install 主体）
    eval "$(awk '/^dry_run\(\)/,/^}/' "$INSTALL")"
    eval "$(awk '/^inject_stacks_reviewed_at\(\)/,/^}/' "$INSTALL")"
    DRY_RUN=false
    run inject_stacks_reviewed_at "$PROJ"
    [ "$status" -eq 0 ]
    grep -q "reviewed_at: $(date +%F)" "$PROJ/placeholder.md"
    grep -q "reviewed_at: 2026-01-01" "$PROJ/reviewed.md"
}

@test "template: 平台 12 个 stacks 文件全部含占位符与 status" {
    count=$(find "$REPO_ROOT/knowledge/stacks" -name '*.md' | wc -l)
    [ "$count" -eq 12 ]
    bad=$(grep -rL '__REVIEWED_AT__' "$REPO_ROOT/knowledge/stacks"/*/*.md | wc -l)
    [ "$bad" -eq 0 ]
    bad2=$(grep -rL '> status: current' "$REPO_ROOT/knowledge/stacks"/*/*.md | wc -l)
    [ "$bad2" -eq 0 ]
}
