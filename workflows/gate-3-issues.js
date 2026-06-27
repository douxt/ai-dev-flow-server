export const meta = {
  name: 'gate-3-issues',
  description: 'Gate 3: 拆解 Issue — 读 PRD + 宪法 → 调 /to-issues → 质量门禁 → 更新 .gate-state',
  phases: [
    { title: '检查前置', detail: '验证 Gate 2 已 passed' },
    { title: '读宪法+PRD', detail: '读取 Issue宪法 + PRD' },
    { title: '拆Issue', detail: '调用 /to-issues 附带宪法' },
    { title: '出口检查', detail: '跑 16 项出口检查' },
  ],
}

phase('检查前置')
await agent(`Read .gate-state，确认 gate-2.status === "passed"。
如果 gate-2 不是 passed，输出 "❌ Gate 2 未通过，请先执行 /gate-2-prd" 并停止。`, { label: '检查前置Gate' })

phase('读宪法+PRD')
await agent(`Read .devflow/knowledge/04-Issue质量宪法.md，理解 14 项宪法规则。
Read docs/ 下最新的 PRD 文件，理解需求范围和验收条件。`, { label: '读宪法和PRD' })

phase('拆Issue')
log('调用 /to-issues 拆解 Issue（附带宪法上下文）...')

await agent(`调用 /to-issues 技能将 PRD 拆成垂直切片 issue。

**必须附带 .devflow/knowledge/04-Issue质量宪法.md 作为上下文**。要求：
1. 每条 issue 对照宪法 14 项逐条自检
2. 垂直切片：每条是完整端到端路径，非水平层
3. 单 issue 工时 ≤1d
4. 类型标记：type: AFK（纯自动）/ type: HITL（含人工）
5. 依赖链清晰：blocked_by 字段
6. 每条 issue 含质量自检 checklist`, { label: '拆解Issue' })

phase('出口检查')
log('逐条跑 Gate 3 出口检查...')

const result = await agent(`逐条检查 Gate 3 出口标准（16 项）：

| # | 检查项 | 方法 |
|:-:|--------|------|
| 3.1 | 每条 estimate ≤1d | grep estimate: |
| 3.2 | type 正确 | AFK/HITL 分类正确 |
| 3.3 | AC 全可量化 | 无模糊词 |
| 3.4 | 代码目录已指定 | AC 或正文写清路径 |
| 3.5 | 前置准备完整 | 外部服务/token/文件已列 |
| 3.6 | mock/E2E 策略明确 | AC 写清测试方式 |
| 3.7 | SDK 用法可参考 | 依赖表格已记录 |
| 3.8 | 验收无主观 | 可自动化或可观测 |
| 3.9 | blocked_by 无循环 | 依赖链检查 |
| 3.10 | 架构约束已引用 | 不可变规则已引用 |
| 3.11 | AC 覆盖集成层 | 不只模块，含编配 |
| 3.12 | Scope 边界清晰 | In/Out 清单 |
| 3.13 | needs_* 已声明 | needs_llm/vision/pdf/docker |
| 3.14 | test_files 已指定 | 精确路径 |
| 3.15 | 总工时与 PRD 一致 | sum(estimate) ±20% |
| 3.16 | 切片方向标注 | 垂直/水平 |

如果全部通过：将 .gate-state 中 gate-3 的 status 改为 "passed"。
如果不通过：输出缺失项清单。

输出 JSON: {"gate": "gate-3", "verdict": "PASSED|FAILED", "checks": {...}, "missing": []}`, { label: 'Gate3出口检查' })

const parsed = JSON.parse(result.match(/\{[\s\S]*\}/)?.[0] || '{}')
if (parsed.verdict === 'PASSED') {
  log('✅ Gate 3 通过，可以进入 /gate-4-review')
} else {
  log(`❌ Gate 3 不通过，缺失项: ${(parsed.missing || []).join(', ')}`)
  log('请修正 issue 后重新 /gate-3-issues')
}
