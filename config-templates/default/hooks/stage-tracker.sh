#!/bin/bash
# stage-tracker.sh — PostToolUse hook：产物检测 + 阶段追踪 + 过渡验证
# 检测关键产物文件，调用 stage-verify.sh 验证产物质量后才写 .devflow/stage
# 5.9: 过渡门禁验证——产物质量不达标 → exit 2 硬阻断，stage 不推进

set -euo pipefail

TOOL_NAME="$1"
TOOL_INPUT="$2"
WORKSPACE="${WORKSPACE:-$(pwd)}"
STAGE_FILE="$WORKSPACE/.devflow/stage"
TRACE_SCRIPT="$WORKSPACE/.devflow/scripts/trace.sh"

trace() { bash "$TRACE_SCRIPT" "$@" 2>/dev/null || true; }

# 仅在工作区有 .devflow/ 的项目中生效
[ -d "$WORKSPACE/.devflow" ] || exit 0

# 阶段检测：基于产物而非 skill 调用
detected_stage=""

# 检测 spec.md
if [ -f "$WORKSPACE/spec.md" ] && [ -s "$WORKSPACE/spec.md" ]; then
    detected_stage="spec:done"
fi

# 检测 issues/ 下是否有新文件（比 tickets 阶段更可靠）
if [ -d "$WORKSPACE/issues" ]; then
    issue_count=$(find "$WORKSPACE/issues" -maxdepth 1 -name "*.md" -not -name "TEMPLATE.md" -type f 2>/dev/null | wc -l)
    if [ "$issue_count" -gt 0 ]; then
        detected_stage="tickets:done"
    fi
fi

# 检测 TDD RED commit → tdd:done（在 tickets 之后、implement 之前）
# 检测 tickets 审查是否完成（constitution 检查 + tickets-checklist 审查）
if [ -f "$WORKSPACE/.devflow/constitution-report.json" ] && [ -s "$WORKSPACE/.devflow/constitution-report.json" ]; then
    detected_stage="tickets:reviewed"
fi

if git -C "$WORKSPACE" log --oneline -1 2>/dev/null | grep -q "TDD: RED"; then
    detected_stage="tdd:done"
fi

# 检测 PR 是否已创建
if git -C "$WORKSPACE" log --oneline -1 2>/dev/null | grep -qiE "Merge pull request|\(#\d+\)"; then
    detected_stage="implement:done"
fi

# 无检测到任何阶段更新 → 跳过
[ -z "$detected_stage" ] && exit 0

# 读取上次记录
previous_stage=""
[ -f "$STAGE_FILE" ] && previous_stage=$(cat "$STAGE_FILE" 2>/dev/null || echo "")

# 无变化 → 跳过
[ "$detected_stage" = "$previous_stage" ] && exit 0

# 阶段顺序校验
stage_order="explore:done spec:done tickets:done tickets:reviewed tdd:done implement:done done"
current_index=0
prev_index=0
i=1
for s in $stage_order; do
    [ "$s" = "$detected_stage" ] && current_index=$i
    [ "$s" = "tdd:done" ] && tdd_index=$i
    [ "$s" = "$previous_stage" ] && prev_index=$i
    i=$((i + 1))
done

# ── 5.9: 过渡门禁验证——硬阻断 stage 写入 ──
VERIFY_SCRIPT="$WORKSPACE/.devflow/scripts/stage-verify.sh"
if [ -f "$VERIFY_SCRIPT" ]; then
    # 构建待验证阶段列表（含被跳过的中间阶段）
    stages_to_verify=""
    start=$((prev_index > 0 ? prev_index + 1 : 1))
    j=1
    for s in $stage_order; do
        [ "$j" -ge "$start" ] && [ "$j" -le "$current_index" ] && stages_to_verify="$stages_to_verify $s"
        j=$((j + 1))
    done
    if ! bash "$VERIFY_SCRIPT" $stages_to_verify 2>&1; then
        # 死循环检测
        BLOCK_FILE="$WORKSPACE/.devflow/.verify-blocks"
        block_count=0
        [ -f "$BLOCK_FILE" ] && block_count=$(grep "^$detected_stage:" "$BLOCK_FILE" 2>/dev/null | cut -d: -f2 || echo "0")
        block_count=$((block_count + 1))
        echo "$detected_stage:$block_count:$(date +%s)" > "$BLOCK_FILE"
        if [ "$block_count" -ge 3 ]; then
            cat >&2 <<EOF

