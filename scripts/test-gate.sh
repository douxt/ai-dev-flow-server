#!/bin/bash
# test-gate.sh — 测试门禁秒检（跨项目通用）
# 用途：RED commit 前自动执行 C0.1-C0.9，不通过则阻断
# 部署：ai-dev-flow-server --update 自动部署到 .devflow/scripts/
# 扩展：项目可在 scripts/test-gate.sh 中追加 C6+/G2/G4 等项目特化检查
#
# 参考：.claude/gate-checklists/test-checklist.md §C0

set -euo pipefail
FAIL=0

# ── 检测测试目录（monorepo + Go 同包测试支持）──
TESTS_DIR=""
INCLUDE_FLAG=""   # Go/FE 无独立测试目录时限定扫描文件类型，防源码误报
for d in tests test __tests__ spec e2e frontend/tests backend/tests; do
    [ -d "$d" ] && { TESTS_DIR="$d"; break; }
done
if [ -z "$TESTS_DIR" ]; then
    # Go 项目：测试与源码同包（backend/**/*_test.go）
    GO_TEST=$(find . -maxdepth 4 -name "*_test.go" -not -path "*/node_modules/*" 2>/dev/null | head -1 || true)
    if [ -n "$GO_TEST" ]; then
        TESTS_DIR="."
        INCLUDE_FLAG="--include='*_test.go'"
    else
        # 前端项目：*.test.ts / *.spec.ts（排除 node_modules）
        FE_TEST=$(find . -maxdepth 4 \( -name "*.test.ts" -o -name "*.spec.ts" \) -not -path "*/node_modules/*" 2>/dev/null | head -1 || true)
        if [ -n "$FE_TEST" ]; then
            TESTS_DIR="."
            INCLUDE_FLAG="--include='*.test.ts' --include='*.spec.ts'"
        fi
    fi
fi
if [ -z "$TESTS_DIR" ]; then
    echo "[test-gate] ⚠️ 未找到测试目录，跳过"
    exit 0
fi

echo "=== test-gate: C0 提交前秒检 ==="
echo "  测试目录: $TESTS_DIR"

