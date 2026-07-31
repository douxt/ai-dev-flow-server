#!/bin/bash
# test-gate.sh — 测试门禁秒检（跨项目通用）
# 用途：RED commit 前自动执行 C0.1-C0.5，不通过则阻断
# 部署：ai-dev-flow-server --update 自动部署到 .devflow/scripts/
# 扩展：项目可在 scripts/test-gate.sh 中追加 C6+/G2/G4 等项目特化检查
#
# 参考：.claude/gate-checklists/test-checklist.md §C0

set -euo pipefail
FAIL=0

# ── 检测测试目录 ──
TESTS_DIR=""
for d in tests test __tests__ spec e2e; do
    [ -d "$d" ] && { TESTS_DIR="$d"; break; }
done
if [ -z "$TESTS_DIR" ]; then
    echo "[test-gate] ⚠️ 未找到测试目录，跳过"
    exit 0
fi

echo "=== test-gate: C0 提交前秒检 ==="
echo "  测试目录: $TESTS_DIR"

# ── C0.1: 无调试残留 ──
echo ""
echo "--- C0.1: 无调试残留 ---"
HITS=$(grep -rn "test\.only\|describe\.only\|it\.only\|page\.pause" "$TESTS_DIR" \
    --exclude-dir=characterization \
    --exclude='*.bak' --exclude='*.bak2' --exclude='*.bak-*' --exclude='*.skip' 2>/dev/null || true)
if [ -n "$HITS" ]; then
    echo "❌ 发现 test.only / describe.only / page.pause 残留："
    echo "$HITS"
    FAIL=1
else
    echo "✅ 零命中"
fi

# ── C0.2: 无恒真断言 ──
echo ""
echo "--- C0.2: 无恒真断言 ---"
HITS=$(grep -rn "toBeGreaterThanOrEqual(0)\|typeof.*toBe('number')\|\.toBeTruthy()\|\.toBeDefined()" "$TESTS_DIR" \
    --exclude-dir=characterization \
    --exclude='*.bak' --exclude='*.bak2' --exclude='*.bak-*' --exclude='*.skip' 2>/dev/null || true)
if [ -n "$HITS" ]; then
    echo "❌ 发现恒真断言："
    echo "$HITS"
    FAIL=1
else
    echo "✅ 零命中"
fi

# ── C0.3: 无硬编码端口 ──
echo ""
echo "--- C0.3: 无硬编码端口 ---"
HITS=$(grep -rn "localhost:[0-9]\{4\}" "$TESTS_DIR" \
    --exclude-dir=characterization \
    --exclude='*.bak' --exclude='*.bak2' --exclude='*.bak-*' --exclude='*.skip' 2>/dev/null || true)
# 排除注释行
HITS=$(echo "$HITS" | grep -v "^\s*\/\/\|^\s*\*\|^\s*#" || true)
if [ -n "$HITS" ]; then
    echo "❌ 发现硬编码端口："
    echo "$HITS"
    FAIL=1
else
    echo "✅ 零命中"
fi

# ── C0.4: 固定延时扫描（警告级）──
echo ""
echo "--- C0.4: 固定延时扫描 ---"
HITS=$(grep -rn "waitForTimeout\|page\.waitForTimeout\|setTimeout.*[0-9]\{4,\}" "$TESTS_DIR" \
    --exclude-dir=characterization \
    --exclude='*.bak' --exclude='*.bak2' --exclude='*.bak-*' --exclude='*.skip' 2>/dev/null || true)
if [ -n "$HITS" ]; then
    COUNT=$(echo "$HITS" | wc -l)
    echo "⚠️  发现 ${COUNT} 处固定延时，需人工确认必要"
    echo "$HITS" | head -10
    [ "$COUNT" -gt 10 ] && echo "  ... 共 ${COUNT} 处"
else
    echo "✅ 零命中"
fi

