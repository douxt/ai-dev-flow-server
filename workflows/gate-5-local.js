export const meta = {
  name: 'gate-5-local',
  description: 'Gate 5: 本地环境准备 — 检查 git/claude/测试套件就绪',
  phases: [
    { title: '检查前置', detail: '验证 Gate 4 已 passed' },
    { title: '读取策略', detail: '读取 scheduling.strategy' },
    { title: '环境检查', detail: '检查本地开发环境' },
    { title: '出口检查', detail: '确认环境就绪' },
  ],
}

phase('检查前置')
await agent(`Read .gate-state，确认 gate-4.status === "passed"。
如果 gate-4 不是 passed，输出 "❌ Gate 4 未通过，请先执行 /gate-4-review" 并停止。`, { label: '检查前置Gate' })

phase('读取策略')
const strategyResult = await agent(`Read .devflow/config.yaml，提取 scheduling.strategy 字段。
如果字段不存在：
  - mode: frontend 或 mode: local → 返回 "local_session"
  - mode: backend 或 mode: server → 返回 "remote"
  - 无 mode 字段 → 返回 "remote"（保守）

输出 JSON: {"strategy": "local_session|local_ralph|remote", "source": "config|fallback"}`, { label: '读取调度策略' })

const strategy = JSON.parse(strategyResult.match(/\{[\s\S]*\}/)?.[0] || '{}')
if (strategy.strategy === 'remote') {
  log('⚠️ scheduling.strategy 为 remote，本 Gate 仅用于本地模式。')
  log('请改用 /gate-5-prep（远程环境准备）')
}

phase('环境检查')
log('检查本地开发环境...')

const envResult = await agent(`逐项检查本地开发环境：

| # | 检查项 | 方法 |
|:-:|--------|------|
| 5L.1 | git 工作区干净 | git status --short（无未提交改动） |
| 5L.2 | claude CLI 可用 | claude --version 正常 |
| 5L.3 | 测试套件可执行 | 检查 test_command 对应工具存在（如 npx playwright --version） |
| 5L.4 | issues/ 有 ready issue | grep -l "status: ready" issues/*.md |
| 5L.5 | gh CLI 可用 | gh auth status |
| 5L.6 | branch_prefix 已配置 | 从 config.yaml 读取 scheduling.branch_prefix（默认 ai/） |

全部通过输出 "COMPLETE"，否则列出缺失项。`, { label: '本地环境检查' })

if (!envResult.includes('COMPLETE')) {
  log(`❌ 本地环境不满足：${envResult}`)
}

phase('出口检查')
const allPassed = envResult.includes('COMPLETE') && strategy.strategy !== 'remote'

if (allPassed) {
  await agent(`将 .gate-state 中 gate-5 的 status 改为 "passed"。`, { label: '更新Gate5状态' })
  log('✅ Gate 5 通过，可以进入 /gate-6-local（本地调度执行）')
} else {
  log('❌ Gate 5 不通过，请修正后重新 /gate-5-local')
}
