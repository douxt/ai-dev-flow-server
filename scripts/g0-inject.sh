#!/bin/bash
# g0-inject.sh — G0 故障注入自动化（跨项目通用）
# 用途：/implement GREEN 之后，GREEN commit 之前，自动验证"测试真能拦住 Bug 吗"
# 部署：ai-dev-flow-server --update 自动部署到 .devflow/scripts/
#
# 用法：
#   g0-inject.sh <source-file> [test-name-pattern]
#     source-file: 被测源文件（相对路径，如 src/api/export.ts）
#     test-name-pattern: 测试名称关键字（可选，如 "export"）
#
# 流程：
#   1. 备份源文件 → 自动注入故障（修改返回值/破坏关键逻辑）
#   2. 运行测试 → 必须 ≥1 失败（证明测试有保护力）
#   3. 恢复源文件 → 运行测试 → 必须全部通过
#
# 退出码：
#   0 - G0 通过
#   1 - G0 失败（故障注入后测试仍全绿 = 断言不够强）
#   2 - 无法自动注入 / 环境问题
#
# 参考：.claude/gate-checklists/test-checklist.md §G0

set -euo pipefail

SOURCE_FILE="${1:-}"
TEST_FILTER="${2:-}"
G0_BAK_SUFFIX=".g0bak"

# ── 参数校验 ──
if [ -z "$SOURCE_FILE" ]; then
    echo "用法: g0-inject.sh <source-file> [test-name-pattern]"
    echo ""
    echo "示例:"
    echo "  g0-inject.sh src/api/export.ts"
    echo "  g0-inject.sh src/services/paint.ts paint-status"
    exit 2
fi

if [ ! -f "$SOURCE_FILE" ]; then
    echo "❌ 源文件不存在: $SOURCE_FILE"
    exit 2
fi

echo "=== g0-inject: G0 故障注入验证 ==="
echo "  源文件: $SOURCE_FILE"
[ -n "$TEST_FILTER" ] && echo "  测试过滤: $TEST_FILTER"

# ── 检测测试运行器 + 定位 config 路径 ──
PW_CONFIG=""
# 先定位 playwright config（必须在函数外，避免 subshell 变量丢失）
for loc in "playwright.config.js" "playwright.config.ts" \
           "tests/playwright.config.js" "tests/playwright.config.ts" \
           "e2e/playwright.config.js" "e2e/playwright.config.ts"; do
    [ -f "$loc" ] && { PW_CONFIG="$loc"; break; }
done

detect_test_runner() {
    [ -n "$PW_CONFIG" ] && { echo "playwright"; return; }
    if [ -f "jest.config.js" ] || [ -f "jest.config.ts" ] || grep -q '"jest"' package.json 2>/dev/null; then
        echo "jest"
    elif [ -f "vitest.config.js" ] || [ -f "vitest.config.ts" ]; then
        echo "vitest"
    elif [ -f "phpunit.xml" ] || [ -f "phpunit.xml.dist" ]; then
        echo "phpunit"
    elif command -v pytest &>/dev/null; then
        echo "pytest"
    elif command -v go &>/dev/null; then
        echo "go"
    else
        echo "unknown"
    fi
}

RUNNER=$(detect_test_runner)
echo "  测试运行器: $RUNNER"
[ -n "$PW_CONFIG" ] && echo "  Playwright config: $PW_CONFIG"

# ── 构建测试命令 ──
build_test_cmd() {
    local expect_fail="${1:-false}"  # true = 预期失败，用于额外容错
    case "$RUNNER" in
        playwright)
            if [ -n "$TEST_FILTER" ]; then
                echo "npx playwright test --config=\"$PW_CONFIG\" --grep \"$TEST_FILTER\""
            else
                echo "npx playwright test --config=\"$PW_CONFIG\""
            fi
            ;;
        jest)
            if [ -n "$TEST_FILTER" ]; then
                echo "npx jest --testNamePattern \"$TEST_FILTER\""
            else
                echo "npx jest"
            fi
            ;;
        vitest)
            if [ -n "$TEST_FILTER" ]; then
                echo "npx vitest run --testNamePattern \"$TEST_FILTER\""
            else
                echo "npx vitest run"
            fi
            ;;
        phpunit)
            if [ -n "$TEST_FILTER" ]; then
                echo "php vendor/bin/phpunit --filter \"$TEST_FILTER\""
            else
                echo "php vendor/bin/phpunit"
            fi
            ;;
        pytest)
            if [ -n "$TEST_FILTER" ]; then
                echo "python3 -m pytest -k \"$TEST_FILTER\""
            else
                echo "python3 -m pytest"
            fi
            ;;
        go)
            if [ -n "$TEST_FILTER" ]; then
                echo "go test ./... -run \"$TEST_FILTER\""
            else
                echo "go test ./..."
            fi
            ;;
        *)
            echo ""
            ;;
    esac
}

