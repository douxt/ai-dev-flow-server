#!/bin/bash
# stage-verify.sh — 阶段推进前校验产物质量（5.9 过渡门禁验证）
# 由 stage-tracker.sh 调用，不被 CC 直接执行
# 用法: bash stage-verify.sh <stage1> [<stage2> ...]
# exit 0 = 全部通过, exit 1 = 有失败项
# STAGE_VERIFY_BYPASS=1 跳过所有检查（legacy 导入用）

set -euo pipefail

WORKSPACE="${WORKSPACE:-$(pwd)}"
SCRIPTS_DIR="$WORKSPACE/.devflow/scripts"
FAIL=0

[ "${STAGE_VERIFY_BYPASS:-0}" = "1" ] && { echo "[stage-verify] STAGE_VERIFY_BYPASS=1 — 跳过所有验证"; exit 0; }

check() {
    local stage="$1" name="$2" result="$3" detail="$4"
    if [ "$result" -eq 0 ]; then
        echo "[stage-verify] $stage — $name: PASS"
    else
        echo "[stage-verify] $stage — $name: FAIL — $detail"
        FAIL=1
    fi
}

# ── spec:done ──
verify_spec_done() {
    # S1: 非空
    if [ -s "$WORKSPACE/spec.md" ]; then
        check "spec:done" "S1 non-empty" 0 ""
    else
        check "spec:done" "S1 non-empty" 1 "spec.md is empty or missing"
    fi

    # S2: 必备段（至少匹配 2/3: ## Testing, ## Risks & Mitigations, AC- 表格行）
    local hits=0
    grep -q '## Testing' "$WORKSPACE/spec.md" 2>/dev/null && hits=$((hits + 1))
    grep -q '## Risks & Mitigations\|## Risk' "$WORKSPACE/spec.md" 2>/dev/null && hits=$((hits + 1))
    grep -qE '^\| *AC-|Acceptance Criteria|验收标准' "$WORKSPACE/spec.md" 2>/dev/null && hits=$((hits + 1))
    if [ "$hits" -ge 2 ]; then
        check "spec:done" "S2 sections ($hits/3)" 0 ""
    else
        check "spec:done" "S2 sections ($hits/3)" 1 "缺少必备段: 需含 ## Testing + ## Risks & Mitigations + AC（至少 2 项）。参考 ~/.claude/gate-checklists/spec-checklist.md"
    fi
}

# ── tickets:done ──
verify_tickets_done() {
    local const="$SCRIPTS_DIR/check_constitution.py"
    if [ ! -f "$const" ]; then
        check "tickets:done" "T1 constitution" 0 "(脚本缺失，跳过)"
        return
    fi
    if python3 "$const" --batch "$WORKSPACE/issues/" 2>&1; then
        check "tickets:done" "T1 constitution" 0 ""
    else
        check "tickets:done" "T1 constitution" 1 "constitution 检查未通过——修复上方列出的 failed 规则后重试"
    fi
}

