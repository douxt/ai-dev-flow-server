---
name: devflow
description: DevFlow — 移动端 AI 开发全流程管理系统
author: Claude Code
created: 2026-06-23
status: draft
---

# DevFlow — 移动端 AI 开发全流程管理系统 PRD

## Problem Statement

当前的 AI 辅助开发存在三个断裂：

1. **人机协作断在终端**。Grill、PRD 生成、Issue 拆分等对齐阶段依赖 Claude Code CLI 终端操作，离开电脑无法推进。手机端语音输入在深度对话场景中体验更优，但缺乏适配移动端的聊天界面。

2. **任务流转依赖手工**。Issue 从确认到执行需要人工运行 `ralph-dispatcher.sh`，审批需要手动改 YAML frontmatter。没有统一的看板界面来管理任务状态和审批流转。

3. **开发流程难以固化**。14 条 Issue 质量宪法、12 条脚本宪法和 TDD 流程依赖人的自觉执行，缺乏框架级的约束。简单任务和复杂任务走同一套流程，缺少灵活的轻重分流机制。

## Solution

**DevFlow** — 一套轻量云服务器上运行的 AI 开发全流程管理系统。人通过手机浏览器完成从需求对齐到代码审批的全部操作，后台自动消费已确认的 Issue 并派发给 Claude Code 执行。

### 核心指标

| 目标 | 指标 |
|------|------|
| 全流程覆盖 | 聊天对齐 → PRD → Issue → 审批 → 自动执行 → PR 审查，一个系统完成 |
| 移动优先 | 手机浏览器即可操作全部流程 |
| 零手动派发 | Issue 标 ready 后秒级自动派发，无需人工操作 |
| 宪法约束 | 14 条 Issue 宪法 + 12 条脚本宪法框架级自动检查 |
| 轻重分流 | 简单改动一句话直接执行，复杂任务走完整流程 |

### 架构

```
手机浏览器
  ├─ OpenLobby     (:3001)  ← 前段：多会话 CC 聊天/grill/PRD/issues
  ├─ 审批看板       (:8421)  ← 中段：全局 Kanban + 状态管理 + 审批
  └─ Archon Web UI  (:8420)  ← 后段：执行监控

轻量云服务器 (1C 2GB)
  ├─ OpenLobby         ← CC 多会话管理（SQLite 持久化）
  ├─ 审批看板           ← FastAPI + htmx，自建 ~380 行
  ├─ Archon serve      ← YAML workflow 引擎，替代 ralph
  ├─ dispatch.sh       ← cron 5min + 即时触发，flock 防并发
  ├─ reconciler        ← 每 5 分钟同步 Archon 实际状态到 issue 文件
  ├─ Telegram bot      ← 审批通知推送（到达审批门 → 手机弹消息）
  └─ cc-stack (:3457)  ← 模型路由（haiku→DeepSeek Flash, sonnet→V4 Pro, opus→Qwen3.7-Max）
```

Archon workflow 分为前后两段，独立定义、独立触发：

- **align**（人驱动）：grill → PRD → to-issues → 宪法检查 → 人审批 → `status: ready`
- **execute**（机器驱动）：TDD 实现 → 自动验证 → AI 审查 → 人审批 → PR → `status: done`

前后段通过 issue 文件的 YAML frontmatter 契约解耦。前段产出符合格式的 issue，后段消费并执行。前段可替换为其他 Agent，只要产出格式一致即可。

## User Stories

### 聊天对齐

1. As a 开发者, I want 在手机上通过聊天与 Claude Code 进行需求对齐 (grill), so that 我不必坐在电脑前就能推进项目。
2. As a 开发者, I want 同时进行多个独立的聊天会话, so that 我可以在不同项目或主题间自由切换。
3. As a 开发者, I want 看到每个会话的状态（工作中/等待回复/空闲）, so that 我知道哪个会话需要我的关注。
4. As a 开发者, I want 聊天记录完整持久化, so that 服务器重启或手机断网后对话不丢失。
5. As a 开发者, I want 在聊天中通过自然语言命令 CC 产出 PRD 和 Issue, so that 不需要额外学习工具操作。

### 开发流程框架

