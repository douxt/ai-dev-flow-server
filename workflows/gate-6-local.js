export const meta = {
  name: 'gate-6-local',
  description: 'Gate 6: 本地调度 — DAG 解析 → CC 会话并行 fan-out → 状态追踪',
  phases: [
    { title: '检查前置', detail: '验证 Gate 5 已 passed' },
    { title: 'DAG解析', detail: '扫描 issues/ → 构建依赖图 → 拓扑排序' },
    { title: '执行调度', detail: '按 DAG 层级并行派发 agent（worktree 隔离）' },
    { title: '汇总', detail: '统计结果，更新 gate-6 状态' },
  ],
}

phase('检查前置')
await agent(`Read .gate-state，确认 gate-5.status === "passed"。
如果 gate-5 不是 passed，输出 "❌ Gate 5 未通过，请先执行 /gate-5-local" 并停止。`, { label: '检查前置Gate' })

phase('DAG解析')
log('扫描 issues/ → 解析 blocked_by → 构建依赖 DAG...')

const dagResult = await agent(`扫描 issues/ 目录下所有 .md 文件，提取 frontmatter 中的 status、type、blocked_by。

规则：
1. 只处理 status: ready 且 type: AFK 的 issue
2. 跳过 type: HITL 的 issue（列清单提示用户手动处理）
3. 解析每个 issue 的 blocked_by 列表
4. 构建依赖 DAG，用 Kahn 算法拓扑排序
5. 检测循环依赖，有循环则报告并停止
6. 按层级分组：level 0 = 无依赖，level N = 依赖全部在前 N-1 层

输出 JSON:
{
  "hitl_issues": ["###-xxx", ...],
  "levels": [
    {"level": 0, "issues": [{"id": "001", "file": "issues/001-xxx.md", "blocked_by": []}]},
    {"level": 1, "issues": [{"id": "003", "file": "issues/003-yyy.md", "blocked_by": ["001"]}]}
  ],
  "total_afk": N,
  "cyclic": []
}`, { label: 'DAG解析' })

const dag = JSON.parse(dagResult.match(/\{[\s\S]*\}/)?.[0] || '{}')
if (!dag.levels || dag.levels.length === 0) {
  if (dag.hitl_issues?.length) {
    log(`⚠️ 没有 AFK ready issue。${dag.hitl_issues.length} 个 HITL issue 需手动处理：${dag.hitl_issues.join(', ')}`)
  } else {
    log('⚠️ 没有 ready issue，调度跳过。')
  }
}

phase('执行调度')
const allResults = []
let failedCount = 0

for (const level of (dag.levels || [])) {
  const issueList = level.issues || []
  if (issueList.length === 0) continue

  log(`📦 Level ${level.level}: ${issueList.length} 个 issue 并行调度中...`)

  const levelResults = await parallel(
    issueList.map(issue => () =>
      agent(`你是软件工程师。请实现以下 issue：

**Issue 文件**: ${issue.file}
**Issue ID**: ${issue.id}

## 要求
1. 读取 issue 文件，理解全部 AC
2. TDD：先写测试，再实现
3. 严格只实现 AC 列出的内容，禁止扩范围、禁止顺手重构
4. 每个逻辑模块独立 git commit
5. 实现完成后验证：测试全绿、AC 全部满足
6. 完成时更新 issue 文件 frontmatter 的 status 为 done

## 约束
- 使用 git worktree 隔离开发（已自动配置）
- 不修改 issue 文件本身（除了 status 字段）
- 遇到阻塞问题立即报告，不自行猜测`, {
        isolation: 'worktree',
        label: `issue-${issue.id}`,
        phase: '执行调度',
      }).then(result => ({ issue_id: issue.id, result }))
      .catch(err => ({ issue_id: issue.id, result: `ERROR: ${err.message}` }))
    )
  )

  for (const r of levelResults.filter(Boolean)) {
    allResults.push(r)
    if (r.result?.includes('ERROR') || r.result?.includes('FAIL')) failedCount++
    log(`  ${r.issue_id}: ${r.result?.includes('ERROR') ? '❌ 失败' : '✅ 完成'}`)
  }
}

phase('汇总')
const doneCount = allResults.length - failedCount
log(`调度完成：${doneCount} 成功 / ${failedCount} 失败 / ${dag.total_afk || 0} 总计`)

if (dag.hitl_issues?.length) {
  log(`⚠️ ${dag.hitl_issues.length} 个 HITL issue 未处理：${dag.hitl_issues.join(', ')}`)
  log('请手动在 CC 交互会话中逐个实现 HITL issue。')
}

await agent(`更新 gate-state：
- 将 gate-6 的 status 改为 "passed"
- 记录调度结果：${doneCount} done, ${failedCount} failed

输出最终汇总。`, { label: '更新Gate6状态' })

if (failedCount > 0) {
  log(`❌ ${failedCount} 个 issue 失败，请检查日志后手动处理或重试。`)
}
log('✅ Gate 6 本地调度完成，进入 Gate 7 人工审查。')
