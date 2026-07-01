#!/bin/bash
# test-dispatch.sh — dispatch/reconcile worktree 替换集成测试
# 用法: bash test-dispatch.sh <项目路径>
# 设计: AAA 模式（Arrange → Act → Assert），幂等可重复，自动清理
set -euo pipefail

WORKSPACE="${1:-$(pwd)}"
ARCHON_DIR="$WORKSPACE/.devflow/archon"
SCRIPTS_DIR="$WORKSPACE/.devflow/scripts"
ISSUES_DIR="$WORKSPACE/issues"
MOCK_ISSUE="$ISSUES_DIR/000-TEST-001-worktree-mock.md"
PASS=0
FAIL=0
SKIP=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

assert() {
    local desc="$1"; local cmd="$2"; local blocker="${3:-false}"
    printf "  %-55s" "$desc ..."
    if eval "$cmd" 2>/dev/null; then
        echo -e "${GREEN}✅ PASS${NC}"
        PASS=$((PASS + 1))
        return 0
    else
        echo -e "${RED}❌ FAIL${NC}"
        FAIL=$((FAIL + 1))
        if [ "$blocker" = "true" ]; then
            echo -e "  ${RED}⛔ 阻断级测试失败，终止${NC}"
            exit 1
        fi
        return 1
    fi
}

#───────────────────────────────────────────────────────────
# 前置检查
#───────────────────────────────────────────────────────────
echo "=========================================="
echo " dispatch/reconcile worktree 集成测试"
echo " 项目: $WORKSPACE"
echo "=========================================="
echo ""

[ -d "$ARCHON_DIR" ] || { echo "❌ archon 目录不存在: $ARCHON_DIR"; exit 1; }
[ -f "$SCRIPTS_DIR/check_constitution.py" ] || { echo "❌ check_constitution.py 不存在"; exit 1; }

#───────────────────────────────────────────────────────────
# Phase 1: 静态分析
#───────────────────────────────────────────────────────────
echo "=== Phase 1: 静态分析 ==="
echo ""

echo "--- dispatch.sh ---"
assert "语法检查" "bash -n $ARCHON_DIR/dispatch.sh" true
assert "无 git stash 残留" "! grep -v '^\s*#' $ARCHON_DIR/dispatch.sh | grep -qE 'git stash (push|pop|apply|save)'" true
assert "DISPATCH_WT 变量存在" "grep -q 'DISPATCH_WT' $ARCHON_DIR/dispatch.sh" true
assert "cleanup_exit 含 worktree remove" "grep -q 'git worktree remove.*DISPATCH_WT' $ARCHON_DIR/dispatch.sh" true
assert "cleanup_exit 含 worktree prune" "grep -q 'git worktree prune' $ARCHON_DIR/dispatch.sh" true
assert "trap 含 EXIT INT TERM" "grep -qE 'trap cleanup_exit EXIT INT TERM' $ARCHON_DIR/dispatch.sh" true
assert "git push 用 HEAD:main" "grep -qE 'git push.*HEAD:main' $ARCHON_DIR/dispatch.sh" true

echo ""
echo "--- reconciler.sh ---"
assert "语法检查" "bash -n $ARCHON_DIR/reconciler.sh" true
assert "无 git stash 残留" "! grep -qE 'git stash (push|pop|apply|save)' $ARCHON_DIR/reconciler.sh" true
assert "RECONCILE_WT 变量存在" "grep -q 'RECONCILE_WT' $ARCHON_DIR/reconciler.sh" true
assert "cleanup_exit 含 worktree remove" "grep -q 'git worktree remove.*RECONCILE_WT' $ARCHON_DIR/reconciler.sh" true

echo ""
echo "--- auto-execute-afk.yaml ---"
assert "无 git stash 残留" "! grep -qE 'git stash (push|pop|apply|save)' $ARCHON_DIR/auto-execute-afk.yaml" true
assert "autostash 至少 2 处" "[ \$(grep -c 'autostash' $ARCHON_DIR/auto-execute-afk.yaml) -ge 2 ]" true

#───────────────────────────────────────────────────────────
# Phase 2: Worktree 单元测试
#───────────────────────────────────────────────────────────
echo ""
echo "=== Phase 2: Worktree 隔离单元测试 ==="
echo ""

# 测试 1: mktemp -d && rmdir 获取唯一路径
WT_NAME=$(mktemp -d /tmp/test-wt-XXXXXX 2>/dev/null) && rmdir "$WT_NAME" || {
    echo -e "  ${RED}❌ FAIL — mktemp 失败${NC}"
    FAIL=$((FAIL + 1))
}
assert "mktemp 获取唯一路径（目录不存在）" "[ -n '${WT_NAME:-}' ] && [ ! -d '${WT_NAME:-/nonexistent}' ]"

