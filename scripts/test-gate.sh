#!/bin/bash
# test-gate.sh — 测试门禁秒检（跨项目通用）
# 用途：RED commit 前自动执行 C0.1-C0.8，不通过则阻断
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
    --exclude='*.bak' --exclude='*.bak2' --exclude='*.bak-*' --exclude='*.skip' 2>/dev/null | grep -v "expect(typeof" || true)
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
    --exclude='*.bak' --exclude='*.bak2' --exclude='*.bak-*' --exclude='*.skip' \
    --exclude='playwright.config.*' --exclude='vitest.config.*' --exclude='jest.config.*' \
    --exclude='cypress.config.*' --exclude='webpack*.js' --exclude='vite.config.*' 2>/dev/null || true)
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
    --exclude='*.bak' --exclude='*.bak2' --exclude='*.bak-*' --exclude='*.skip' 2>/dev/null | grep -v "test\.setTimeout" || true)
if [ -n "$HITS" ]; then
    COUNT=$(echo "$HITS" | wc -l)
    echo "⚠️  发现 ${COUNT} 处固定延时（已排除 test.setTimeout 测试超时配置），需人工确认必要"
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


# ── C0.7: if-count/length === 0 → early return（硬阻断）──
echo ""
echo "--- C0.7: if-count/length === 0 → return ---"
C07_HITS=""
for f in $(find "$TESTS_DIR" \( -name "*.spec.*" -o -name "*.test.*" \)     -not -path "*/characterization/*"     -not -name "*.bak" -not -name "*.bak2" -not -name "*.bak-*" -not -name "*.skip" 2>/dev/null); do
    [ -f "$f" ] || continue
    # 单行: if (...count() === 0) { return; }
    single=$(grep -n "if\s*.*\.count()\s*===\s*0\b.*return\b\|if\s*.*\.length\s*===\s*0\b.*return\b" "$f" 2>/dev/null || true)
    [ -n "$single" ] && while IFS= read -r line; do
        C07_HITS="${C07_HITS}${f}:${line}\n"
    done <<< "$single"
    # 多行: if 行含 count/length === 0 → 下行含 return
    multi=$(grep -n "\.count()\s*===\s*0\b\|\.length\s*===\s*0\b" "$f" 2>/dev/null || true)
    [ -n "$multi" ] && while IFS=: read -r ln rest; do
        [ -n "$ln" ] || continue
        next=$((ln + 1))
        next_line=$(sed -n "${next}p" "$f" 2>/dev/null || true)
        if echo "$next_line" | grep -q "^\s*return\b"; then
            C07_HITS="${C07_HITS}${f}:${ln}: if-count-return (multi-line)\n"
        fi
    done <<< "$multi"
done
if [ -n "$C07_HITS" ]; then
    COUNT=$(echo -e "$C07_HITS" | grep -c ":" || echo "0")
    echo "❌ 发现 ${COUNT} 处 if-count/length === 0 → return（Skip Test 硬阻断）"
    echo -e "$C07_HITS" | head -10
    [ "$COUNT" -gt 10 ] && echo "  ... 共 ${COUNT} 处"
    FAIL=1
else
    echo "✅ 零命中"
fi
# ── C0.8: 断言强度分布（警告级）──
echo ""
echo "--- C0.8: 断言强度分布 ---"
# 统计 expect 总数（排除注释行）
TOTAL_EXPECT=$(grep -rn "expect(" "$TESTS_DIR" \
    --exclude-dir=characterization \
    --exclude='*.bak' --exclude='*.bak2' --exclude='*.bak-*' --exclude='*.skip' 2>/dev/null | grep -v '^\s*\/\/\|^\s*\*\|^\s*#' | wc -l || echo "0")
