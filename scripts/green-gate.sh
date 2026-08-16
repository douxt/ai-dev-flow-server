#!/bin/bash
# green-gate.sh — GREEN 侧提交前秒检（跨项目通用）
# 用途：/implement 阶段 GREEN commit 前自动检查，防 AI 假 GREEN
# 部署：ai-dev-flow-server --update 自动部署到 .devflow/scripts/
#
# 与 test-gate.sh（RED 侧）互补——test-gate 查"测试写对了吗"，green-gate 查"实现写对了吗"

set -euo pipefail

# ── 定位 RED commit ──
RED_COMMIT=$(git log --oneline --grep="TDD: RED" -1 --format="%H" 2>/dev/null || true)
if [ -z "$RED_COMMIT" ]; then
    echo "[green-gate] ⚠️ 未找到 TDD: RED commit，以 HEAD~1 为基线"
    RED_COMMIT="HEAD~1"
fi

echo "=== green-gate: GREEN 侧提交前秒检 ==="
echo "  基线: $(git log --oneline -1 --format='%h %s' "$RED_COMMIT")"
echo "  HEAD: $(git log --oneline -1 --format='%h %s' HEAD)"

WARN=0

# ── G2.1: GREEN 阶段不应修改测试文件 ──
echo ""
echo "--- G2.1: 测试文件不应在 GREEN 阶段被修改 ---"
TEST_CHANGES=$(git diff "$RED_COMMIT"..HEAD --name-only --diff-filter=M | grep -E '(\.spec\.|\.test\.|_test\.go$|^tests/|^test/|^__tests__/|^e2e/)' || true)
if [ -n "$TEST_CHANGES" ]; then
    COUNT=$(echo "$TEST_CHANGES" | grep -c . || echo "0")
    echo "⚠️  发现 ${COUNT} 个测试文件在 GREEN 阶段被修改（不应修改测试来适配实现）:"
    echo "$TEST_CHANGES" | sed 's/^/    /'
    echo "  提示: 测试 = spec 的可执行版本。如测试确实有 bug，应在 commit message 中标注 TEST_FIX: <原因>"
    WARN=1
else
    echo "✅ 零命中"
fi

# ── G2.2: 无硬编码空数据 ──
echo ""
echo "--- G2.2: 无硬编码空数据 ---"
EMPTY_DATA=$(git diff "$RED_COMMIT"..HEAD | grep -E '^\+\s*.*data\s*:\s*\[\]|^\+\s*.*data\s*:\s*\{\}|^\+\s*.*return\s+\{\s*code\s*:\s*0\s*,\s*\}$' || true)
if [ -n "$EMPTY_DATA" ]; then
    COUNT=$(echo "$EMPTY_DATA" | grep -c . || echo "0")
    echo "⚠️  发现 ${COUNT} 处疑似硬编码空数据（data: [] / data: {} / 空 return {code:0}）:"
    echo "$EMPTY_DATA" | head -10 | sed 's/^/    /'
    [ "$COUNT" -gt 10 ] && echo "    ... 共 ${COUNT} 处"
    echo "  提示: 可能是 mock 残留或未完成实现，人工确认"
    WARN=1
else
    echo "✅ 零命中"
fi

# ── G2.3: 无 skip/only 残留（限定 diff 范围）──
echo ""
echo "--- G2.3: 无 skip/only 残留 ---"
SKIP_ONLY=$(git diff "$RED_COMMIT"..HEAD | grep -E '^\+\s*.*(test\.only|describe\.only|it\.only|\.skip\()' || true)
if [ -n "$SKIP_ONLY" ]; then
    COUNT=$(echo "$SKIP_ONLY" | grep -c . || echo "0")
    echo "⚠️  发现 ${COUNT} 处 skip/only 残留（diff 中新增行）:"
    echo "$SKIP_ONLY" | head -5 | sed 's/^/    /'
    [ "$COUNT" -gt 5 ] && echo "    ... 共 ${COUNT} 处"
    echo "  提示: test.only 是调试残留，.skip 可能绕过失败测试"
    WARN=1
else
    echo "✅ 零命中"
fi

# ── 结果 ──
echo ""
echo "============================================"
if [ $WARN -eq 0 ]; then
    echo "✅ green-gate G2.1-G2.3 全部通过"
    exit 0
else
    echo "⚠️  green-gate 有标记项——需人工确认后方可提交 GREEN commit"
    echo "   exit 1 — 标记项未解决（GREEN_GATE_WARN_ONLY=1 可切换为 advisory）"
    if [ "${GREEN_GATE_WARN_ONLY:-0}" = "1" ]; then
        exit 0
    else
        exit 1
    fi
fi
