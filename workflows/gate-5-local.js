export const meta = {
  name: 'gate-5-local',
  description: 'Gate 5: 本地环境准备 — 检查 git/claude/测试套件 + 关联项目 + wt 可用性',
  phases: [
    { title: '检查前置', detail: '验证 Gate 4 已 passed' },
    { title: '读取策略', detail: '读取 scheduling.strategy + linked_projects' },
    { title: '环境检查', detail: '检查本地开发环境 + wt/fallback' },
    { title: '出口检查', detail: '确认环境就绪' },
  ],
}

phase('检查前置')
await agent(`Read .gate-state，确认 gate-4.status === "passed"。
如果 gate-4 不是 passed，输出 "❌ Gate 4 未通过，请先执行 /gate-4-review" 并停止。`, { label: '检查前置Gate' })

phase('读取策略')
const configResult = await agent(`Read .devflow/config.yaml，提取以下字段：

1. scheduling.strategy（不存在则按 mode: frontend→local_session, backend→remote fallback）
2. linked_projects 数组（如存在），每项含 name/path/repo_url

输出 JSON: {
  "strategy": "local_session|remote",
  "source": "config|fallback",
  "linked_projects": [{"name": "fa56-php", "path": "/home/dou/projects/fa56-php", "repo_url": "git@github.com:douxt/fa56-php.git"}]
}`, { label: '读取配置' })

const config = JSON.parse(configResult.match(/\{[\s\S]*\}/)?.[0] || '{}')
if (config.strategy === 'remote') {
  log('⚠️ scheduling.strategy 为 remote，本 Gate 仅用于本地模式。')
  log('请改用 /gate-5-prep（远程环境准备）')
}

phase('环境检查')
log('检查本地开发环境...')

const linkedRepos = config.linked_projects || []
const dualRepo = linkedRepos.length > 0
if (dualRepo) {
  log(`🔗 检测到关联项目: ${linkedRepos.map(r => r.name).join(', ')}`)
}

const envResult = await agent(`逐项检查本地开发环境：

| # | 检查项 | 方法 |
|:-:|--------|------|
| 5L.1 | git 工作区干净 | 主仓库 git status --short（无未提交改动） |
| 5L.2 | claude CLI 可用 | claude --version 正常 |
| 5L.3 | 测试套件可执行 | test_command 对应工具存在 |
| 5L.4 | issues/ 有 ready issue | grep -l "status: ready" issues/*.md |
| 5L.5 | gh CLI 可用 | gh auth status |
| 5L.6 | branch_prefix 已配置 | config.yaml 的 scheduling.branch_prefix（默认 ai/） |
${dualRepo ? `| 5L.7 | wt 工具可用 | which wt（不可用则确认 git worktree 可用作 fallback） |
| 5L.8 | 关联项目可访问 | 逐项 ls ${linkedRepos.map(r => r.path).join(' ')} |` : ''}

全部通过输出 "COMPLETE"，否则列出缺失项。
同时输出 JSON: {"complete": true/false, "dual_repo": ${dualRepo}, "wt_available": true/false, "missing": [...]}`, { label: '本地环境检查' })

const envParsed = JSON.parse(envResult.match(/\{[\s\S]*\}/)?.[0] || '{}')
if (!envParsed.complete) {
  log(`❌ 本地环境不满足：${(envParsed.missing || []).join(', ')}`)
}
if (dualRepo && !envParsed.wt_available) {
  log('⚠️ wt 不可用，将使用 git worktree 原生命令兜底')
}

phase('出口检查')
const allPassed = envParsed.complete && config.strategy !== 'remote'

if (allPassed) {
  await agent(`将 .gate-state 中 gate-5 的 status 改为 "passed"。
记录：dual_repo=${dualRepo}, wt=${envParsed.wt_available}`, { label: '更新Gate5状态' })
  log('✅ Gate 5 通过，可以进入 /gate-6-local（本地调度执行）')
} else {
  log('❌ Gate 5 不通过，请修正后重新 /gate-5-local')
}
