export const meta = {
  name: 'gate-2-prd',
  description: 'Gate 2: 产出 PRD — 读宪法 → 调 /to-prd → 9 项出口检查 → 自动更新 .gate-state',
  phases: [
    { title: '检查前置', detail: '验证 Gate 1 已 passed' },
    { title: '读宪法', detail: '读取 PRD 宪法' },
    { title: '生成PRD', detail: '调用 /to-prd 附带宪法' },
    { title: '出口检查', detail: '逐条跑 9 项出口检查' },
  ],
}

phase('检查前置')
await agent(`Read .gate-state，确认 gate-1.status === "passed"。
如果 gate-1 不是 passed，输出 "❌ Gate 1 未通过，请先执行 /gate-1-grill" 并停止。`, { label: '检查前置Gate' })

phase('读宪法')
await agent(`Read .devflow/knowledge/03-PRD质量宪法.md，理解 11 项宪法规则。
重点记住：出口检查对照的是 #1 #2 #3 #4 #5 #7 #8 #9 #11 这 9 项。
注意 #5 无外部依赖时可标 N/A，#8 纯技术 PRD 无 User Stories 时可标 N/A。`, { label: '读PRD宪法' })

phase('生成PRD')
log('调用 /to-prd 生成 PRD（附带宪法上下文）...')

await agent(`调用 /to-prd 技能生成 PRD。

**必须附带 .devflow/knowledge/03-PRD质量宪法.md 作为上下文**。要求：
1. 按宪法 11 项逐条自检
2. 在 PRD 尾部输出合规表：

\`\`\`markdown
## PRD 质量宪法合规表
| # | 规则 | 状态 | 证据/位置 |
|---|------|:----:|----------|
| 1 | 章节完整 | ✅/❌ | 证据 |
| ...共 11 行
\`\`\`

3. PRD 必须包含六段：Problem / Solution / User Stories / Implementation / Testing / Out of Scope
4. Risks ≥5 项且有缓解措施
5. AC 定量可测（EARS 格式推荐）
6. 异常路径覆盖 4 类（空状态/错误状态/边界条件/权限拒绝）`, { label: '生成PRD' })

phase('出口检查')
log('逐条跑 Gate 2 出口检查...')

const result = await agent(`逐条检查 Gate 2 出口标准（对照 PRD 质量宪法 9 项）：

| # | 检查项 | 宪法条目 | 检查方法 |
|:-:|--------|:--------:|------|
| 2.1 | 六段齐全 | #1 | 扫标题确认六段都在 |
| 2.2 | Risks ≥5 + 缓解 | #2 | 数风险条目，每条有缓解 |
| 2.3 | AC 定量可测 | #3 | 读 AC，查"质量好""完整"等模糊词 |
| 2.4 | 异常路径 4 类 | #4 | 逐类确认空状态/错误/边界/权限 |
| 2.5 | 外部依赖接口签名 | #5 | 检查接口写到参数/返回值级（无外部依赖则 N/A） |
| 2.6 | 估算 ≤5d | #7 | 读工时数字 |
| 2.7 | US 有独立 AC | #8 | 检查 US 格式和独立验收条件（纯技术 PRD 则 N/A） |
| 2.8 | Out of Scope 不含 N+1 | #9 | 扫 OOS 内容，确认无 Phase N+1 内容 |
| 2.9 | 架构约束已引用 | #11 | 确认列出了不可变架构规则 |

如果全部通过（含 N/A 项）：将 .gate-state 中 gate-2 的 status 改为 "passed"。
如果不通过：输出具体缺失项，不修改 .gate-state。

输出 JSON: {"gate": "gate-2", "verdict": "PASSED|FAILED", "checks": {"2.1": true/false/"N/A", ...}, "missing": ["缺失项描述"]}`, { label: 'Gate2出口检查' })

const parsed = JSON.parse(result.match(/\{[\s\S]*\}/)?.[0] || '{}')
if (parsed.verdict === 'PASSED') {
  log('✅ Gate 2 通过，可以进入 /gate-3-issues')
} else {
  log(`❌ Gate 2 不通过，缺失项: ${(parsed.missing || []).join(', ')}`)
  log('请修正 PRD 后重新 /gate-2-prd（不通过时可能需回 Gate 1 重新对齐）')
}