# ── C0.6: try/catch 包裹 expect（警告级）──
echo ""
echo "--- C0.6: try/catch 包裹 expect ---"
# 检测 try 块内包含 expect 且后续有 catch 的模式（腐烂断言高风险）
HITS=$(grep -rn "try\s*{" "$TESTS_DIR" \
    --exclude-dir=characterization \
    --exclude='*.bak' --exclude='*.bak2' --exclude='*.bak-*' --exclude='*.skip' 2>/dev/null || true)
if [ -n "$HITS" ]; then
    # 进一步筛选：try 和 catch 之间是否有 expect
    TRY_CATCH_COUNT=0
    while IFS=: read -r file line rest; do
        if [ -f "$file" ]; then
            # 检查该文件是否存在 try { ... expect ... } catch { ... } 模式
            if grep -Pzo '(?s)try\s*\{[^}]*expect[^}]*\}\s*catch' "$file" > /dev/null 2>&1; then
                TRY_CATCH_COUNT=$((TRY_CATCH_COUNT + 1))
            fi
        fi
    done <<< "$HITS"
    if [ "$TRY_CATCH_COUNT" -gt 0 ]; then
        echo "⚠️  发现 ${TRY_CATCH_COUNT} 处 try/catch 包裹 expect — 需人工确认 catch 块未被 auto-dismiss 时序竞争绕过"
        echo "  提示: catch 块 + antd message/toast/notification 自动消失 = 永远 GREEN"
    else
        echo "✅ 零命中"
    fi
else
    echo "✅ 零命中"
fi

# ── C0.5: 测试实际执行 ──
echo ""
echo "--- C0.5: 测试实际执行 ---"
DISCOVERED=0

# 搜索 playwright config（cwd + 常见子目录）
PW_CONFIG=""
for loc in "playwright.config.js" "playwright.config.ts" \
           "tests/playwright.config.js" "tests/playwright.config.ts" \
           "e2e/playwright.config.js" "e2e/playwright.config.ts"; do
    [ -f "$loc" ] && { PW_CONFIG="$loc"; break; }
done

if [ -n "$PW_CONFIG" ]; then
    # 用 Total: N 解析测试数（方案 A，最可靠——suites 数 ≠ 测试数）
    PW_LIST=$(npx playwright test --config="$PW_CONFIG" --list 2>&1 || true)
    DISCOVERED=$(echo "$PW_LIST" | grep -oP 'Total:\s+\K\d+' || echo "0")
    # fallback: 直接 node 调 playwright 二进制（绕过可能的 npx wrapper/RTK）
    if [ "$DISCOVERED" -eq 0 ] && [ -f "./node_modules/.bin/playwright" ]; then
        PW_LIST2=$(node "./node_modules/.bin/playwright" test --config="$PW_CONFIG" --list 2>&1 || true)
        DISCOVERED=$(echo "$PW_LIST2" | grep -oP 'Total:\s+\K\d+' || echo "0")
    fi
elif [ -f "jest.config.js" ] || [ -f "jest.config.ts" ] || grep -q '"jest"' package.json 2>/dev/null; then
    DISCOVERED=$(npx jest --listTests 2>/dev/null | wc -l || echo "0")
elif [ -f "phpunit.xml" ] || [ -f "phpunit.xml.dist" ]; then
    DISCOVERED=$(php vendor/bin/phpunit --list-tests 2>/dev/null | grep -c '^\s*-' || echo "0")
elif command -v pytest &>/dev/null; then
    DISCOVERED=$(python3 -m pytest --collect-only -q 2>/dev/null | grep -c '::' || echo "0")
elif command -v go &>/dev/null; then
    DISCOVERED=$(go test ./... -list '.*' 2>/dev/null | grep -c '^Test' || echo "0")
fi

if [ "$DISCOVERED" -eq 0 ]; then
    echo "❌ 0 条测试被发现——test discovery 可能故障（PASS(0) 真空通过不可接受）"
    FAIL=1
else
    echo "✅ ${DISCOVERED} 条测试被发现"
fi

# ── 结果 ──
echo ""
echo "============================================"
if [ $FAIL -eq 0 ]; then
    echo "✅ test-gate C0.1-C0.5 全部通过"
else
    echo "❌ test-gate 未通过，修复后再提交"
    exit 1
fi
