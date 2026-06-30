# Claude Code 全局规则（由 ai-dev-flow-server 安装）

## Worktree 强制（全平台，不可绕过）

所有代码开发必须在 git worktree 中隔离进行，**禁止在主仓库目录下直接编辑代码**。

| 规则 | 说明 |
|------|------|
| 创建 worktree | 修改代码前先 `git worktree add .claude/worktrees/<任务名> -b feat/<任务名>` |
| 禁止主分支编辑 | 禁止在 master/main 分支直接 Edit/Write |
| 禁止 `rm -rf` worktree | 用 `git worktree remove` 清理 |
| 禁止跨 worktree 复制 | 共享代码通过 git 对象库自然共享 |

## 代码修改安全

- 修改前备份：`cp file file.bak`
- 每完成一个逻辑改动立即提交，不攒批
- 永不 `git checkout -- <file>`，用 `git stash` 或 `.bak` 恢复
- 全局替换前先 grep 列清单确认范围

## Git 操作约束

- 禁止 `git push --force`
- 禁止 `git commit --amend` 在已推送分支
- 禁止直推 master/main 分支
- 所有代码变更走功能分支 → PR → 审查 → 合并

## Agent B 权限边界

Agent B（本地 Claude Code）的权限按仓库区分：

| 仓库类型 | 能干什么 | 不能干什么 |
|---------|---------|-----------|
| **业务项目**（openlobby 等） | commit、push、开 PR、**合并 PR 到 main**（人审后由 B 执行 merge） | 直推 main |
| **管线框架**（devflow-src） | 只能读 | **禁止 commit、禁止 push、禁止 merge** |
| **管线文件**（.devflow/、CLAUDE.md） | 只能读 | 修改需写 `_handoff/outbox/agent-b/` 委托 Agent A |

Agent B 在业务项目里拥有完整开发权限——写代码、开 PR、人审后**由 B 执行合并**。Agent B 在管线框架里是只读用户——要改管线配置就走 handoff 委托。

## 计划文件管理（防覆盖）

- 每次新计划创建新文件，文件名含日期+主题，禁止覆盖已有计划文件
- 计划执行完毕后，关键设计决策（权限边界、接口约束、架构取舍、被拒绝的方案）必须提取为 ADR
- ADR 存放：项目有 `docs/decisions/` 则写项目，否则写 `~/.claude/plans/decisions/`
- 旧计划文件保留不删；计划只存执行步骤，不可变决策回流正式文档

### ADR 格式

```markdown
# ADR-NNN: <标题>
## 状态：已采纳 / 已废弃
## 日期：YYYY-MM-DD
## 背景
## 决策
## 后果
## 拒绝的方案
```