⚠️  同一阶段 ($detected_stage) 已连续阻断 ${block_count} 次——请停下来确认：
  1. 检查是否理解验证条件（见上方 FAIL 项）
  2. 确认修复方向正确（不要反复试同一路径）
  3. 如果是验证条件过于严格 → 报告给人，不要绕过
EOF
        fi
        trace "stage.blocked" from="$previous_stage" to="$detected_stage"
        exit 2
    fi
    # 验证通过 → 清除阻断计数
    rm -f "$BLOCK_FILE"
    trace "stage.verify" from="$previous_stage" to="$detected_stage" stages="$stages_to_verify"
else
    echo "[stage-tracker] ⚠️ stage-verify.sh 未部署——本次推进跳过验证（advisory）" >&2
fi

# 写入新阶段
echo "$detected_stage" > "$STAGE_FILE"
trace "stage.transition" from="$previous_stage" to="$detected_stage"

# ── 阶段进入提醒（advisory，不拦截）──

if [ "$detected_stage" = "spec:done" ] && [ "$detected_stage" != "$previous_stage" ]; then
    cat >&2 <<'REMINDER'

📋 spec:done — 下一步：spec 评审

  按任务规模选择：
  • 大型（spec >200 行 / 涉及 >3 模块 / 安全红线 / 工作量 >3d）
    → /review-cc-cli --opus --rubric prd,plan \
        --with ~/.claude/gate-checklists/spec-checklist.md spec.md
  • 中型（spec 50-200 行 / 1-2 模块）
    → 自查 ~/.claude/gate-checklists/spec-checklist.md— 必须逐项过 S1-S13：
	      S1-S5（六段+风险+AC+异常+依赖）、S10-S13（产物+测试段+特征测试+分层）
	      🛑 S11（Testing 段含分层分配表）、S13（E2E ≤ 15%，每项标注决策路径理由）
	    → 测试分层：Read ~/.claude/knowledge/10-测试分层策略.md §决策树，按决策树选层级
  • 简单 → 跳过评审，直接 /to-tickets

  💡 上下文管理: 评审前建议 /compact；大型任务写 handoff 到 .devflow/handoff/

REMINDER
fi

if [ "$detected_stage" = "tickets:done" ] && [ "$detected_stage" != "$previous_stage" ]; then
    cat >&2 <<'REMINDER'