# 统计弱断言：toBeVisible / toBeDefined / toBeTruthy / toBeNull / toBeFalsy
WEAK_ASSERT=$(grep -rnE "expect\(.*\)\.toBeVisible\(\)|expect\(.*\)\.toBeDefined\(\)|expect\(.*\)\.toBeTruthy\(\)|expect\(.*\)\.toBeNull\(\)|expect\(.*\)\.toBeFalsy\(\)" "$TESTS_DIR" \
    --exclude-dir=characterization \
    --exclude='*.bak' --exclude='*.bak2' --exclude='*.bak-*' --exclude='*.skip' 2>/dev/null | grep -v '^\s*\/\/\|^\s*\*\|^\s*#' | wc -l || echo "0")
if [ "$TOTAL_EXPECT" -gt 0 ]; then
    WEAK_PCT=$((WEAK_ASSERT * 100 / TOTAL_EXPECT))
    echo "  总断言: ${TOTAL_EXPECT}, 弱断言: ${WEAK_ASSERT} (${WEAK_PCT}%)"
    echo "  弱断言类型: toBeVisible/toBeDefined/toBeTruthy/toBeNull/toBeFalsy"
    if [ "$WEAK_PCT" -gt 50 ]; then
        echo "⚠️  弱断言占比 ${WEAK_PCT}% > 50%——测试可能不验证操作结果"
        echo "  提示: click/fill/submit 之后必须有强断言（精确值/集合/数量），不能只有'元素可见'"
        echo "  参考: .claude/gate-checklists/test-checklist.md §C0.8 + ASI 五级量表"
    else
        echo "✅ 弱断言占比 ${WEAK_PCT}%，在可接受范围"
    fi
else
    echo "✅ 未检测到 expect() 断言（非 JS/TS 项目，跳过）"
fi

# C0.8 单文件级：检测"有操作但只有弱断言"的文件（防蒙面效应）
echo ""
echo "--- C0.8 单文件级：操作-断言匹配 ---"
C08_PERFILE_HITS=""
for f in $(find "$TESTS_DIR" \( -name "*.spec.*" -o -name "*.test.*" \) \
    -not -path "*/characterization/*" \
    -not -name "*.bak" -not -name "*.bak2" -not -name "*.bak-*" -not -name "*.skip" 2>/dev/null); do
    [ -f "$f" ] || continue
    # 有 UI 操作？（直接 grep 文件，注释行误判风险低）
    HAS_ACTION=$(grep -cE '\.(click|fill|type|press|submit|selectOption|check|dblclick|hover|focus)\(' "$f" 2>/dev/null) || HAS_ACTION=0
    [ "$HAS_ACTION" -gt 0 ] 2>/dev/null || continue
    # 有强断言？（精确值/集合/数量/包含/匹配）
    HAS_STRONG=$(grep -cE '\.(toBe\(|toEqual\(|toStrictEqual\(|toContain\(|toHaveLength\(|toMatch\(|toBeGreaterThan|toBeGreaterThanOrEqual|toBeLessThan|toBeLessThanOrEqual|toBeCloseTo)' "$f" 2>/dev/null) || HAS_STRONG=0
    [ "$HAS_STRONG" -gt 0 ] 2>/dev/null && continue
    # 有弱断言？
    HAS_WEAK=$(grep -cE '\.(toBeVisible|toBeDefined|toBeTruthy|toBeNull|toBeFalsy)\(\)' "$f" 2>/dev/null) || HAS_WEAK=0
    [ "$HAS_WEAK" -gt 0 ] 2>/dev/null || continue
    # 有操作 + 零强断言 + 有弱断言 = 操作后不验证结果
    C08_PERFILE_HITS="${C08_PERFILE_HITS}${f}: ${HAS_ACTION} 操作, 0 强断言, ${HAS_WEAK} 弱断言\n"
done
if [ -n "$C08_PERFILE_HITS" ]; then
    COUNT=$(echo -e "$C08_PERFILE_HITS" | grep -c ":" || echo "0")
    echo "⚠️  发现 ${COUNT} 个文件有操作但零强断言（操作成败不区分）:"
    echo -e "$C08_PERFILE_HITS" | head -10 | sed 's/^/    /'
    [ "$COUNT" -gt 10 ] && echo "    ... 共 ${COUNT} 个文件"
    echo "  提示: click/fill/submit 之后至少加 1 条强断言（toBe/toEqual/toContain），不能只有 toBeVisible"
