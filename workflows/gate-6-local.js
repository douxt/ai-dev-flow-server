export const meta = {
  name: 'gate-6-local',
  description: 'Gate 6: 本地调度 — DAG 解析 → 串行派发 agent（单/双仓库 + wt/fallback）',
  phases: [
    { title: '检查前置', detail: '验证 Gate 5 已 passed' },
    { title: '读关联项目', detail: '从 config.yaml 读取 linked_projects' },
    { title: 'DAG解析', detail: '扫描 issues/ → 构建依赖图 → 拓扑排序' },
    { title: '执行调度', detail: '按 DAG 层级串行 + 逐 issue 派发 agent' },
    { title: '汇总', detail: '统计结果，更新 gate-6，引导 Gate 7' },
  ],
}

phase('检查前置')
await agent(`Read .gate-state，确认 gate-5.status === "passed"。
如果 gate-5 不是 passed，输出 "❌ Gate 5 未通过，请先执行 /gate-5-local" 并停止。`, { label: '检查前置Gate' })

phase('读关联项目')
const linkedResult = await agent(`Read .devflow/config.yaml，提取 linked_projects 数组（如存在）。
每项含 name/path/repo_url。不存在则返回空数组。

同时检查 wt 命令是否可用（which wt 2>/dev/null && echo "wt" || echo "git"）。

输出 JSON: {
  "linked_projects": [{"name": "...", "path": "...", "repo_url": "..."}],
  "dual_repo": true/false,
  "wt_available": true/false
}`, { label: '读关联项目' })

const linkInfo = JSON.parse(linkedResult.match(/\{[\s\S]*\}/)?.[0] || '{}')
const linkedRepos = linkInfo.linked_projects || []
const dualRepo = linkedRepos.length > 0
const useWt = linkInfo.wt_available

if (dualRepo) {
  log(`🔗 关联项目: ${linkedRepos.map(r => r.name).join(', ')} | 工具: ${useWt ? 'wt' : 'git worktree'}`)
}

// 构建双仓库工作流指令
const repoInstructions = dualRepo ? `
## 双仓库工作流（${useWt ? 'wt 工具' : 'git worktree 原生'}）

本 issue 涉及主仓库 + ${linkedRepos.length} 个关联项目：
${linkedRepos.map(r => `  - ${r.name}: ${r.path}`).join('\n')}

### 工作区创建
${useWt ? `\`\`\`bash
bash ~/bin/wt create top-down-issue-${'${issueId}'}
\`\`\`
（自动在 UMES3 和 ${linkedRepos.map(r => r.name).join('、')} 创建配对 worktree）` : `\`\`\`bash
# 主仓库
git worktree add .claude/worktrees/top-down-issue-${'${issueId}'} -b top-down-issue-${'${issueId}'}
${linkedRepos.map(r => `# ${r.name}
git -C ${r.path} worktree add .claude/worktrees/top-down-issue-${'${issueId}'} -b top-down-issue-${'${issueId}'}
`).join('')}\`\`\``}

### 提交
${useWt ? `\`\`\`bash
bash ~/bin/wt commit top-down-issue-${'${issueId}'} "feat: <说明>"
\`\`\`` : `\`\`\`bash
# 主仓库
git -C .claude/worktrees/top-down-issue-${'${issueId}'} add ... && git -C .claude/worktrees/top-down-issue-${'${issueId}'} commit -m "..."
${linkedRepos.map(r => `# ${r.name}
git -C ${r.path}/.claude/worktrees/top-down-issue-${'${issueId}'} add ... && git -C ${r.path}/.claude/worktrees/top-down-issue-${'${issueId}'} commit -m "..."
`).join('')}\`\`\``}

### 清理
${useWt ? `\`\`\`bash
bash ~/bin/wt cleanup top-down-issue-${'${issueId}'}
\`\`\`` : `\`\`\`bash
# 主仓库
git worktree remove .claude/worktrees/top-down-issue-${'${issueId}'} && git branch -D top-down-issue-${'${issueId}'}
${linkedRepos.map(r => `# ${r.name}
git -C ${r.path} worktree remove .claude/worktrees/top-down-issue-${'${issueId}'} && git -C ${r.path} branch -D top-down-issue-${'${issueId}'}
`).join('')}\`\`\``}