📋 tickets:done — 下一步：Ticket 审查 + TDD 前置

  🛑 测试分层——进入 /tdd 前必做:
	     → Read ~/.claude/knowledge/10-测试分层策略.md §决策树
	     → 对照 spec §Testing 的分层分配表，确认每个 ticket 选用的测试层级与 spec 一致
	     → spec-checklist S13 要求 E2E ≤ 15%，如超阈值需调整分层

	  🛑 进入 /tdd 前，必须先通过 Ticket 审查 Gate（tickets:reviewed）:
     → 步骤1: python3 .devflow/scripts/check_constitution.py --batch issues/ --json > .devflow/constitution-report.json
       (16 项 L1 自动检查: frontmatter/AC标注/estimate/blocked_by/安全红线)
     → 步骤2: LLM 对照 ~/.claude/gate-checklists/tickets-checklist.md §自动审查 L2 语义层
       (接口签名/前置准备具体性/AC覆盖完整性/DAG对齐)
     → 步骤3: 确认全部通过后，将审查结论追加写入 .devflow/constitution-report.json
     → 🛑 生成 .devflow/constitution-report.json 后自动进入 tickets:reviewed → 方可 /tdd

  审查通过后，每个 ticket 按序执行:
  1. /tdd <ticket> — 按 AC 写失败测试 + stub → 运行测试确认 🔴
  1.5 C0 提交前秒检（~/.claude/gate-checklists/test-checklist.md §C0）
       → 运行 .devflow/scripts/test-gate.sh（C0.1-C0.8 自动检查：调试残留/恒真断言/硬编码端口/固定延时/测试发现/try-catch断言/if-count-return/断言强度分布），不通过则阻断
       → 通过后 RED commit
  2. RED commit（message 含 "TDD: RED"）
  3. 🛑 立即停止，执行完整预检（Read ~/.claude/gate-checklists/test-checklist.md 全文，含 C0 + C1-C5 + C7 + 项目扩展）
     → R7 分层一致性: 确认 /tdd 接缝选择与 spec §Testing 分层分配一致，偏离需注释理由
     → C7 E2E 可信度（E2E 项目）: Action 走 UI + 完整链路 + 结果断言诚实
     → 逐项运行全部检查，输出结构化报告
     → 等待人工确认，未经确认不得继续
     → 确认通过后方可进入 /implement

  💡 上下文管理: 建议写 handoff（完成/待处理/约束/文件）→ /clear → 新会话进入审查

  🌿 分支: 所有 ticket commit 提交到当前 worktree 分支，全部完成+验收后 PR→main

REMINDER
    # [legacy] ticket 检测
    if grep -q "\[legacy\]" "$WORKSPACE/issues/"*.md 2>/dev/null; then
        cat >&2 <<'LEGACY'
🛑 检测到 [legacy] ticket — 涉及无测试覆盖的遗留代码。

    执行顺序改为:
    0. /characterize <ticket> — Read characterization-checklist.md
       → ANALYZE → CAPTURE → VERIFY（改代码确认变红→恢复）
       → 特征测试 GREEN + 提交后，方可进入下一步
    1. /tdd <ticket> — 按 AC 写失败测试 + stub
    （后续步骤不变）

    跳过步骤 0 直接改旧代码 = Edit and Pray。
    无安全网改 9044 行代码 = 改完不知道是修复还是破坏。

LEGACY
    fi
fi

if [ "$detected_stage" = "tickets:reviewed" ] && [ "$detected_stage" != "$previous_stage" ]; then
    cat >&2 <<'REMINDER'

📋 tickets:reviewed — Ticket 审查通过，准备 /tdd

  🛑 宪法审查已通过（constitution-report.json 已生成）
  □ 测试分层已对照 spec §Testing 确认
  □ tickets-checklist L2 语义审查已完成
  □ 人工已确认审查报告

  下一步——每个 ticket 按序执行 /tdd:
  1. /tdd <ticket> — 按 AC 写失败测试 + stub → 运行测试确认 🔴
  2. C0 提交前秒检 → bash .devflow/scripts/test-gate.sh（C0.1-C0.9）
  3. 通过后 RED commit（message 含 "TDD: RED"）
  4. 🛑 立即停止——等待人工确认后方可进入 /implement

  🌿 分支: 所有 ticket commit 提交到当前 worktree 分支

REMINDER
fi

if [ "$detected_stage" = "tdd:done" ] && [ "$detected_stage" != "$previous_stage" ]; then
    cat >&2 <<'REMINDER'

