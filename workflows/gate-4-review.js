export const meta = {
  name: 'gate-4-review',
  description: 'Gate 4: Issue 评审 — 读宪法 + issues/ → 调 /review-cc-cli → 更新 .gate-state',
  phases: [
    { title: '检查前置', detail: '验证 Gate 3 已 passed' },
    { title: 'Issue评审', detail: '调用 /review-cc-cli 对照宪法评审' },
    { title: '出口检查', detail: '确认评审通过' },
  ],
}

phase('检查前置')
await agent(`Read .gate-state，确认 gate-3.status === "passed"。
如果 gate-3 不是 passed，输出 "❌ Gate 3 未通过，请先执行 /gate-3-issues" 并停止。`, { label: '检查前置Gate' })

phase('Issue评审')
log('启动 /review-cc-cli 对照宪法评审所有 issue...')

await agent(`调用 /review-cc-cli --rubric plan --explore 评审 issues/ 目录下的所有 issue 文件。

评审要求：
1. 逐条对照 .devflow/knowledge/04-Issue质量宪法.md 的 14 项规则
2. 检查每条 issue 的 estimate、type、AC、前置准备、blocked_by 等
3. 检查依赖链是否形成 DAG（无循环）

输出评审报告，verdict 为 APPROVED 或 CHANGES_REQUESTED。`, { label: '评审Issue' })

phase('出口检查')

const result = await agent(`逐条检查 Gate 4 出口标准：

| # | 检查项 | 方法 |
|:-:|--------|------|
| 4.1 | 至少 1 轮评审完成 | 产生 .review-report-*.json |
| 4.2 | 最终 verdict APPROVED | 不接受 CHANGES_REQUESTED |
| 4.3 | 评审员按宪法检查 | prompt 携带了宪法文件 |
| 4.4 | 阻塞项全部修复 | 跟踪表已闭环 |
| 4.5 | 各 issue 一致 | estimate/blocked_by 对齐 |

如果全部通过：将 .gate-state 中 gate-4 的 status 改为 "passed"。
如果评审 verdict 为 CHANGES_REQUESTED：将 gate-4 设为 "blocked"，gate-3 也设为 "blocked"（需要回退重拆）。

输出 JSON: {"gate": "gate-4", "verdict": "PASSED|BLOCKED", "checks": {...}, "missing": []}`, { label: 'Gate4出口检查' })

const parsed = JSON.parse(result.match(/\{[\s\S]*\}/)?.[0] || '{}')
if (parsed.verdict === 'PASSED') {
  log('✅ Gate 4 通过，可以进入 /gate-5-prep')
} else if (parsed.verdict === 'BLOCKED') {
  log('❌ Gate 4 不通过，已回退到 Gate 3（.gate-state 中 gate-3 和 gate-4 均已设为 blocked）')
  log('请按评审意见重拆 Issue 后重新 /gate-3-issues')
} else {
  log(`❌ Gate 4 不通过，缺失项: ${(parsed.missing || []).join(', ')}`)
}
