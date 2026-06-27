export const meta = {
  name: 'gate-1-grill',
  description: 'Gate 1: 需求对齐 — 调用 /grill-me 全方位拷问，确认关键决策全覆盖',
  phases: [
    { title: '检查前置', detail: '验证 Gate A 已通过' },
    { title: '需求对齐', detail: '调用 /grill-me' },
    { title: '出口检查', detail: '逐条确认出口标准' },
  ],
}

phase('检查前置')

const gateStatePath = '.gate-state'
const fs = await agent(`Read ${gateStatePath}，提取 gate-1 状态和 project 字段`, { label: '读.gate-state' })

log(`当前项目: ${fs.match(/project:\s*"(.+)"/)?.[1] || '未知'}`)

phase('需求对齐')
log('启动 /grill-me 全方位拷问...')

await agent(`调用 /grill-me 技能对需求草案进行全方位拷问：
1. 扫描项目代码库，理解现有架构
2. 逐一提问关键决策点（技术选型、接口设计、范围边界）
3. 持续直到所有关键决策被覆盖（通常 20-80 个问题）
4. 每个问题给出推荐答案，由人确认

输入来自 Gate A 的需求草案（文件或当前会话上下文）。`, { label: 'grill-me对齐' })

phase('出口检查')

const result = await agent(`逐条检查 Gate 1 出口标准，只读 .gate-state 确认状态：

| # | 检查项 | 方法 |
|:-:|--------|------|
| 1.1 | 所有关键决策已覆盖 | 审查产出，无"待定"事项 |
| 1.2 | 分歧已消除 | 无未关闭的 question |
| 1.3 | 否决项已明确 | 明确说了"不做"的已记录 |

如果全部通过：将 .gate-state 中 gate-1 的 status 改为 "passed"。
如果不通过：输出缺失项清单，不修改 .gate-state。

输出 JSON: {"gate": "gate-1", "verdict": "PASSED|FAILED", "checks": {"1.1": true/false, "1.2": true/false, "1.3": true/false}, "missing": []}`, { label: 'Gate1出口检查' })

const parsed = JSON.parse(result.match(/\{[\s\S]*\}/)?.[0] || '{}')
if (parsed.verdict === 'PASSED') {
  log('✅ Gate 1 通过，可以进入 /gate-2-prd')
} else {
  log(`❌ Gate 1 不通过，缺失项: ${(parsed.missing || []).join(', ')}`)
  log('请修正后重新 /gate-1-grill')
}