else
    echo "✅ 所有含操作的文件均有强断言"
fi

# C0.8 操作行级：混合文件中操作后仅有弱断言（单测试蒙面效应）
echo ""
echo "--- C0.8 操作行级：操作后断言检查 ---"
C08_LINE_HITS=""
for f in $(find "$TESTS_DIR" \( -name "*.spec.*" -o -name "*.test.*" \) \
    -not -path "*/characterization/*" \
    -not -name "*.bak" -not -name "*.bak2" -not -name "*.bak-*" -not -name "*.skip" 2>/dev/null); do
    [ -f "$f" ] || continue
    HAS_ACTION=$(grep -cE '\.(click|fill|submit|press|type|selectOption|check|dblclick)\(' "$f" 2>/dev/null) || HAS_ACTION=0
    [ "$HAS_ACTION" -gt 0 ] 2>/dev/null || continue
    HAS_STRONG=$(grep -cE '\.(toBe\(|toEqual\(|toStrictEqual\(|toContain\(|toHaveLength\(|toMatch\(|toBeGreaterThan|toBeGreaterThanOrEqual|toBeLessThan|toBeLessThanOrEqual|toBeCloseTo)' "$f" 2>/dev/null) || HAS_STRONG=0
    # 只扫描混合文件（有操作+有强断言，但可能存在个别测试只有弱断言）
    [ "$HAS_STRONG" -gt 0 ] 2>/dev/null || continue
    ACTION_LINES=$(grep -nE '\.(click|fill|submit|press|type|selectOption|check|dblclick)\(' "$f" 2>/dev/null | cut -d: -f1 || true)
    [ -n "$ACTION_LINES" ] || continue
    for ln in $ACTION_LINES; do
        [ -n "$ln" ] || continue
        BLOCK=$(sed -n "${ln},$((ln+5))p" "$f" 2>/dev/null || true)
        HAS_FW=$(echo "$BLOCK" | grep -cE 'expect\(.*\)\.(toBeVisible|toBeDefined|toBeTruthy|toBeNull|toBeFalsy)\(\)' 2>/dev/null) || HAS_FW=0
        HAS_FS=$(echo "$BLOCK" | grep -cE 'expect\(.*\)\.(toBe\(|toEqual\(|toStrictEqual\(|toContain\(|toHaveLength\(|toMatch\(|toBeGreaterThan|toBeGreaterThanOrEqual|toBeLessThan|toBeLessThanOrEqual|toBeCloseTo)' 2>/dev/null) || HAS_FS=0
        if [ "$HAS_FW" -gt 0 ] && [ "$HAS_FS" -eq 0 ]; then
            C08_LINE_HITS="${C08_LINE_HITS}${f}:${ln}: 操作后仅弱断言（5行内无强断言）\n"
            break  # 每文件报一次即可
        fi
    done
done
if [ -n "$C08_LINE_HITS" ]; then
    COUNT=$(echo -e "$C08_LINE_HITS" | grep -c ":" || echo "0")
    echo "⚠️  发现 ${COUNT} 个文件存在操作后仅有弱断言的行（单测试蒙面）:"
    echo -e "$C08_LINE_HITS" | head -10 | sed 's/^/    /'
    [ "$COUNT" -gt 10 ] && echo "    ... 共 ${COUNT} 个文件"
    echo "  提示: 该操作（click/fill/submit）后应补充强断言验证操作结果"
else
    echo "✅ 所有操作行后均有强断言跟随"
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
    echo "✅ test-gate C0.1-C0.8 全部通过"
else
    echo "❌ test-gate 未通过（C0.1-C0.8），修复后再提交"
    exit 1
fi