📋 tdd:done — TDD RED 阶段完成，准备 /implement

  /implement 启动前确认:
  □ R1-R6 就绪门禁: ~/.claude/gate-checklists/tdd-readiness-checklist.md
  □ T1-T4 TDD 质量: ~/.claude/gate-checklists/test-checklist.md
  🛑 test-checklist 完整预检: 必须已 Read 全文并按全部检查项（C0 + C1-C5 + C7 + G0 + 项目扩展）执行并输出报告，经人工确认。如未完成 → 立即退回执行，禁止跳过
  🛑 G0 故障注入验证 — /implement 标记 done 前必做:
     → 自动: bash .devflow/scripts/g0-inject.sh <你刚改的源文件> [测试名关键字]
       脚本自动注入故障 → 跑测试（预期失败）→ 恢复 → 再跑测试（预期通过）
       ❌ 故障注入后测试仍全绿 = 硬阻断（断言不够强，需修复后重新 /implement）
     → 手工 fallback（脚本无法自动注入时）:
       在被测代码中改一个关键值使功能必错 → 跑测试（必须 RED）
       → 如仍通过 → 断言不够强 → 修复断言后重新注入
       → 撤销故障注入，测试重新 GREEN
     → 详细规则: ~/.claude/gate-checklists/test-checklist.md §G0
  🛑 R7 分层一致性: 确认 /tdd 接缝选择与 spec §Testing 分层分配一致
  ⚠️ GREEN 阶段禁止修改测试文件——测试断言在 /tdd 以最终业务行为形式写入（RED 靠 stub 抛 NotImplementedError/501 保证），GREEN 阶段只改实现（stage-gate-block 硬阻断执行）。测试有 bug → TEST_BUG: <file>:<line> — <原因>，等人工判断
  □ 无依赖 ticket 可并行 /implement；有 blocked_by 需等上游 GREEN
	  🛑 /implement 反作弊规则（违反 = 实现无效，重新 /implement）:
	     1. 禁止修改测试文件 — 测试 = spec 的可执行版本，只能改实现去适配测试
	        测试有 bug？→ STOP，输出 TEST_BUG: <file>:<line> — <原因>，等人工判断
	     2. 禁止硬编码返回值骗测试 — 不许 return { code: 0, data: [] } / if (testEnv) return mockData
	     3. GREEN commit 前必做（三项全部通过方可提交）:
	        a. 运行全量测试，粘贴完整输出（含 X passing / Y failing 计数）
	        b. 运行 bash .devflow/scripts/green-gate.sh — 逐条确认
	        c. 逐条 AC 对照 git diff 验证:
	           git diff <RED-commit>..HEAD --stat → 每个改动文件必须能对应到具体 AC
	           输出: | AC | 状态 | 证据（file:line）|
	        ⚠️ 不许只说"全部通过"而不贴实际输出——贴输出 = 唯一可接受的证据

  🐴 Ponytail 决策阶梯（写实现代码前逐级检查）:
     1. 这真的需要存在？（YAGNI — 只为 ticket AC 写代码）
     2. 代码库里已有了？→ 复用已有工具/类型/模式
     3. 标准库能做？→ 用 stdlib，不自己写
     4. 原生平台功能覆盖？→ CSS>JS, DB约束>应用代码
     5. 已安装的依赖能解决？→ 不加新依赖
     6. 能一行搞定？→ 就一行
     7. 都不行 → 写最小可工作代码
     有意简化时标记: # ponytail: <简化描述>, <升级条件>

  🤖 自动重试循环（/implement 内建）:
     测试失败 → 读错误输出 → 修复实现（不改测试）→ 重试
     最多 3 次，超限后 escalation 人工介入

  💡 上下文管理: 进入下一层前 /compact + 写 handoff

REMINDER
fi

# 阶段跳跃 → advisory 警告
if [ "$current_index" -gt 0 ] && [ "$prev_index" -gt 0 ] && [ "$current_index" -gt "$((prev_index + 1))" ]; then
    trace "stage.skip" from="$previous_stage" to="$detected_stage" skipped="$((current_index - prev_index - 1))"
    cat >&2 <<EOF

⚠️  stage-tracker: 检测到阶段跳跃
   上一阶段: $previous_stage
   当前检测: $detected_stage
   建议: 确认中间阶段产物是否存在，缺失可能影响后续质量

EOF
    exit 0  # advisory — 不硬拦截
fi

# 正常推进
exit 0