TEST_CMD=$(build_test_cmd)
if [ -z "$TEST_CMD" ]; then
    echo "❌ 无法检测测试运行器，请手动运行测试"
    exit 2
fi
echo "  测试命令: $TEST_CMD"

# ── 自动故障注入策略（按优先级尝试）──
inject_fault() {
    local file="$1"

    # 策略 1: 修改成功返回码 (return { code: 0 → code: 999)
    if grep -qE 'return\s+\{.*code\s*:\s*0' "$file" 2>/dev/null; then
        sed -i -E 's/(return\s+\{.*code\s*:\s*)0/\1999/' "$file"
        echo "策略1: 成功返回码 code:0 → code:999"
        return 0
    fi

    # 策略 2: 修改 API 返回的成功状态
    if grep -qE 'success\s*:\s*true' "$file" 2>/dev/null; then
        sed -i -E 's/success\s*:\s*true/success: false/' "$file"
        echo "策略2: success:true → success:false"
        return 0
    fi

    # 策略 3: 修改 HTTP 状态码
    if grep -qE 'status\s*:\s*200' "$file" 2>/dev/null; then
        sed -i -E 's/status\s*:\s*200/status: 500/' "$file"
        echo "策略3: status:200 → status:500"
        return 0
    fi

    # 策略 4: 删除最后一条 return 语句前一行（破坏数据构建）
    # 跳过 JSX/TSX 组件——return 前的行通常不是数据逻辑，注释掉不影响功能
    if echo "$SOURCE_FILE" | grep -qE '\.(jsx|tsx)$' || grep -qE '<[A-Z]\w+|<div|<span|className=' "$file" 2>/dev/null; then
        echo "  策略4: 跳过（JSX组件，注释return前行无效）"
    else
        local last_return=$(grep -n 'return' "$file" | tail -1 | cut -d: -f1)
        if [ -n "$last_return" ] && [ "$last_return" -gt 1 ]; then
            local prev=$((last_return - 1))
            sed -i "${prev}s/^/\/\/ G0-FAULT-INJECTED /" "$file"
            echo "策略4: 注释掉 return 前一行 (L${prev})"
            return 0
        fi
    fi

    # 策略 5: 在第一个非 render 的导出/事件处理函数体首行插入 early return
    local first_func=$(grep -n 'export\s\+\(async\s\+\)\?function\|handle[A-Z]\|const\s\+\w\+\s*=\s*\(async\s*\)\?(' "$file" \
        | grep -v 'render\s*(' | head -1 | cut -d: -f1)
    if [ -n "$first_func" ]; then
        local inject=$((first_func + 1))
        sed -i "${inject}a\  return { code: -1, message: 'G0-FAULT-INJECTED' };" "$file"
        echo "策略5: 函数体首行注入 early return (L${inject})"
        return 0
    fi

    return 1
}

# ── 运行测试并返回通过/失败 ──
run_test() {
    local output
    set +e
    output=$(eval "$TEST_CMD" 2>&1)
    local rc=$?
    set -e
    echo "$output"
    return $rc
}

# ── Step 1: 运行基线测试（确认初始状态 GREEN）──
echo ""
echo "--- Step 1/5: 基线测试（确认初始状态）---"
BASELINE_OUT=$(run_test) && BASELINE_RC=$? || BASELINE_RC=$?
if [ "$BASELINE_RC" -ne 0 ]; then
    echo "❌ 基线测试未通过！请先修复后再运行 G0"
    echo "  输出（最后 20 行）:"
    echo "$BASELINE_OUT" | tail -20
    exit 2
fi
echo "✅ 基线测试通过"

# ── Step 2: 备份 + 注入故障 ──
echo ""
echo "--- Step 2/5: 注入故障 ---"
cp "$SOURCE_FILE" "${SOURCE_FILE}${G0_BAK_SUFFIX}"

FAULT_MSG=""
if inject_fault "$SOURCE_FILE"; then
    FAULT_MSG="故障已注入"
else
    echo "⚠️  无法自动注入故障（源文件无匹配模式），请手工注入后重试"
    echo "  提示: 改一个关键返回值（如 code:0 → code:999），使功能必错"
    rm -f "${SOURCE_FILE}${G0_BAK_SUFFIX}"
    exit 2
fi
echo "  $FAULT_MSG"
echo "  diff 预览:"
diff -u "${SOURCE_FILE}${G0_BAK_SUFFIX}" "$SOURCE_FILE" | head -10 | sed 's/^/    /' || true

