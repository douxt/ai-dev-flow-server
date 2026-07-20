# Claude Code 全局规则（由 ai-dev-flow-server 安装）

## Worktree 强制（全平台，不可绕过）

所有代码开发必须在 git worktree 中隔离，**禁止在主仓库目录下直接编辑代码**。
统一使用 `wt` 工具管理，禁止直接调用 `git worktree add/remove`。

| 操作 | 命令 |
|------|------|
| 创建 | `wt create <任务名>` |
| 清理 | `wt cleanup <任务名>` |
| 提交 | `wt commit <任务名> "消息"` |

| 禁止 | 正确做法 |
|------|---------|
| `git worktree add` | 用 `wt create` |
| `git worktree remove` / `rm -rf` worktree | 用 `wt cleanup` |
| 跨 worktree 复制文件 | 通过 git 共享 |

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
