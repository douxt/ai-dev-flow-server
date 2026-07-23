# Claude Code 全局规则（由 ai-dev-flow-server 安装）

## 工作流自动路由

⚠️ 处理任何开发任务前，必须先做工作流评估。禁止跳过评估直接编码。

### 评估三问

1. **上下文窗口装得下吗？**
   否 → /wayfinder（~5%，决策树或预期 token 超过窗口容量）

2. **单会话 — 有现有文档（CONTEXT.md / spec / ADR）可直接 grill 吗？**
   无 → 先进 Plan Mode 出初稿 → 再判断

3. **初稿/现有文档基础上有雾吗？**
   有雾 → /grill-with-docs（基于文档对话澄清）
   无雾 → 直接 /to-spec
   简单改动？→ 直接 /implement

### 路由表

```
单会话？
  ├── 有现有文档（CONTEXT.md / spec / ADR）？
  │   ├── 有 → /grill-with-docs → /to-spec → /to-tickets → /implement
  │   └── 无 → 先进 Plan Mode 出初稿
  │         ├── 初稿有雾 → /grill-with-docs（基于初稿）→ /to-spec → ...
  │         └── 初稿清晰 → 直接 /to-spec → /to-tickets → /implement
  │
  └── 否（~5%，一个窗口装不下）→ /wayfinder
        └── 地图清晰后 → /to-spec → /to-tickets → /implement
```

| 任务特征 | 占比 | 推荐路径 |
|---------|:---:|---------|
| 简单改动（单文件、命名、小 bug） | 30% | 直接 /implement |
| 无现有文档，先进 Plan Mode 出初稿 | 35% | **Plan Mode → /grill-with-docs → /to-spec → /to-tickets → /implement** ⬅ 默认 |
| 有现有文档，直接 grill | 20% | /grill-with-docs → /to-spec → /to-tickets → /implement |
| 需求明确、无雾、能直接写 spec | 10% | /to-spec → /to-tickets → /implement |
| 多会话大型（一个窗口装不下） | 5% | /wayfinder → /to-spec → /to-tickets → /implement |
| 已有代码逆向规格 | 按需 | /to-spec（逆向）→ /to-tickets → /implement |

### 评估输出格式

收到任务后，先输出：
```
📋 建议路径：[...]
原因：[...]
是否按此执行？（回复 y 开始，或指定其他路径）
```

## 五大命令

| 命令 | 用途 | 适用场景 |
|------|------|---------|
| `/grill-with-docs` | 基于文档对话澄清需求 | **默认入口**，~95% 的任务 |
| `/to-spec` | 需求 → 规格（可逆向） | grill 之后，或需求已明确 |
| `/to-tickets` | 规格 → 工单拆分 | spec 之后，每工单 ≤ 上下文 40% |
| `/implement` | 工单 → 代码 + 内建审查 | ticket 就绪后 |
| `/code-review` | 独立子代理审查全部 diff | implement 之后，PR 之前 |

### /wayfinder（仅 ~5% 的任务，上下文窗口装不下时）

> 规划 skill，不做实现。在 issue tracker 上建立决策地图，按决策拆 ticket，跨多会话逐个击破。

| ✅ 该用 | ❌ 不该用 |
|---------|----------|
| 任务超过一个上下文窗口 | 单 session 能搞定 |
| 到达目的地的路线不清晰（"有雾"） | 能直接写 spec（无雾） |
| 决策之间有依赖链 | 纯编码，不需要决策 |
| 跨多天/多 session 的调研 | 简单改动、bug 修复 |

**判断标准**："我现在能直接写 spec 吗？" 能 → 不走 wayfinder。不能 → wayfinder 先清雾。

### 上下文预算

/to-tickets 拆分时，每个 ticket 内容不超过上下文窗口的 40%（~48K token），确保 agent 在智能区内工作。

## 引导词

- **先想清楚再做**：收到任务先评估路径，不直接改代码
- **垂直切片**：每次交付完整的功能切片，不只是代码片段
- **假设可证伪**：所有假设写下后立刻找反例，不等到审查阶段
- **证据不声称**：说"改了 X"必须附带 diff/测试结果，不接受口头声明
- **不扩范围**：只做 ticket 要求的事，发现相关问题 → 新开 ticket
- **每个 Bug 都是永久升级**：修复后必须追加测试用例 + 更新 CLAUDE.md 规则

## 模型路由建议

| 任务类型 | 推荐模型 |
|---------|---------|
| 规划、架构决策、复杂需求分析 | Opus |
| 日常实现、审查、重构 | Sonnet |
| 批量文件操作（重命名、格式转换） | Haiku |
| 生产代码 | **禁止** Haiku |

## 安全红线

以下类型的改动必须人工逐行审查，**禁止自动合并**：
- `auth` — 认证/授权逻辑
- `payment` — 支付/计费逻辑
- `crypto` — 加密/签名/密钥处理
- `delete` — 数据删除/销毁操作
- `permission` — 权限边界变更

ticket 含上述标记时，check_constitution.py 自动标记 `⚠️ HUMAN_REVIEW_REQUIRED`。

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
