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

REMINDER
fi

if [ "$detected_stage" = "tickets:done" ] && [ "$detected_stage" != "$previous_stage" ]; then
    cat >&2 <<'REMINDER'

📋 tickets:done — 下一步：TDD 前置

  每个 ticket 按序执行:
  1. /tdd <ticket> — 按 AC 写失败测试 + 接口 stub → 🔴 RED
  2. /implement <ticket> — 填实现逻辑 → 🟢 GREEN
  3. 全部 ticket 通过后 → /code-review

REMINDER
fi

if [ "$detected_stage" = "tdd:done" ] && [ "$detected_stage" != "$previous_stage" ]; then
    cat >&2 <<'REMINDER'

📋 tdd:done — TDD RED 阶段完成，准备 /implement

  /implement 启动前确认:
  □ R1-R6 就绪门禁: ~/.claude/gate-checklists/tdd-readiness-checklist.md
  □ T1-T4 TDD 质量: ~/.claude/gate-checklists/test-checklist.md
  □ C1-C4 转换检查: 全部 RED、原因正确、commit 已提交、无实现混入
  □ 无依赖 ticket 可并行 /implement；有 blocked_by 需等上游 GREEN

  自动重试: /implement 失败后自动修复重试，最多 3 次，超限后 escalation。

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