# 测试 2: worktree 创建
WT_BASELINE=$(git -C "$WORKSPACE" worktree list 2>/dev/null | wc -l)
assert "worktree 创建 (detached HEAD)" "git -C $WORKSPACE worktree add $WT_NAME origin/main --detach 2>/dev/null"
assert "issues/ 目录可访问" "[ -d $WT_NAME/issues ]"
assert "worktree 数量 +1" "[ \$(git -C $WORKSPACE worktree list | wc -l) -eq $((WT_BASELINE + 1)) ]"

# 测试 3: worktree remove
git -C "$WORKSPACE" worktree remove "$WT_NAME" --force 2>/dev/null || true
assert "worktree remove 成功（目录已删除）" "[ ! -d $WT_NAME ]"
assert "worktree 数量回归基线" "[ \$(git -C $WORKSPACE worktree list | wc -l) -le $WT_BASELINE ]"

# 测试 4: worktree prune
git -C "$WORKSPACE" worktree prune 2>/dev/null || true
assert "worktree prune 无副作用" "[ \$(git -C $WORKSPACE worktree list | wc -l) -le $WT_BASELINE ]"

# 测试 5: 重复创建→移除 3 次，无泄漏
LEAK=0
for i in 1 2 3; do
    WT_N=$(mktemp -d /tmp/test-wt-loop-XXXXXX) && rmdir "$WT_N"
    git -C "$WORKSPACE" worktree add "$WT_N" origin/main --detach 2>/dev/null || { LEAK=1; break; }
    git -C "$WORKSPACE" worktree remove "$WT_N" --force 2>/dev/null || true
done
assert "重复创建→移除 3 次无泄漏" "[ $LEAK -eq 0 ] && [ \$(git -C $WORKSPACE worktree list | wc -l) -le $WT_BASELINE ]"

#───────────────────────────────────────────────────────────
# Phase 3: 集成测试 — Mock Issue 全流程
#───────────────────────────────────────────────────────────
echo ""
echo "=== Phase 3: 集成测试（Mock Issue 全流程）==="
echo ""

# Arrange: 创建 mock issue
cat > "$MOCK_ISSUE" << 'ISSUEEOF'
---
type: AFK
estimate: 0.5d
effort: small
status: ready
blocked_by: []
needs_llm: true
needs_vision: false
needs_pdf: false
needs_docker: false
test_files: ["tests/test_mock.py"]
---

# TEST: Worktree 集成测试

## 背景
自动化测试 mock issue，验证 dispatch.sh 的 worktree 隔离机制。

## Acceptance Criteria
- [ ] AC1: dispatch 成功创建 worktree（从 origin/main --detach）
- [ ] AC2: dispatch 退出后 worktree 已清理（git worktree list 数量回归）
- [ ] AC3: 日志无 FATAL 或 stash 残留

## 代码目录
- 实现: `src/`（不存在，预期 Archon 失败）
- 测试: `tests/test_mock.py`（不存在）
ISSUEEOF

assert "mock issue 创建" "[ -f $MOCK_ISSUE ]"

# Arrange: 宪法检查
CONSTITUTION_OUT=$(python3 "$SCRIPTS_DIR/check_constitution.py" "$MOCK_ISSUE" --json 2>&1 || true)
CONSTITUTION_FAILED=$(echo "$CONSTITUTION_OUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('failed',99))" 2>/dev/null || echo 99)
assert "宪法检查通过（failed=0）" "[ '$CONSTITUTION_FAILED' = '0' ]" true

# Arrange: 提交 mock issue 到远程（dispatch 需要从 origin/main fetch）
cd "$WORKSPACE"
git add "$MOCK_ISSUE" 2>/dev/null
git commit -m "test: mock issue for dispatch worktree test" 2>/dev/null || true
git push 2>/dev/null || { echo -e "  ${YELLOW}⚠️  SKIP — git push 失败，跳过集成测试${NC}"; SKIP=$((SKIP + 1)); }

if [ $SKIP -eq 0 ]; then
    # Arrange: 记录基线
    WT_PHASE3_BEFORE=$(git -C "$WORKSPACE" worktree list 2>/dev/null | wc -l)

    # Act: 运行 dispatch
    echo "  运行 dispatch.sh ..."
    DISPATCH_OUT=$(sudo -u www bash "$ARCHON_DIR/dispatch.sh" "$WORKSPACE" 2>&1) || true

    # Assert: worktree 无残留
    WT_PHASE3_AFTER=$(git -C "$WORKSPACE" worktree list 2>/dev/null | wc -l)
    assert "worktree 无残留（${WT_PHASE3_BEFORE}→${WT_PHASE3_AFTER}）" "[ $WT_PHASE3_AFTER -le $WT_PHASE3_BEFORE ]" true

    # Assert: 日志无 FATAL/stash
    LOG_TAIL=$(tail -30 "$WORKSPACE/logs/dispatch.log" 2>/dev/null || echo "")
    assert "日志无 FATAL" "! echo \"\$LOG_TAIL\" | grep -q 'FATAL'" true
    assert "日志无 stash" "! echo \"\$LOG_TAIL\" | grep -q 'stash'"

    # Assert: issue 状态已变更
    ISSUE_STATUS=$(grep '^status:' "$MOCK_ISSUE" 2>/dev/null | awk '{print $2}' || echo "unchanged")
    assert "issue 状态已变更（ready→${ISSUE_STATUS}）" "[ '$ISSUE_STATUS' != 'ready' ]"

    # Cleanup: 删除 mock issue + push
    rm -f "$MOCK_ISSUE"
    cd "$WORKSPACE"
    git add "$MOCK_ISSUE" 2>/dev/null || true
    git commit -m "test: cleanup mock issue" 2>/dev/null || true
    git push 2>/dev/null || true
