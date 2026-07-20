# 全局 CLAUDE.md 精简版预览

> 基于 P1-P11 诊断决策生成。以 `config-templates/default/CLAUDE.md`（45 行）为安全骨架，叠加个人工作流层。
> 目标：80-100 行 / ≤30 条 actionable bullet。
> 此文件仅供审阅，未覆盖原 `~/.claude/CLAUDE.md`。

---

# 全局强制规则

- 全程简洁中文，无寒暄、无客套、无多余开场与结尾。
- 不复述需求、不重复上下文，回答直击重点，杜绝冗余。
- 代码精简干净，仅复杂逻辑加必要注释，常规逻辑不写注释。
- 严格限定修改范围，不擅自扩范围、不私自重构、不额外加功能。
- 关键逻辑存在疑问时主动确认；细节不明确时按最小改动原则，不擅自脑补。

## 代码修改安全

- 修改前备份：`cp file file.bak`
- 每完成一个逻辑改动立即提交，不攒批
- 永不 `git checkout -- <file>`，用 `git stash` 或 `.bak` 恢复
- 全局替换前先 `grep -n` 列清单确认范围

## Worktree 隔离

所有代码开发在 git worktree 中隔离，**禁止在主仓库目录下直接编辑**。
统一使用 `wt` 工具管理，禁止直接调用 `git worktree add/remove`。
制定任何代码改动计划时，**计划首步必须包含 `wt create <任务名>`**（文档/配置修改豁免）。

| 操作 | 命令 |
|------|------|
| 创建 | `wt create <任务名>` |
| 清理 | `wt cleanup <任务名>` |
| 提交 | `wt commit <任务名> "消息"` |
| 开发环境 | `wt dev [任务名]` / `wt dev-stop [任务名]` |

| 禁止 | 原因 |
|------|------|
| `git worktree add` | 用 `wt create` 代替 |
| `git worktree remove` / `rm -rf` worktree | 用 `wt cleanup` 代替 |
| 主分支直接编辑 | 禁止在 master/main 直接 Edit/Write |
| 存在未合并 worktree 时新建 | 先合并或清理已有 worktree，再创建新的 |
| `cd <path> && git` | 用 `git -C <path> <command>` |
| `git push --force` | — |
| 直推 master/main | 所有变更走功能分支 |

基准分支默认 `origin/master`。
完整工作流（合并步骤、wt 命令参考、多仓库 fallback）见 `docs/references/worktree-workflow.md`。

## 操作边界

- 只做用户要求的事，不擅自扩范围、不私自重构
- 不确定时主动确认，不猜测
- 修改已有代码前先进 Plan Mode 出变更方案，确认后执行
- Plan Mode 中必须先对照项目审查清单逐条过再出方案（清单在项目 `.claude/gate-checklists/`）

## 文件写入防御

- 禁止绕过 file-guard / bash-firewall 拦截
- ⚠️ 子代理不继承 PreToolUse 钩子，file-guard 和 bash-firewall 在其中不生效；唯一约束手段是 audit-log 事后审计
- 违规操作被 audit-log 记录（`~/.claude/logs/file-audit.jsonl`）

## 工具使用

- 搜索/网页抓取：优先内置 `WebSearch` 和 `WebFetch`，多次失效后 fallback 到 `tavily_search`、`tavily_extract`、`web_search_exa`

## 踩坑自省

- 遇到报错、回退、字段猜错等，先搜索网络最佳实践，再记录到项目 `memory/` 目录
- 格式：根因 → 解决方法 → 如何预防
- 同步更新 `MEMORY.md` 索引
- 踩坑后更新对应审查清单，不重复犯错
- 注意：不同 worktree 路径下 `~/.claude/projects/` 记忆会分裂，关键决策必须写项目 `memory/` 确保跨 worktree 可查

## CodeGraph

在索引了 CodeGraph 的仓库中，查找代码优先用 `codegraph_explore`（MCP 工具）或 `codegraph explore`（Shell），代替 grep/Read 循环。未初始化则跳过。

## 计划文件管理

- 每次新计划新文件，文件名含日期+主题
- 执行完毕后关键设计决策提取为 ADR 存入 `docs/decisions/`
- 旧计划文件保留不删，不可变决策回流正式文档
- ADR 格式模板见 `docs/decisions/` 中已有文件

## @import / 路径引用

- `@RTK.md` — CLI token 优化代理用法
- 完整 Worktree 流程 → `docs/references/worktree-workflow.md`
- CodeGraph 详表 → `docs/references/codegraph-guide.md`
