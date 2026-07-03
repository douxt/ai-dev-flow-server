export const meta = {
  name: 'gate-6-local',
  description: 'Gate 6: 本地调度 — DAG 解析 → CC 会话并行 fan-out → 验证合并',
  phases: [
    { title: '检查前置', detail: '验证 Gate 5 已 passed' },
    { title: 'DAG解析', detail: '扫描 issues/ → 构建依赖图 → 拓扑排序' },
    { title: '执行调度', detail: '按 DAG 层级并行派发 agent（worktree 隔离）' },
    { title: '验证合并', detail: '验证每个分支测试通过 → 合并到 master' },
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
const doneBranches = []
let failCount = 0

for (const level of (dag.levels || [])) {
  const issueList = level.issues || []
  if (issueList.length === 0) continue

  log(`📦 Level ${level.level}: ${issueList.length} 个 issue 并行调度...`)

  const levelResults = await parallel(
    issueList.map(issue => () =>
      agent(`在隔离 worktree 中实现以下 issue。

**Issue 文件**: ${issue.file}
**Issue ID**: ${issue.id}

## 步骤
1. 读取 issue 文件，理解全部 AC
2. TDD：先写测试，再实现（严格只实现 AC，禁止扩范围、顺手重构）
3. 每个逻辑模块独立 git commit
4. 执行 test_command 确认测试全绿
5. push 分支到 origin：ai/${issue.id}-<简短描述>
6. 更新 issue frontmatter：status: in_review，记录分支名

## 红线
- 只在 worktree 内修改，禁止碰 master/main
- 遇到阻塞立即报告，不猜测

输出 JSON: {"status": "ok|fail", "branch": "ai/NNN-desc", "issue_id": "${issue.id}", "summary": "简述"}`, {
        isolation: 'worktree',
        label: `issue-${issue.id}`,
        phase: '执行调度',
      }).then(raw => {
        const json = JSON.parse((raw || '').match(/\{[\s\S]*\}/)?.[0] || '{}')
        return { issue_id: issue.id, ...json }
      }).catch(err => ({ issue_id: issue.id, status: 'error', branch: '', summary: err.message }))
    )
  )

  for (const r of levelResults.filter(Boolean)) {
    if (r.status === 'ok') {
      doneBranches.push(r)
      log(`  ${r.issue_id}: ✅ ${r.branch}`)
    } else {
      failCount++
      log(`  ${r.issue_id}: ❌ ${r.summary || r.status}`)
    }
  }
}

phase('验证合并')
log('逐个验证分支测试结果，通过后合并...')

let mergeFails = 0
for (const b of doneBranches) {
  const mergeResult = await agent(`合并分支 ${b.branch}（issue ${b.issue_id}）：

1. git fetch origin ${b.branch}
2. git diff origin/master...origin/${b.branch} --stat 确认改动量合理
3. 从 config.yaml 读取 test_command，运行测试
4. 全部通过 → git merge origin/${b.branch} --no-ff && git push origin master
5. 失败 → 报告原因，不合并

输出: {"branch": "${b.branch}", "merged": true/false, "reason": "..."}`, {
    label: `合并-${b.issue_id}`,
    phase: '验证合并',
  })

  const m = JSON.parse((mergeResult || '').match(/\{[\s\S]*\}/)?.[0] || '{}')
  if (m.merged) {
    log(`  ✅ ${b.issue_id} 已合并到 master`)
  } else {
    mergeFails++
    log(`  ❌ ${b.issue_id} 合并失败: ${m.reason || '未知'}`)
  }
}

phase('汇总')
const okCount = doneBranches.length - mergeFails
await agent(`更新 gate-state：
- gate-6 的 status 改为 "passed"
- 汇总：${doneBranches.length} push / ${okCount} merge / ${failCount + mergeFails} fail

同步更新 issue frontmatter：
- 已合并 → status: done
- 已 push 未合并 → status: in_review（进入 Gate 7 人工审查）
- 失败 → status: failed

输出最终汇总。`, { label: '更新Gate6状态' })

if (dag.hitl_issues?.length) {
  log(`⚠️ ${dag.hitl_issues.length} 个 HITL issue 未处理：${dag.hitl_issues.join(', ')}`)
}
log(`✅ Gate 6: ${doneBranches.length} push, ${okCount} merge, ${failCount + mergeFails} fail → Gate 7`)