> 禁止直接 git commit，必须用 ${useWt ? 'wt commit' : 'git -C <worktree> commit'}。
` : '';

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

  log(`📦 Level ${level.level}: ${issueList.length} 个 issue 串行调度...`)

  for (const issue of issueList) {
    log(`  ▶ ${issue.id}: ${issue.file}`)

    const repoBlock = dualRepo ? repoInstructions.replace(/\$\{issueId\}/g, issue.id) : ''

    const raw = await agent(`在隔离 worktree 中实现以下 issue。

**Issue 文件**: ${issue.file}
**Issue ID**: ${issue.id}
${dualRepo ? `\n**仓库模式**: 双仓库（主仓库 + ${linkedRepos.map(r => r.name).join('、')}）` : ''}

## 步骤
1. 读取 issue 文件，理解全部 AC
2. TDD：先写测试，再实现
   - 严格只实现 AC 列出的内容，禁止扩范围、禁止顺手重构、禁止改无关文件
3. 每个逻辑模块独立 commit${dualRepo ? '（主仓库和关联项目分别提交）' : ''}
4. 执行 test_command 确认测试全绿
5. 门禁自检：
   - [ ] test_command 全量绿（旧测试+新测试，0 失败）
   - [ ] git diff --stat origin/master 文件清单与 Issue Scope 一致
   - [ ] 无 .bak 残留文件
6. push 分支到 origin：ai/${issue.id}-<简短描述>${dualRepo ? '（所有仓库均需 push）' : ''}
7. 更新 issue frontmatter：status: in_review，追加 branch: <分支名>
${dualRepo ? repoBlock : ''}
## 红线
- 只在 worktree 内修改，禁止碰 master/main
${dualRepo ? '- 关联项目在各自的 worktree 内修改，禁止直接改原始目录' : ''}
- 遇到阻塞立即报告，不猜测

## 完成信号
结束时输出：
\`\`\`
✅ Issue ${issue.id} 完成
改动文件: <清单>${dualRepo ? '\n关联项目改动: <清单>' : ''}
测试: <N passed, 0 failed>
分支: ai/${issue.id}-<描述>
\`\`\`

同时输出 JSON: {"status": "ok|fail", "branch": "ai/NNN-desc", "issue_id": "${issue.id}", "files_changed": [...], ${dualRepo ? '"linked_files_changed": [...], ' : ''}"tests_passed": N, "summary": "简述"}`, {
      isolation: 'worktree',
      label: `issue-${issue.id}`,
      phase: '执行调度',
    }).then(raw => {
      const json = JSON.parse((raw || '').match(/\{[\s\S]*\}/)?.[0] || '{}')
      return { issue_id: issue.id, ...json }
    }).catch(err => ({ issue_id: issue.id, status: 'error', branch: '', summary: err.message }))

    if (raw.status === 'ok') {
      doneBranches.push(raw)
      log(`    ✅ ${raw.branch} | ${raw.files_changed?.length || '?'} files | ${raw.tests_passed || '?'} tests`)
    } else {
      failCount++
      log(`    ❌ ${raw.summary || raw.status}`)
    }
  }
}

phase('汇总')
const branchList = doneBranches.map(b => `  - ${b.branch} (issue ${b.issue_id}) | ${b.files_changed?.length || '?'} files | ${b.tests_passed || '?'} tests`).join('\n')

await agent(`更新 gate-state：
- gate-6 的 status 改为 "passed"
- 汇总：${doneBranches.length} 个分支已 push / ${failCount} 个失败
${dualRepo ? `- 仓库模式: 双仓库（${linkedRepos.map(r => r.name).join('、')}），${useWt ? 'wt' : 'git worktree'} 管理` : ''}

同步更新 issue frontmatter：
- 已 push → status: in_review，追加 branch: <分支名>
- 失败 → status: failed

列出所有分支供 Gate 7 审查：
${branchList}

输出最终汇总。`, { label: '更新Gate6状态' })

if (dag.hitl_issues?.length) {
  log(`⚠️ ${dag.hitl_issues.length} 个 HITL issue 未处理：${dag.hitl_issues.join(', ')}`)
}
log(`✅ Gate 6: ${doneBranches.length} push, ${failCount} fail`)
log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
log('📋 Gate 7 人工审查（逐分支）：')
log('   1. git diff origin/main...origin/<分支> --stat 核对 Scope')
log('   2. 对照 AC 审查代码，确认测试真实性')
log('   3. 通过后手动 git merge --no-ff 到 main')
log('   4. issue status 改为 done')
if (dualRepo) {
  log('   5. 关联项目分支同样审查后合并')
  log(`   6. ${useWt ? 'wt cleanup <任务名>' : 'git worktree remove + git branch -D'} 清理`)
}
log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