# ── Step 2.5: 等 dev-server 重编译（E2E 场景）──
if [ "$RUNNER" = "playwright" ]; then
    # 检测是否有 webpack/vite dev-server 在运行（常见端口 3000/5173/8972/8080）
    DEV_URL="${G0_DEV_URL:-}"
    if [ -z "$DEV_URL" ]; then
        for port in 8972 5173 3000 8080 4200; do
            if curl -s -o /dev/null -w '%{http_code}' "http://localhost:$port" 2>/dev/null | grep -q '^[23]'; then
                DEV_URL="http://localhost:$port"
                break
            fi
        done
    fi
    if [ -n "$DEV_URL" ]; then
        echo ""
        echo "  检测到 dev-server: $DEV_URL，等待重编译..."
        OLD_HASH=$(curl -s "$DEV_URL" 2>/dev/null | grep -oP '(main|bundle|app)\.[a-f0-9]+\.js' | head -1 || true)
        touch "$SOURCE_FILE" 2>/dev/null || true
        for i in $(seq 1 8); do
            sleep 2
            NEW_HASH=$(curl -s "$DEV_URL" 2>/dev/null | grep -oP '(main|bundle|app)\.[a-f0-9]+\.js' | head -1 || true)
            if [ -n "$NEW_HASH" ] && [ "$NEW_HASH" != "$OLD_HASH" ]; then
                echo "  重编译完成（#${i}, hash: ${NEW_HASH}）"
                break
            fi
            [ "$i" -eq 8 ] && echo "  ⚠️ 等待超时（16s），继续执行——可能命中旧 bundle"
        done
    fi
fi

# ── Step 3: 运行测试（预期失败）──
echo ""
echo "--- Step 3/5: 故障后测试（预期 ≥1 失败）---"
FAULT_OUT=$(run_test) && FAULT_RC=$? || FAULT_RC=$?
if [ "$FAULT_RC" -eq 0 ]; then
    echo ""
    echo "╔══════════════════════════════════════════════╗"
    echo "║  🛑 G0 阻断: 测试没有保护力                  ║"
    echo "╠══════════════════════════════════════════════╣"
    echo "║  故障注入后测试仍然全部通过                   ║"
    echo "║  这些测试断言不够强——操作成功和失败分不清      ║"
    echo "║  修复断言后重新 /implement                    ║"
    echo "╚══════════════════════════════════════════════╝"
    echo ""
    echo "  故障注入位置: $SOURCE_FILE"
    echo "  仍为 GREEN 的测试（最后 10 条）:"
    echo "$FAULT_OUT" | grep -E '✓|PASS|pass|ok' | head -10 | sed 's/^/    /' || echo "    (无法解析测试输出)"
    # 恢复
    mv "${SOURCE_FILE}${G0_BAK_SUFFIX}" "$SOURCE_FILE"
    exit 1
fi
echo "✅ 故障注入后确实有测试失败（证明测试有保护力）"
# 显示失败计数
FAIL_COUNT=$(echo "$FAULT_OUT" | grep -cE '✗|FAIL|fail|not ok' 2>/dev/null || echo "≥1")
echo "  失败数: ${FAIL_COUNT}"

# ── Step 4: 恢复源文件 ──
echo ""
echo "--- Step 4/5: 恢复源文件 ---"
mv "${SOURCE_FILE}${G0_BAK_SUFFIX}" "$SOURCE_FILE"
# 验证恢复干净
if [ -f "${SOURCE_FILE}${G0_BAK_SUFFIX}" ]; then
    echo "⚠️  备份文件残留: ${SOURCE_FILE}${G0_BAK_SUFFIX}"
    rm -f "${SOURCE_FILE}${G0_BAK_SUFFIX}"
fi
echo "✅ 文件已恢复"

# ── Step 5: 恢复后测试（预期全部通过）──
echo ""
echo "--- Step 5/5: 恢复后测试（预期全部通过）---"
RESTORE_OUT=$(run_test) && RESTORE_RC=$? || RESTORE_RC=$?
if [ "$RESTORE_RC" -ne 0 ]; then
    echo "⚠️  恢复后测试未全部通过——可能恢复不完整或有 flaky 测试"
    echo "  输出（最后 20 行）:"
    echo "$RESTORE_OUT" | tail -20
    exit 2
fi
echo "✅ 恢复后测试全部通过"

# ── 结果 ──
echo ""
echo "============================================"
echo "✅ G0 故障注入验证通过"
echo "   $(echo "$FAULT_MSG" | cut -c1-60)"
echo "   → 故障注入后测试失败 → 恢复后测试通过"
echo "   → 证明了: 测试真能拦住 Bug"