6. As a 开发者, I want 一个固定的 Grill → PRD → Issues → 宪法检查 → 审批 的框架用于标准/大型需求, so that 复杂改动经过完整的对齐和审查。简单改动可走轻量路径豁免。
7. As a 开发者, I want 每个 Gate 都能用自然语言跳过或重来（"通过"、"跳过"、"重新出 PRD"）, so that 框架不变成负担。
8. As a 开发者, I want 简单的改动可以走轻量路径（一句话直接实现）, so that 修改 typo 不需要经过完整流程。
9. As a 开发者, I want CC 在拆分 Issue 时自动对照 14 条质量宪法, so that 不合规的 Issue 在审批前就被发现。
10. As a 开发者, I want 宪法检查结果区分"必然通过"、"需确认"、"必须人工判断"三级, so that 我把注意力放在真正需要决策的地方。

### 任务管理与审批

11. As a 开发者, I want 在手机上看到一个 Kanban 看板（backlog/ready/in_progress/in_review/done/failed）, so that 一眼了解所有任务的全局状态。
12. As a 开发者, I want 把 backlog 列的 Issue 拖到 ready 后自动触发后台执行, so that 不需要手动运行脚本。
13. As a 开发者, I want 看板上显示每个 in_progress Issue 的执行进度（正在实现/正在测试/AI 审查中/等待审批）, so that 我知道该关注哪个。
14. As a 开发者, I want CC 执行完成后在手机上收到审批通知, so that 我可以及时审查并决定是否通过。
15. As a 开发者, I want 审批卡片上展示改动摘要（改了什么文件、AI 审查评分、测试结果）, so that 我在手机上就能做出审批决策。
16. As a 开发者, I want 点击卡片上的链接跳转到 Gitee 查看完整 PR diff, so that 需要细看时不离开工作流。

### 自动执行

17. As a 开发者, I want 确认的 Issue 自动派发给 Claude Code 执行（TDD 实现→测试→AI 审查）, so that 不需要手动盯着执行过程。
18. As a 开发者, I want CC 执行失败时自动重试最多 3 次, so that 偶发错误不需要我介入。
19. As a 开发者, I want 失败超过 3 次后 Issue 标记为 failed 并展示在看板上, so that 我知道哪些需要人工处理。
20. As a 开发者, I want 执行完成后的 PR 自动展示在看板 done 列上, so that 我可以追踪从 Issue 到合并的完整链路。
21. As a 开发者, I want 多个 CC 实例可以同时执行不同的 Issue, so that 不互相阻塞。

### 质量保障

22. As a 开发者, I want CC 实现的代码通过 AI 自动审查（安全/性能/可维护性）, so that 人审批时有参考依据。
23. As a 开发者, I want 不同模型交叉审查代码（如 Qwen 审查 DeepSeek 的产物）, so that 避免同一模型的盲区。
24. As a 开发者, I want 每次执行的成本（token 用量）被追踪记录, so that 可以评估 AI 开发的经济性。

## Implementation Decisions

### 平台选型

| 组件 | 方案 | 选择理由 |
|------|------|---------|
| 执行引擎 | Archon (coleam00/archon) | 22k+ stars, MIT, YAML DAG workflow, worktree 隔离, 17 内置 workflow |
| 前段聊天 | OpenLobby (kkkkk1k1/openlobby) | SQLite 持久化, CC CLI 原生兼容 `claude --resume`, MCP 元 Agent, 移动端 IM 风格 |
| 审批看板 | 自建 FastAPI + htmx | 极简 (~380 行), 与 MAF-Hub 统一技术栈 |
| 模型路由 | cc-stack（现有） | haiku→DS Flash, sonnet→DS V4 Pro, opus→Qwen3.7-Max |
| 数据传输 | Git | issue 文件全走 Git push/pull, 零新增协议 |

### 前后段隔离

DevFlow 由两个独立 Archon workflow 组成, 通过 issue YAML frontmatter 契约解耦:

- **align workflow**: Grill → PRD → to-issues → constitution-check → approve-issues。人在 OpenLobby 中通过 CC agent 执行 `archon workflow run align` 触发。产出 `status: ready` + `constitution: passed` 的 issue 文件。
- **execute workflow**: implement(TDD loop) → verify → auto-review → approve → create-pr → mark-done。dispatch.sh 自动触发。消费 ready issue, 产出 PR。