# ── tickets:reviewed ──
verify_tickets_reviewed() {
    local report="$WORKSPACE/.devflow/constitution-report.json"

    # R1: 报告存在且非空
    if [ -f "$report" ] && [ -s "$report" ]; then
        check "tickets:reviewed" "R1 report exists" 0 ""
    else
        check "tickets:reviewed" "R1 report exists" 1 "constitution-report.json 缺失或为空——运行 tickets:done 提醒中的步骤 1-3"
        return
    fi

    # R2: failed == 0（容错解析：python json.loads → grep fallback）
    local failed
    failed=$(python3 -c "
import json, sys
try:
    d = json.load(open('$report'))
except Exception:
    sys.exit(1)
f = d.get('total_failed')
if f is None and 'results' in d:
    f = sum(r.get('failed', 0) for r in d['results'])
if f is None:
    f = d.get('failed')
print(f if f is not None else '')
" 2>/dev/null || true)
    if [ -z "$failed" ]; then
        # grep fallback
        failed=$(grep -oP '"total_failed"\s*:\s*\K\d+' "$report" 2>/dev/null | head -1 || echo "")
    fi
    if [ -n "$failed" ] && [ "$failed" = "0" ]; then
        check "tickets:reviewed" "R2 failed=$failed" 0 ""
    elif [ -n "$failed" ]; then
        check "tickets:reviewed" "R2 failed=$failed" 1 "报告有 $failed 项失败——修复后重新生成 report"
    else
        check "tickets:reviewed" "R2 parse" 1 "无法解析报告——重新生成: python3 .devflow/scripts/check_constitution.py --batch issues/ --json > .devflow/constitution-report.json"
        return
    fi

    # R3: 未过期（mtime）
    local newer
    newer=$(find "$WORKSPACE/issues" -maxdepth 1 -name '*.md' ! -name 'TEMPLATE.md' -newer "$report" 2>/dev/null | head -1 || true)
    if [ -z "$newer" ]; then
        check "tickets:reviewed" "R3 staleness" 0 ""
    else
        check "tickets:reviewed" "R3 staleness" 1 "issues/ 中有文件比 report 新——重新运行 check_constitution.py --batch"
    fi

    # R4: 数量一致
    local scanned issue_count
    scanned=$(python3 -c "import json; d=json.load(open('$report')); print(d.get('scanned',''))" 2>/dev/null || echo "")
    issue_count=$(find "$WORKSPACE/issues" -maxdepth 1 -name '*.md' ! -name 'TEMPLATE.md' -type f 2>/dev/null | wc -l)
    if [ -z "$scanned" ] || [ "$scanned" = "$issue_count" ]; then
        check "tickets:reviewed" "R4 count ($scanned/$issue_count)" 0 ""
    else
        check "tickets:reviewed" "R4 count ($scanned/$issue_count)" 1 "报告扫描数($scanned) ≠ 当前 issue 数($issue_count)——重新生成 report"
    fi
}

# ── tdd:done ──
verify_tdd_done() {
    local tg="$SCRIPTS_DIR/test-gate.sh"
    if [ ! -f "$tg" ]; then
        check "tdd:done" "D1 test-gate" 0 "(脚本缺失，跳过)"
        return
    fi
    if bash "$tg" 2>&1; then
        check "tdd:done" "D1 test-gate" 0 ""
    else
        check "tdd:done" "D1 test-gate" 1 "test-gate.sh C0 检查未通过——RED commit 不应包含调试残留/恒真断言/固定延时等"
    fi
}

# ── implement:done ──
verify_implement_done() {
    # I1: RED commit 存在
    if git -C "$WORKSPACE" log --oneline --grep="TDD: RED" -1 2>/dev/null | grep -q "TDD: RED"; then
        check "implement:done" "I1 RED commit" 0 ""
    else
        check "implement:done" "I1 RED commit" 1 "git 历史中无 TDD: RED commit——/tdd 被跳过，无 RED 验证"
    fi

    # I2: green-gate
    local gg="$SCRIPTS_DIR/green-gate.sh"
    if [ ! -f "$gg" ]; then
        check "implement:done" "I2 green-gate" 0 "(脚本缺失，跳过)"
    elif bash "$gg" 2>&1; then
        check "implement:done" "I2 green-gate" 0 ""
    else
        check "implement:done" "I2 green-gate" 1 "green-gate G2.x 有标记项——见上方输出"
    fi

    # I3: test-gate
    local tg="$SCRIPTS_DIR/test-gate.sh"
    if [ ! -f "$tg" ]; then
        check "implement:done" "I3 test-gate" 0 "(脚本缺失，跳过)"
        return
    fi
    if bash "$tg" 2>&1; then
        check "implement:done" "I3 test-gate" 0 ""
    else
        check "implement:done" "I3 test-gate" 1 "test-gate.sh C0 检查未通过"
    fi

    # I4: G0 故障注入证据（未跑 G0 不推进 implement:done）
    local g0="$SCRIPTS_DIR/g0-inject.sh"
    if [ ! -f "$g0" ]; then
        check "implement:done" "I4 G0 evidence" 0 "(g0-inject.sh 未部署，跳过)"
        return
    fi
    local g0_marker="$WORKSPACE/.devflow/.g0-passed"
    if [ -f "$g0_marker" ] && [ -s "$g0_marker" ]; then
        local red_ts g0_ts
        red_ts=$(git -C "$WORKSPACE" log --grep="TDD: RED" -1 --format=%ct 2>/dev/null || echo "0")
        g0_ts=$(head -1 "$g0_marker" 2>/dev/null | cut -d' ' -f1 || echo "0")
        if [ "${g0_ts:-0}" -ge "${red_ts:-0}" ]; then
            check "implement:done" "I4 G0 evidence" 0 ""
        else
            check "implement:done" "I4 G0 evidence" 1 \
                "G0 标记 ($(date -d @"$g0_ts" '+%F %T' 2>/dev/null || echo "$g0_ts")) 早于 RED commit ($(date -d @"$red_ts" '+%F %T' 2>/dev/null || echo "$red_ts"))——重新运行: bash .devflow/scripts/g0-inject.sh <源文件>"
        fi
    else
        check "implement:done" "I4 G0 evidence" 1 \
            "未找到 G0 执行证据——运行: bash .devflow/scripts/g0-inject.sh <你改的源文件> [测试名关键字]"
    fi
}

# ── 主调度 ──
cd "$WORKSPACE"

for stage in "$@"; do
    case "$stage" in
        spec:done)       verify_spec_done ;;
        tickets:done)    verify_tickets_done ;;
        tickets:reviewed) verify_tickets_reviewed ;;
        tdd:done)        verify_tdd_done ;;
        implement:done)  verify_implement_done ;;
        *) echo "[stage-verify] $stage — SKIP (未知阶段，无验证规则)" ;;
    esac
done

exit $FAIL