else
    rm -f "$MOCK_ISSUE"
    cd "$WORKSPACE"
    git reset --hard HEAD~1 2>/dev/null || true
fi
assert "mock issue 已清理" "[ ! -f $MOCK_ISSUE ]"

#───────────────────────────────────────────────────────────
# Phase 4: 故障模式测试
#───────────────────────────────────────────────────────────
echo ""
echo "=== Phase 4: 故障模式测试 ==="
echo ""

# 4a: git fetch 失败
echo "--- 4a: git fetch 失败 ---"
ORIG_REMOTE=$(git -C "$WORKSPACE" remote get-url origin 2>/dev/null || echo "")
if [ -n "$ORIG_REMOTE" ]; then
    git -C "$WORKSPACE" remote set-url origin /nonexistent/repo 2>/dev/null || true
    FETCH_FAIL_OUT=$(sudo -u www bash "$ARCHON_DIR/dispatch.sh" "$WORKSPACE" 2>&1) || true
    git -C "$WORKSPACE" remote set-url origin "$ORIG_REMOTE" 2>/dev/null || true
    WT_MID=$(git -C "$WORKSPACE" worktree list 2>/dev/null | wc -l)
    assert "git fetch 失败时 exit 1" "echo \"\$FETCH_FAIL_OUT\" | grep -q 'FATAL.*fetch'"
    assert "fetch 失败后 worktree 无残留" "[ $WT_MID -le $WT_BASELINE ]"
else
    echo -e "  ${YELLOW}⚠️  SKIP — 无法获取 remote URL${NC}"
    SKIP=$((SKIP + 1))
fi

# 4b: SIGTERM 中断（手动执行指南）
echo ""
echo "--- 4b: SIGTERM 中断（手动验证步骤）---"
echo "  此测试需手动执行（自动化不可靠）："
echo ""
echo "  # 终端1: 创建第二个 mock issue，运行 dispatch"
echo "  sudo -u www bash $ARCHON_DIR/dispatch.sh $WORKSPACE &"
echo "  PID=\$!"
echo "  sleep 2  # 等 dispatch 进入 worktree"
echo "  kill -TERM \$PID"
echo ""
echo "  # 终端2: 立即检查"
echo "  git -C $WORKSPACE worktree list"
echo "  # 预期: 无残留 dispatch-* worktree"
echo "  tail -5 $WORKSPACE/logs/dispatch.log"
echo "  # 预期: 无 FATAL（SIGTERM 是预期退出路径）"
echo ""

#───────────────────────────────────────────────────────────
# Phase 5: Reconciler 测试
#───────────────────────────────────────────────────────────
echo "=== Phase 5: Reconciler 测试 ==="
echo ""

WT_PHASE5_BEFORE=$(git -C "$WORKSPACE" worktree list 2>/dev/null | wc -l)

echo "  运行 reconciler.sh ..."
sudo -u www bash "$ARCHON_DIR/reconciler.sh" "$WORKSPACE" 2>&1 || true

WT_PHASE5_AFTER=$(git -C "$WORKSPACE" worktree list 2>/dev/null | wc -l)
assert "reconciler worktree 无残留（${WT_PHASE5_BEFORE}→${WT_PHASE5_AFTER}）" "[ $WT_PHASE5_AFTER -le $WT_PHASE5_BEFORE ]"

RECONCILE_LOG_TAIL=$(tail -20 "$WORKSPACE/logs/reconcile.log" 2>/dev/null || echo "")
assert "reconciler 日志无 FATAL" "! echo \"\$RECONCILE_LOG_TAIL\" | grep -q 'FATAL'"
assert "reconciler 日志无 stash" "! echo \"\$RECONCILE_LOG_TAIL\" | grep -q 'stash'"

#───────────────────────────────────────────────────────────
# 汇总
#───────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo " 测试结果"
echo "=========================================="
echo -e " ${GREEN}✅ PASS${NC}: $PASS"
echo -e " ${RED}❌ FAIL${NC}: $FAIL"
echo -e " ${YELLOW}⚠️  SKIP${NC}: $SKIP"
echo ""

if [ $FAIL -gt 0 ]; then
    echo -e "${RED}❌ 有 $FAIL 项测试失败，部署前必须修复${NC}"
    exit 1
else
    echo -e "${GREEN}✅ 全部 $PASS 项通过${NC}"
fi