前段可替换为任何能产出符合格式 issue 的 Agent, 后段可替换为任何能消费该格式的执行引擎。

### Issue 数据契约

参考 taskmd v1.2 规范，每个 issue 为一个 Markdown 文件，YAML frontmatter 承载结构化元数据，Markdown body 承载人+Agent 可读上下文。

**frontmatter 字段：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `id` | string | ✓ | 唯一标识，文件名前缀（如 `019`） |
| `title` | string | ✓ | 标题，同时作为 `#` 一级标题 |
| `status` | enum | ✓ | `backlog` / `ready` / `in_progress` / `in_review` / `done` / `failed` |
| `type` | enum | ✓ | `AFK`（全自动）/ `HITL`（含人工步骤） |
| `effort` | enum | ✓ | `small`（<2h，自动通过）/ `medium`（2-8h，需确认不超 2d）/ `large`（>8h，宪法检查阻断，必须拆分后再标 ready） |
| `priority` | enum | | `low` / `medium` / `high` / `critical` |
| `blocked_by` | array | | 依赖的 issue 文件路径列表 |
| `needs_llm` | bool | | 需要 LLM 调用 |
| `needs_vision` | bool | | 需要视觉能力 |
| `needs_pdf` | bool | | 需要 PDF 处理 |
| `needs_docker` | bool | | 需要 Docker 环境 |
| `test_files` | array | | 测试文件路径列表 |
| `constitution` | enum | | `pending` / `passed` / `failed`（宪法检查结果） |
| `archon_run` | string | | 关联的 Archon run ID（dispatch 时填入） |
| `pr` | array | | PR URL 列表（create-pr 节点填入） |
| `created_at` | date | | 创建日期 `YYYY-MM-DD` |
| `completed_at` | date | | 完成日期（done 时填入） |

**状态机：**

```
backlog → ready → in_progress → in_review → done
                    ↓                ↓
failed ←──────────────────────────────
```

- `backlog → ready`：人通过宪法检查后手动标记
- `ready → in_progress`：dispatch.sh 抢占时自动标记
- `in_progress → in_review`：create-pr 节点执行后自动标记
- `in_review → done`：PR 合并后人工标记
- `in_progress → failed`：Archon 重试耗尽后自动标记
- `in_review → failed`：PR 被驳回且放弃重试时标记

**Markdown body 约定章节：**

`needs_*` 字段各自独立标记，互不排斥——workflow 据此配置运行环境，无互斥约束。例如 `needs_docker=true` + `needs_llm=false` 表示纯脚本不需要 LLM。

| 章节 | 说明 |
|------|------|
| `## Scope` | In（涉及文件/目录）/ Out（不碰哪些） |
| `## 前置准备` | 外部服务/token/文件/验证方式 |
| `## Acceptance Criteria` | 可测量的验收条件列表 |
| `## 测试策略` | mock 还是真连、E2E 还是单元测试 |
| `## 架构约束` | 引用不可变规则，遵守宪法第 10 条 |
| `## 质量自检` | 对照宪法 14 项 checklist |

### Issue 宪法检查分层

14 条 Issue 宪法分为三层（部分条目跨层拆分为子项）:

- **机器确定检查** (可自动化，6 子项): 工时 ≤2d (1d 通/2d warning)、effort 约束 (small 自动通过/medium 需确认/large 阻断)、type 值合法、blocked_by DAG 无环、needs_* 字段完整、test_files 非空、共享字段 Optional
- **LLM 辅助判断** (7 子项): AC 可测量、目录指定、外部依赖完整性、mock 策略、验收无主观、架构约束引用、集成层覆盖
- **人终审** (2 子项): Scope 边界、SDK 用法参考

> 14 条宪法 → 15 子项：第 9 条"跨 issue 接口引用"拆为 blocked_by DAG 无环 + 共享字段 Optional 两个独立机器检查，其余条目一对一。

宪法检查是一次性准入审查——issue 确认后不再重复检查。通过后 issue 标记 `constitution: passed`。机器检查由 `check_constitution.py` 实现（CLI 工具，被 align workflow 调用），LLM 辅助判断和人工终审在 approve-issues Gate 完成。