# ── C0.1: 无调试残留 ──
echo ""
echo "--- C0.1: 无调试残留 ---"
HITS=$(grep -rn "test\.only\|describe\.only\|it\.only\|page\.pause" "$TESTS_DIR" $INCLUDE_FLAG \
    --exclude-dir=characterization --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=vendor \
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
HITS=$(grep -rn "toBeGreaterThanOrEqual(0)\|typeof.*toBe('number')\|\.toBeTruthy()\|\.toBeDefined()" "$TESTS_DIR" $INCLUDE_FLAG \
    --exclude-dir=characterization --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=vendor \
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
HITS=$(grep -rn "localhost:[0-9]\{4\}" "$TESTS_DIR" $INCLUDE_FLAG \
    --exclude-dir=characterization --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=vendor \
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
HITS=$(grep -rn "waitForTimeout\|page\.waitForTimeout\|setTimeout.*[0-9]\{4,\}" "$TESTS_DIR" $INCLUDE_FLAG \
    --exclude-dir=characterization --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=vendor \
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
HITS=$(grep -rn "try\s*{" "$TESTS_DIR" $INCLUDE_FLAG \
    --exclude-dir=characterization --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=vendor \
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
for f in $(find "$TESTS_DIR" \( -name "*.spec.*" -o -name "*.test.*" \)     -not -path "*/characterization/*" -not -path "*/node_modules/*"     -not -name "*.bak" -not -name "*.bak2" -not -name "*.bak-*" -not -name "*.skip" 2>/dev/null); do
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
    COUNT=$(echo -e "$C07_HITS" | grep -c ":" || true)
    echo "❌ 发现 ${COUNT} 处 if-count/length === 0 → return（Skip Test 硬阻断）"
    echo -e "$C07_HITS" | head -10
    [ "$COUNT" -gt 10 ] && echo "  ... 共 ${COUNT} 处"
    FAIL=1
else
    echo "✅ 零命中"
fi
# ── C0.8: 断言强度分布（硬阻断）──
echo ""
echo "--- C0.8: 断言强度分布 ---"
# 统计 expect 总数（排除注释行）
TOTAL_EXPECT=$(grep -rn "expect(" "$TESTS_DIR" $INCLUDE_FLAG \
    --exclude-dir=characterization --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=vendor \
    --exclude='*.bak' --exclude='*.bak2' --exclude='*.bak-*' --exclude='*.skip' 2>/dev/null | grep -v '^\s*\/\/\|^\s*\*\|^\s*#' | wc -l || true)
# 统计弱断言：toBeVisible / toBeDefined / toBeTruthy / toBeNull / toBeFalsy
WEAK_ASSERT=$(grep -rnE "expect\([^)]*\)\.toBeVisible\(|expect\([^)]*\)\.toBeDefined\(|expect\([^)]*\)\.toBeTruthy\(|expect\([^)]*\)\.toBeNull\(|expect\([^)]*\)\.toBeFalsy\(" "$TESTS_DIR" $INCLUDE_FLAG \
    --exclude-dir=characterization --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=vendor \
    --exclude='*.bak' --exclude='*.bak2' --exclude='*.bak-*' --exclude='*.skip' 2>/dev/null | grep -v '^\s*\/\/\|^\s*\*\|^\s*#' | wc -l || true)
if [ "$TOTAL_EXPECT" -gt 0 ]; then
    WEAK_PCT=$((WEAK_ASSERT * 100 / TOTAL_EXPECT))
    echo "  总断言: ${TOTAL_EXPECT}, 弱断言: ${WEAK_ASSERT} (${WEAK_PCT}%)"
    echo "  弱断言类型: toBeVisible/toBeDefined/toBeTruthy/toBeNull/toBeFalsy"
    if [ "$WEAK_PCT" -gt 50 ]; then
        echo "⚠️  弱断言占比 ${WEAK_PCT}% > 50%——测试可能不验证操作结果"
        echo "  提示: click/fill/submit 之后必须有强断言（精确值/集合/数量），不能只有'元素可见'"
        echo "  参考: .claude/gate-checklists/test-checklist.md §C0.8 + .devflow/knowledge/12-断言强度指数.md（ASI 五级量表）"
        FAIL=1
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
    -not -path "*/characterization/*" -not -path "*/node_modules/*" \
    -not -name "*.bak" -not -name "*.bak2" -not -name "*.bak-*" -not -name "*.skip" 2>/dev/null); do
    [ -f "$f" ] || continue
    # 有 UI 操作？（直接 grep 文件，注释行误判风险低）
    HAS_ACTION=$(grep -cE '\.(click|fill|type|press|submit|selectOption|check|dblclick|hover|focus)\(' "$f" 2>/dev/null) || HAS_ACTION=0
    [ "$HAS_ACTION" -gt 0 ] 2>/dev/null || continue
    # 有强断言？（精确值/集合/数量/包含/匹配）
    HAS_STRONG=$(grep -cE '\.(toBe\(|toEqual\(|toStrictEqual\(|toContain\(|toHaveLength\(|toMatch\(|toBeGreaterThan|toBeGreaterThanOrEqual|toBeLessThan|toBeLessThanOrEqual|toBeCloseTo|toBeChecked\(|toHaveCount\(|toHaveClass\(|toHaveText\(|toContainText\(|toHaveValue\(|toHaveAttribute\()' "$f" 2>/dev/null) || HAS_STRONG=0
    [ "$HAS_STRONG" -gt 0 ] 2>/dev/null && continue
    # 有弱断言？
    HAS_WEAK=$(grep -cE '\.(toBeVisible|toBeDefined|toBeTruthy|toBeNull|toBeFalsy)\(' "$f" 2>/dev/null) || HAS_WEAK=0
    [ "$HAS_WEAK" -gt 0 ] 2>/dev/null || continue
    # 有操作 + 零强断言 + 有弱断言 = 操作后不验证结果
    C08_PERFILE_HITS="${C08_PERFILE_HITS}${f}: ${HAS_ACTION} 操作, 0 强断言, ${HAS_WEAK} 弱断言\n"
done
if [ -n "$C08_PERFILE_HITS" ]; then
    COUNT=$(echo -e "$C08_PERFILE_HITS" | grep -c ":" || true)
    echo "⚠️  发现 ${COUNT} 个文件有操作但零强断言（操作成败不区分）:"
    echo -e "$C08_PERFILE_HITS" | head -10 | sed 's/^/    /'
    [ "$COUNT" -gt 10 ] && echo "    ... 共 ${COUNT} 个文件"
    echo "  提示: click/fill/submit 之后至少加 1 条强断言（toBe/toEqual/toContain），不能只有 toBeVisible"
    FAIL=1
else
    echo "✅ 所有含操作的文件均有强断言"
fi

# C0.8 操作行级：混合文件中操作后仅有弱断言（单测试蒙面效应）
echo ""
echo "--- C0.8 操作行级：操作后断言检查 ---"
C08_LINE_HITS=""
for f in $(find "$TESTS_DIR" \( -name "*.spec.*" -o -name "*.test.*" \) \
    -not -path "*/characterization/*" -not -path "*/node_modules/*" \
    -not -name "*.bak" -not -name "*.bak2" -not -name "*.bak-*" -not -name "*.skip" 2>/dev/null); do
    [ -f "$f" ] || continue
    HAS_ACTION=$(grep -cE '\.(click|fill|submit|press|type|selectOption|check|dblclick)\(' "$f" 2>/dev/null) || HAS_ACTION=0
    [ "$HAS_ACTION" -gt 0 ] 2>/dev/null || continue
    HAS_STRONG=$(grep -cE '\.(toBe\(|toEqual\(|toStrictEqual\(|toContain\(|toHaveLength\(|toMatch\(|toBeGreaterThan|toBeGreaterThanOrEqual|toBeLessThan|toBeLessThanOrEqual|toBeCloseTo|toBeChecked\(|toHaveCount\(|toHaveClass\(|toHaveText\(|toContainText\(|toHaveValue\(|toHaveAttribute\()' "$f" 2>/dev/null) || HAS_STRONG=0
    # 只扫描混合文件（有操作+有强断言，但可能存在个别测试只有弱断言）
    [ "$HAS_STRONG" -gt 0 ] 2>/dev/null || continue
    ACTION_LINES=$(grep -nE '\.(click|fill|submit|press|type|selectOption|check|dblclick)\(' "$f" 2>/dev/null | cut -d: -f1 || true)
    [ -n "$ACTION_LINES" ] || continue
    for ln in $ACTION_LINES; do
        [ -n "$ln" ] || continue
        BLOCK=$(sed -n "${ln},$((ln+5))p" "$f" 2>/dev/null || true)
        HAS_FW=$(echo "$BLOCK" | grep -cE 'expect\([^)]*\)\.(toBeVisible|toBeDefined|toBeTruthy|toBeNull|toBeFalsy)\(' 2>/dev/null) || HAS_FW=0
        HAS_FS=$(echo "$BLOCK" | grep -cE 'expect\([^)]*\)\.(toBe\(|toEqual\(|toStrictEqual\(|toContain\(|toHaveLength\(|toMatch\(|toBeGreaterThan|toBeGreaterThanOrEqual|toBeLessThan|toBeLessThanOrEqual|toBeCloseTo|toBeChecked\(|toHaveCount\(|toHaveClass\(|toHaveText\(|toContainText\(|toHaveValue\(|toHaveAttribute\()' 2>/dev/null) || HAS_FS=0
        if [ "$HAS_FW" -gt 0 ] && [ "$HAS_FS" -eq 0 ]; then
            C08_LINE_HITS="${C08_LINE_HITS}${f}:${ln}: 操作后仅弱断言（5行内无强断言）\n"
            break  # 每文件报一次即可
        fi
    done
done
if [ -n "$C08_LINE_HITS" ]; then
    COUNT=$(echo -e "$C08_LINE_HITS" | grep -c ":" || true)
    echo "❌ 发现 ${COUNT} 个文件存在操作后仅有弱断言的行（单测试蒙面）:"
    echo -e "$C08_LINE_HITS" | head -10 | sed 's/^/    /'
    [ "$COUNT" -gt 10 ] && echo "    ... 共 ${COUNT} 个文件"
    echo "  提示: 该操作（click/fill/submit）后应补充强断言验证操作结果"
    FAIL=1
else
    echo "✅ 所有操作行后均有强断言跟随"
fi

# ── C0.9: 代码覆盖率秒检（警告级）──
echo ""
echo "--- C0.9: 代码覆盖率 ---"
COV_THRESHOLD=50  # 初始阈值，逐步提升
COV_CONFIGURED=false
COV_SUMMARY=""

# 检测覆盖率配置
for cfg in "vitest.config.js" "vitest.config.ts" "jest.config.js" "jest.config.ts"; do
    if [ -f "$cfg" ]; then
        if grep -q 'coverage\|collectCoverage' "$cfg" 2>/dev/null; then
            COV_CONFIGURED=true
            break
        fi
    fi
done

# 检测覆盖率报告
if [ -f "coverage/coverage-summary.json" ]; then
    COV_SUMMARY="coverage/coverage-summary.json"
elif [ -f "coverage/coverage-final.json" ]; then
    COV_SUMMARY="coverage/coverage-final.json"
elif [ -f "coverage/lcov.info" ]; then
    COV_SUMMARY="coverage/lcov.info"
fi

if [ -n "$COV_SUMMARY" ]; then
    # 解析 JSON 覆盖率摘要
    if command -v jq >/dev/null 2>&1 && [ "$COV_SUMMARY" = "coverage/coverage-summary.json" ]; then
        LINES_PCT=$(jq -r '.total.lines.pct // "N/A"' "$COV_SUMMARY" 2>/dev/null || echo "N/A")
        BRANCHES_PCT=$(jq -r '.total.branches.pct // "N/A"' "$COV_SUMMARY" 2>/dev/null || echo "N/A")
        FUNCTIONS_PCT=$(jq -r '.total.functions.pct // "N/A"' "$COV_SUMMARY" 2>/dev/null || echo "N/A")
        echo "  行: ${LINES_PCT}%  分支: ${BRANCHES_PCT}%  函数: ${FUNCTIONS_PCT}%"
        # 检查阈值（仅检查数字值）
        BELOW=""
        [ "$LINES_PCT" != "N/A" ] && [ "${LINES_PCT%.*}" -lt "$COV_THRESHOLD" ] 2>/dev/null && BELOW="$BELOW 行"
        [ "$BRANCHES_PCT" != "N/A" ] && [ "${BRANCHES_PCT%.*}" -lt "$COV_THRESHOLD" ] 2>/dev/null && BELOW="$BELOW 分支"
        [ "$FUNCTIONS_PCT" != "N/A" ] && [ "${FUNCTIONS_PCT%.*}" -lt "$COV_THRESHOLD" ] 2>/dev/null && BELOW="$BELOW 函数"
        if [ -n "$BELOW" ]; then
            echo "⚠️  覆盖率低于阈值 ${COV_THRESHOLD}%:${BELOW}"
            echo "  提示: 为新代码补充测试，阈值从 50% 起步逐步提升"
        else
            echo "✅ 覆盖率 ≥ ${COV_THRESHOLD}%"
        fi
    elif [ "$COV_SUMMARY" = "coverage/lcov.info" ]; then
        # lcov 摘要（无 jq fallback）
        TOTAL_LINES=$(grep -c '^DA:' "$COV_SUMMARY" 2>/dev/null || true)
        COVERED_LINES=$(grep '^DA:' "$COV_SUMMARY" 2>/dev/null | grep -c ',1$\|,2$\|,3$\|,4$\|,5$\|,6$\|,7$\|,8$\|,9$' || true)
        echo "  lcov: ${COVERED_LINES}/${TOTAL_LINES} 行覆盖"
        if [ "$TOTAL_LINES" -gt 0 ]; then
            LCOV_PCT=$((COVERED_LINES * 100 / TOTAL_LINES))
            if [ "$LCOV_PCT" -lt "$COV_THRESHOLD" ]; then
                echo "⚠️  覆盖率 ${LCOV_PCT}% < ${COV_THRESHOLD}%"
            else
                echo "✅ 覆盖率 ${LCOV_PCT}% ≥ ${COV_THRESHOLD}%"
            fi
        fi
    fi
elif $COV_CONFIGURED; then
    echo "⚠️  覆盖率已配置但无报告——运行测试时加 --coverage 生成报告"
    echo "  提示: vitest run --coverage / jest --coverage / npx playwright test --coverage"
else
    echo "ℹ️  覆盖率未配置——建议为关键模块启用 coverage reporter"
    echo "  参考: https://vitest.dev/guide/coverage.html"
fi

# ── C0.5: 测试实际执行 ──
echo ""
echo "--- C0.5: 测试实际执行 ---"
DISCOVERED=0

# 模块目录定位（monorepo：go.mod/package.json 可能在子目录）
MODULE_DIRS=""
if [ -f "go.mod" ] || [ -f "package.json" ]; then
    MODULE_DIRS="."
else
    for d in backend server api frontend web client; do
        if [ -f "$d/go.mod" ] || [ -f "$d/package.json" ]; then
            MODULE_DIRS="$MODULE_DIRS $d"
        fi
    done
fi
[ -z "$MODULE_DIRS" ] && MODULE_DIRS="."

for MOD_DIR in $MODULE_DIRS; do
    # 搜索 playwright config（模块内 + 常见子目录）
    PW_CONFIG=""
    for loc in "$MOD_DIR/playwright.config.js" "$MOD_DIR/playwright.config.ts" \
               "$MOD_DIR/tests/playwright.config.js" "$MOD_DIR/tests/playwright.config.ts" \
               "$MOD_DIR/e2e/playwright.config.js" "$MOD_DIR/e2e/playwright.config.ts"; do
        [ -f "$loc" ] && { PW_CONFIG="$loc"; break; }
    done

    if [ -n "$PW_CONFIG" ]; then
        # 用 Total: N 解析测试数（方案 A，最可靠——suites 数 ≠ 测试数）
        PW_LIST=$(npx playwright test --config="$PW_CONFIG" --list 2>&1 || true)
        N=$(echo "$PW_LIST" | grep -oP 'Total:\s+\K\d+' || true)
        # fallback: 直接 node 调 playwright 二进制（绕过可能的 npx wrapper/RTK）
        if [ "$N" -eq 0 ] && [ -f "$MOD_DIR/node_modules/.bin/playwright" ]; then
            PW_LIST2=$(node "$MOD_DIR/node_modules/.bin/playwright" test --config="$PW_CONFIG" --list 2>&1 || true)
            N=$(echo "$PW_LIST2" | grep -oP 'Total:\s+\K\d+' || true)
        fi
        DISCOVERED=$((DISCOVERED + N))
    elif [ -f "$MOD_DIR/jest.config.js" ] || [ -f "$MOD_DIR/jest.config.ts" ] || grep -q '"jest"' "$MOD_DIR/package.json" 2>/dev/null; then
        N=$(cd "$MOD_DIR" && npx jest --listTests 2>/dev/null | wc -l || true)
        DISCOVERED=$((DISCOVERED + N))
    elif [ -f "$MOD_DIR/vitest.config.js" ] || [ -f "$MOD_DIR/vitest.config.ts" ]; then
        N=$(npx --prefix "$MOD_DIR" vitest list 2>/dev/null | grep -cE '\.(test|spec)\.' || true)
        DISCOVERED=$((DISCOVERED + N))
    elif [ -f "$MOD_DIR/phpunit.xml" ] || [ -f "$MOD_DIR/phpunit.xml.dist" ]; then
        N=$(php "$MOD_DIR/vendor/bin/phpunit" --list-tests 2>/dev/null | grep -c '^\s*-' || true)
        DISCOVERED=$((DISCOVERED + N))
    elif command -v pytest &>/dev/null; then
        N=$(cd "$MOD_DIR" && python3 -m pytest --collect-only -q 2>/dev/null | grep -c '::' || true)
        DISCOVERED=$((DISCOVERED + N))
    elif [ -f "$MOD_DIR/go.mod" ]; then
        N=$(go -C "$MOD_DIR" test ./... -list '.*' 2>/dev/null | grep -c '^Test' || true)
        DISCOVERED=$((DISCOVERED + N))
    fi
done

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
    echo "✅ test-gate C0.1-C0.9 全部通过"
else
    echo "❌ test-gate 未通过（C0.1-C0.9），修复后再提交"
    exit 1
fi
