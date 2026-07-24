#!/bin/bash
# stage-tracker.sh — PostToolUse hook：产物检测 + 阶段追踪
# 检测关键产物文件，自动更新 .devflow/stage 状态
# 阶段约束为 advisory 警告，不硬拦截

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

# 阶段顺序校验（仅在状态变化时做 advisory 警告）
stage_order="explore:done spec:done tickets:done tdd:done implement:done done"
current_index=0
prev_index=0
i=1
for s in $stage_order; do
    [ "$s" = "$detected_stage" ] && current_index=$i
    [ "$s" = "$previous_stage" ] && prev_index=$i
    i=$((i + 1))
done

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
    → 自查 ~/.claude/gate-checklists/spec-checklist.md（S1-S10）
  • 简单 → 跳过评审，直接 /to-tickets

  💡 上下文管理: 评审前建议 /compact；大型任务写 handoff 到 .devflow/handoff/

REMINDER
fi

if [ "$detected_stage" = "tickets:done" ] && [ "$detected_stage" != "$previous_stage" ]; then
    cat >&2 <<'REMINDER'

📋 tickets:done — 下一步：Ticket 审查 + TDD 前置

  🛑 进入 /tdd 前，先做 Ticket 宪法审查:
     → 优先: python3 .devflow/scripts/check_constitution.py --batch issues/
       (15 项 L1 自动检查: frontmatter/AC标注/estimate/blocked_by/安全红线)
     → 补充: LLM 对照 ~/.claude/gate-checklists/tickets-checklist.md §自动审查 L2 语义层
       (接口签名/前置准备具体性/AC覆盖完整性/DAG对齐)
     → 输出审查报告，人工确认通过后方可进入 /tdd

  审查通过后，每个 ticket 按序执行:
  1. /tdd <ticket> — 按 AC 写失败测试 + stub → 运行测试确认 🔴
  2. RED commit（message 含 "TDD: RED"）
  3. 🛑 立即停止，执行 C1-C5 预检（~/.claude/gate-checklists/test-checklist.md §C1-C5）
     → 运行 5 项检查，输出结构化报告
     → 等待人工确认，未经确认不得继续
     → 确认通过后方可进入 /implement

  💡 上下文管理: 建议写 handoff（完成/待处理/约束/文件）→ /clear → 新会话进入审查

REMINDER
fi

if [ "$detected_stage" = "tdd:done" ] && [ "$detected_stage" != "$previous_stage" ]; then
    cat >&2 <<'REMINDER'

📋 tdd:done — TDD RED 阶段完成，准备 /implement

  /implement 启动前确认:
  □ R1-R6 就绪门禁: ~/.claude/gate-checklists/tdd-readiness-checklist.md
  □ T1-T4 TDD 质量: ~/.claude/gate-checklists/test-checklist.md
  🛑 C1-C5 预检: 必须已输出报告并经人工确认。如未完成 → 立即退回执行 C1-C5，禁止跳过
  □ 无依赖 ticket 可并行 /implement；有 blocked_by 需等上游 GREEN

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
