# -*- bats -*-
# DEFECT-008 退役清理通道：RETIRED.txt + prune_retired()（--update 时执行）
# HOME 沙箱由 helpers 提供，退役残留预置在沙箱 ~/.claude/ 下

load /code/tests/helpers/common.bash

seed_retired() {
    mkdir -p "$TEST_HOME/.claude/skills/caveman" "$TEST_HOME/.claude/skills/keep-me" \
             "$TEST_HOME/.claude/workflows" "$TEST_HOME/.claude/gate-checklists"
    echo x > "$TEST_HOME/.claude/skills/caveman/SKILL.md"
    echo x > "$TEST_HOME/.claude/skills/keep-me/SKILL.md"
    echo x > "$TEST_HOME/.claude/workflows/wf-gate-1-grill.js"
    echo x > "$TEST_HOME/.claude/gate-checklists/gate-2-prd.md"
}

@test "prune: 退役三载体 mv 进 skill-backups，非退役项不动" {
    bash /code/install.sh "$TEST_PROJECT" --mode backend >/dev/null 2>&1
    seed_retired
    run bash /code/install.sh "$TEST_PROJECT" --update
    [ "$status" -eq 0 ]
    [ ! -e "$TEST_HOME/.claude/skills/caveman" ]
    [ ! -e "$TEST_HOME/.claude/workflows/wf-gate-1-grill.js" ]
    [ ! -e "$TEST_HOME/.claude/gate-checklists/gate-2-prd.md" ]
    [ -e "$TEST_HOME/.claude/skills/keep-me/SKILL.md" ]
    ls "$TEST_HOME/.claude/skill-backups/" | grep -q "^caveman.pruned-"
    [ -f "$TEST_HOME/.claude/skill-backups/workflows/wf-gate-1-grill.js" ]
    [ -f "$TEST_HOME/.claude/skill-backups/checklists/gate-2-prd.md" ]
    [[ "$output" =~ "退役清理" ]]
    [[ "$output" =~ "请人工清理" ]]
}

@test "prune: 幂等——无残留时零动作零提示" {
    bash /code/install.sh "$TEST_PROJECT" --mode backend >/dev/null 2>&1
    seed_retired
    bash /code/install.sh "$TEST_PROJECT" --update >/dev/null 2>&1
    run bash /code/install.sh "$TEST_PROJECT" --update
    [ "$status" -eq 0 ]
    [[ ! "$output" =~ "退役清理" ]]
    # 备份仍只有一份（未重复搬移）
    [ "$(ls "$TEST_HOME/.claude/skill-backups/" | grep -c "^caveman.pruned-")" = "1" ]
}

@test "prune: dry-run 不真实搬移" {
    bash /code/install.sh "$TEST_PROJECT" --mode backend >/dev/null 2>&1
    seed_retired
    run bash /code/install.sh "$TEST_PROJECT" --update --dry-run
    [ "$status" -eq 0 ]
    [ -e "$TEST_HOME/.claude/skills/caveman/SKILL.md" ]
    [ -e "$TEST_HOME/.claude/workflows/wf-gate-1-grill.js" ]
}

@test "retired-list: RETIRED.txt 三类前缀格式合法且覆盖 wf-gate 全 8 项" {
    grep -vE '^(#|$)' /code/RETIRED.txt | grep -vcE '^(skill|wf|checklist):[^ ]+' | grep -q '^0$'
    [ "$(grep -c '^wf:gate-' /code/RETIRED.txt)" = "8" ]
}