### 执行重试与恢复

- mark-done 节点: git push 失败重试 3 次(退避 5s/10s/15s),区分瞬态错误(重试)和永久错误(403/auth 立即退出)
- 最终失败不阻断 workflow —— PR 已创建, status 同步由 reconciler 兜底
- Archon workflow 支持 `--resume` 从断点恢复

### 双数据源一致性

- 权威源: Archon 实际运行状态 (`archon workflow get <run-id> --json`)
- 展示层: issue YAML frontmatter 的 `status` 字段
- 同步: reconciler 每 5 分钟检查 `in_progress` 或 `in_review` 的 issue 对应的 Archon run 实际状态, completed → done, failed → failed, paused → 保持

### 派发触发机制

两层触发，互为兜底：

- **即时触发**：审批看板 `PUT /api/issues/{path}` 将 status 改为 `ready` 后，后端异步执行 `flock -xn /var/run/dispatch.lock -c 'bash dispatch.sh'`。flock 保证与 cron 不并发。这是主路径，人在看板点 ready 后秒级响应。
- **定时兜底**：cron 每 5 分钟 `flock -xn /var/run/dispatch.lock -c 'bash dispatch.sh'`。覆盖异常路径（审批看板挂了、人手动 git push ready issue 等）。

dispatch.sh 开头 `git pull` 保证读到最新状态，`sed -i 's/^status: ready/status: in_progress/'` + `git commit` 形成原子抢占（`^` 锚定仅匹配 frontmatter 行），杜绝重复派发。`flock` 保证 dispatch.sh 同一时刻只有一个实例运行，但不限制 Archon workflow 的并行数——多个 issue 可在一次 dispatch 中依次被派发为独立 Archon run，并行执行。

```cron
# /etc/cron.d/devflow
*/5 * * * * www flock -xn /var/run/dispatch.lock -c 'cd /opt/maf-hub && bash dispatch.sh'
# 每日清理过期 worktree，防止磁盘占满
0 3 * * * www cd /opt/maf-hub && archon isolation cleanup
```

### 审批卡片展示

审批门到达时, 卡片展示三个摘要维度 + 外链, 不嵌入完整 diff(移动端不适合):

- 改动文件列表(从 Archon node output 提取)
- AI 审查评分/建议(从 auto-review node 输出提取)
- 测试结果(pass/fail count, 从 validate node 输出提取)
- [查看完整 PR diff →] 链接跳 Gitee

### 通知机制

审批门到达时通过 Telegram bot 推送消息到手机：

- 审批看板在 Archon workflow 到达 approval 节点时检测到暂停状态
- Telegram bot 发送卡片摘要（改动文件数、AI 审查结论、测试结果）+ [Approve] [Reject] 按钮
- 人在 Telegram 中直接点按钮审批，无需打开浏览器
- 审批看板 30s 轮询兜底，Telegram 不可用时仍可通过 Web 审批

### 网络安全

三个服务（OpenLobby :3001、审批看板 :8421、Archon :8420）均通过 Tailscale 隧道加密，不暴露公网端口。所有服务仅 tailnet 内可访问，不添加额外认证层。

### 轻重分流

复杂度由人在聊天中自行判断, 无需系统自动分类:

- 简单改动(single-file, typo, 配置变更): `archon workflow run execute-light "..."`，单节点 interactive prompt 直接实现，无需 align
- 标准/大型改动: `archon workflow run align "..."`，走完整对齐→审查→执行流程

**execute-light 结构：**

```yaml
# .archon/workflows/execute-light.yaml
# 简单改动——跳过 align + review，一句话直接实现
nodes:
  - id: implement
    prompt: |
      用户请求：$ARGUMENTS
      如果是小改动（typo、单文件修改、简单配置），直接修改文件。
      改动超过单文件时提示用户，确认是否走标准流程。
    interactive: true
```

## Implementation Plan

### Phase 1: 本地试点 (2h)

在开发者本机安装 Archon, 选 `issues/phase2-compiler/020-review-types.md` 做试点。写 `execute.yaml` workflow, 跑通一次 implement→validate→approve→create-pr→mark-done 全流程。验证 Archon CLI 行为、`$ARGUMENTS` 用法、cc-stack 代理兼容性。

