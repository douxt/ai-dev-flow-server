export const meta = {
  name: 'gate-5-prep',
  description: 'Gate 5: 环境准备 — 检查 .devflow/ 完整性 + config.yaml 有效 + dispatch.timer 已激活',
  phases: [
    { title: '检查前置', detail: '验证 Gate 4 已 passed' },
    { title: '环境检查', detail: '检查 .devflow/ 目录完整' },
    { title: '配置验证', detail: '验证 config.yaml 有效' },
    { title: 'Timer 确认', detail: '确认 dispatch.timer 已激活' },
    { title: 'Inbox 检查', detail: '检查 _handoff/inbox/agent-b/ 有无 A 回复' },
  ],
}

phase('检查前置')
await agent(`Read .gate-state，确认 gate-4.status === "passed"。
如果 gate-4 不是 passed，输出 "❌ Gate 4 未通过，请先执行 /gate-4-review" 并停止。`, { label: '检查前置Gate' })

phase('环境检查')
log('检查 .devflow/ 目录完整性...')

const envCheck = await agent(`逐项检查 .devflow/ 目录结构：

| # | 检查项 | 路径 |
|:-:|--------|------|
| 5.1a | config.yaml 存在 | .devflow/config.yaml |
| 5.1b | archon/ 目录存在 | .devflow/archon/ |
| 5.1c | dispatch.sh 存在 | .devflow/archon/dispatch.sh |
| 5.1d | auto-execute-afk.yaml 存在 | .devflow/archon/auto-execute-afk.yaml |
| 5.1e | scripts/ 目录存在 | .devflow/scripts/ |
| 5.1f | check_constitution.py 存在 | .devflow/scripts/check_constitution.py |
| 5.1g | knowledge/ 目录存在 | .devflow/knowledge/ |

列出缺失项，全部存在输出 "COMPLETE"。`, { label: '目录完整性检查' })

if (!envCheck.includes('COMPLETE')) {
  log(`❌ .devflow/ 不完整，缺失：${envCheck}`)
  log('请重新运行 install.sh 或手动补全缺失文件')
}

phase('配置验证')
log('验证 config.yaml 有效性...')

const configCheck = await agent(`Read .devflow/config.yaml，检查以下必填字段是否存在且非空：

- project.name
- project.repo_url
- project.workspace
- tech_stack.language
- tech_stack.test_command
- dispatch.branch_prefix
- notify.telegram_chat_id
- notify.telegram_bot_token

输出 JSON: {"valid": true/false, "missing_fields": [...], "errors": [...]}`, { label: 'config.yaml验证' })

const configParsed = JSON.parse(configCheck.match(/\{[\s\S]*\}/)?.[0] || '{}')
if (!configParsed.valid) {
  log(`❌ config.yaml 无效，缺失字段: ${(configParsed.missing_fields || []).join(', ')}`)
  if (configParsed.errors?.length) {
    log(`错误: ${configParsed.errors.join('; ')}`)
  }
}

phase('Timer 确认')
log('检查 dispatch.timer 状态...')

const timerResult = await agent(`检查 AFK 调度 timer 状态。

执行（或模拟检查）：
1. systemctl is-active dispatch-*.timer 2>/dev/null || echo "NOT_ACTIVE"
2. systemctl is-enabled dispatch-*.timer 2>/dev/null || echo "NOT_ENABLED"
3. systemctl is-active reconcile-*.timer 2>/dev/null || echo "NOT_ACTIVE"

输出 JSON: {"dispatch_active": true/false, "dispatch_enabled": true/false, "reconcile_active": true/false}`, { label: 'Timer状态检查' })

const timerParsed = JSON.parse(timerResult.match(/\{[\s\S]*\}/)?.[0] || '{}')

phase('Inbox 检查')
log('检查 _handoff/inbox/agent-b/ 有无 A 的回复...')

const inboxCheck = await agent(`执行 git pull --rebase 同步远端，然后检查 _handoff/inbox/agent-b/ 目录。
列出所有 .md 文件（如果有），输出每个文件的 status（done/rejected）。
如果目录为空或无文件，输出 "EMPTY"。

对于 status: done 的消息：
- 验证 A 的操作结果是否满足原委托要求
- 满足 → 将原委托消息和此回复一起 mv 到 _handoff/archive/
- 不满足 → 写新消息到 outbox/agent-b/ 说明哪里不满足

输出处理结果: "EMPTY" | "PROCESSED: <N> 条回复已验证并归档"`, { label: 'Inbox检查' })

log(inboxCheck)

const allPassed = envCheck.includes('COMPLETE') && configParsed.valid && timerParsed.dispatch_active

if (allPassed) {
  await agent(`将 .gate-state 中 gate-5 的 status 改为 "passed"。`, { label: '更新Gate5状态' })
  log('✅ Gate 5 通过，可以进入 /gate-6-afk')
} else {
  const issues = []
  if (!envCheck.includes('COMPLETE')) issues.push('.devflow/ 不完整')
  if (!configParsed.valid) issues.push('config.yaml 无效')
  if (!timerParsed.dispatch_active) issues.push('dispatch.timer 未激活')
  log(`❌ Gate 5 不通过: ${issues.join(', ')}`)
  log('请修正后重新 /gate-5-prep')
}
