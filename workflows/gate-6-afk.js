export const meta = {
  name: 'gate-6-afk',
  description: 'Gate 6: AFK 就绪确认 — 验证 dispatch 管线就绪，ready issue 将由 timer 自动消化',
  phases: [
    { title: '检查前置', detail: '验证 Gate 5 已 passed' },
    { title: '管线检查', detail: '验证 AFK 管线各环节就绪' },
    { title: '就绪确认', detail: '列出 ready issue，确认自动消化' },
  ],
}

phase('检查前置')
await agent(`Read .gate-state，确认 gate-5.status === "passed"。
如果 gate-5 不是 passed，输出 "❌ Gate 5 未通过，请先执行 /gate-5-prep" 并停止。`, { label: '检查前置Gate' })

phase('管线检查')
log('验证 AFK 管线各环节...')

const pipelineCheck = await agent(`逐项检查 AFK 管线就绪状态：

| # | 检查项 | 方法 |
|:-:|--------|------|
| 6.1 | dispatch.timer active | systemctl is-active dispatch-*.timer |
| 6.2 | reconcile.timer active | systemctl is-active reconcile-*.timer |
| 6.3 | gh CLI 可用且已认证 | gh auth status 2>&1 |
| 6.4 | git 可用 | git --version |
| 6.5 | Python 3 可用 | python3 --version |
| 6.6 | Archon 可用 | which archon 或 archon --version 2>&1 |
| 6.7 | check_constitution.py 可执行 | python3 .devflow/scripts/check_constitution.py --help 2>&1 |

输出 JSON: {"all_ready": true/false, "checks": {"6.1": true/false, ...}, "errors": [...]}`, { label: 'AFK管线检查' })

const pipelineParsed = JSON.parse(pipelineCheck.match(/\{[\s\S]*\}/)?.[0] || '{}')

phase('就绪确认')
log('扫描 ready issue，确认自动消化就绪...')

const result = await agent(`扫描 issues/ 目录，列出所有 status: ready 的 issue。

然后输出以下确认信息：

**AFK 管线就绪确认：**

1. dispatch.timer 每 ${5} 分钟扫描一次 issues/
2. 发现 ready issue → check_constitution.py 7 项机器检查
3. 通过 → 原子抢占（ready → in_progress）
4. Archon 7 节点工作流：implement → validate → review → PR
5. PR 创建后 → notify.py Telegram 通知审批

**当前就绪的 issue：**
（列出所有 ready issue 的 ID 和标题）

**如果当前无 ready issue：**
- 提示人将 issue 从 backlog 拖到 ready（修改 frontmatter status: ready）
- dispatch.timer 下次扫描时会自动消化

如果管线检查全部通过且人确认理解流程：将 .gate-state 中 gate-6 的 status 改为 "passed"。

输出 JSON: {"gate": "gate-6", "verdict": "PASSED|PENDING", "ready_count": N, "ready_issues": ["#N title", ...], "pipeline_ready": true/false}`, { label: 'Gate6就绪确认' })

const parsed = JSON.parse(result.match(/\{[\s\S]*\}/)?.[0] || '{}')
if (parsed.verdict === 'PASSED') {
  log('✅ Gate 6 通过！AFK 管线已就绪，ready issue 将由 dispatch.timer 自动消化。')
  log(`当前 ${parsed.ready_count || 0} 个 ready issue 等待消化。`)
  log('下一步：Gate 7 人工审查（PR 创建后在 Telegram 审批）')
} else {
  log('⚠️ AFK 管线未完全就绪，请检查上述检查项')
  if (!pipelineParsed.all_ready) {
    log(`管线问题: ${(pipelineParsed.errors || []).join(', ')}`)
  }
}