### Phase 2: 前段部署 (5.5h)

服务器部署 OpenLobby (多会话 CC 聊天) + 审批看板 (Kanban + 审批按钮) + Telegram bot (审批通知推送) + `check_constitution.py` (宪法机器检查 6 子项)。Tailscale 安全隧道, 手机浏览器+Telegram 访问。

### Phase 3: 后段部署 + 过渡 (3h)

服务器部署 Archon + dispatch.sh + reconciler。试点项目 `issues/phase2-compiler/` 走 Archon, 其余继续 ralph。

### Phase 4: 全量切换 (0.5h)

Archon 扫描范围扩大到全部 `issues/`。ralph 退役。

### Phase 5: 增强 (2h)

自动 PR 审查(双模型交叉) + 成本追踪。

### 开发量

| Phase | 内容 | 时间 |
|:---:|------|:---:|
| 1 | 本地试点 | 2h |
| 2 | 前段部署 | 5.5h |
| 3 | 后段部署 + 过渡 | 3h |
| 4 | 全量切换 | 0.5h |
| 5 | 增强 | 2h |
| **合计** | | **13h** |

## Testing Decisions

### 测试哲学

只测试外部行为, 不测试实现细节。每个组件有独立可验证的验收标准。

### 测试层次

| 层 | 内容 | 方式 |
|-----|------|------|
| 单 workflow | 一个 issue 跑通全流程 | Phase 1 手动验证 |
| 多 workflow 并行 | 2 个 issue 同时 dispatch, 确认隔离正确 | Phase 3 手动验证 |
| 审批流转 | backlog→ready→in_progress→in_review→done 完整链 | Phase 2-3 手动验证 |
| 异常恢复 | mark-done push 失败、dispatch 重复触发、Archon crash | Phase 3 观察 |
| 宪法检查 | 机器可确定检查项对已知合规/不合规 issue 的输出 | Phase 2 单元测试 |

### 自建组件测试

- `approval_board.py`: 单元测试 API 响应格式, 集成测试 status 变更→git push 完整链路
- `dispatch.sh`: 幂等性测试 (flock 并发), reconciler 同步准确性测试

## Out of Scope

| 项目 | 说明 |
|------|------|
| 多用户协作 | 当前单人使用, 不涉及权限/角色 |
| 远程 Archon Worker | Phase 1-5 都在同一台服务器 |
| 审批看板 WebSocket 推送 | 当前 30s 轮询足够 |
| Docker 化部署 | 裸机部署, 后续可选 |
| 审计日志/合规 | 单人项目不需要 |
| 自动化质量门 (lint 自动打回) | 后续增强 |
| Slack/Discord 通知集成 | Telegram 已覆盖通知需求 |
| 分布式 Worker | 当前单机并行 (worktree 隔离) |
| Retro 复盘知识沉淀 | 后续迭代，自动总结踩坑并写入宪法 |

## Further Notes

- 参考项目: [Archon](https://github.com/coleam00/archon) (MIT), [OpenLobby](https://github.com/kkkkk1k1/openlobby)
- 参考文档: `docs/best_practices/开发全流程最佳实践.md`, `docs/best_practices/AI开发指南.md`
- 参考宪法: `knowledge/best_practices/issue-quality-constitution.md`, `knowledge/best_practices/script-quality-constitution.md`
- 完整方案: `/home/dou/.claude/plans/cc-fleet-manager-plan.md`
- 差异说明: 母档中独立的 review workflow（code-review + security-review）已吸收到 execute workflow 的 `auto-review` 节点（安全/性能/可维护性三角度一次性审查），不再独立触发。retro 复盘纳入未来增强
- Phase 结构相对母档合并了过渡观察期和增强功能（Phase 4-7 → Phase 4-5），总工时 11.5→13h 因新增 Telegram bot 和 check_constitution.py
- workflow 文件名：align → `align.yaml`、execute → `execute.yaml`、轻量路径 → `execute-light.yaml`
- 最佳实践参考: `docs/references/archon-best-practices.md`
- 官方文档参考: `docs/references/archon-docs/README.md`
