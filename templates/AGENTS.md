<!-- ai-dev-flow-server:AGENTS-START -->
# AGENTS.md — __PROJECT__

> 本文件由 ai-dev-flow-server 管理，是**任何 AI 编码 agent**（Claude Code / Cursor / Copilot / Codex / 自研 agent）接入本项目的唯一入口。只读本文件即可执行本项目开发流程。

## 1. 项目身份

- 技术栈：__STACK_TAGS__（install.sh 从 .devflow/config.yaml tech_stack.tags 注入；未配置时留占位）
- 关键路径：
  - `.devflow/` — DevFlow 管线（scripts/ gate 命令、knowledge/ 质量宪法、templates/ 角色模板）
  - `issues/` — ticket 与 spec（开发任务入口）
  - `RULES.md` — 项目踩坑规则（若有）
- 角色：`.devflow/scripts/devflow role` 查看当前角色

## 2. 开发流程

阶段状态机（写入 `.devflow/stage`，每次推进只保留最新值）：

```
explore:done → spec:done → tickets:done → tickets:reviewed → tdd:done → implement:done → done
```

ticket 状态机（frontmatter status 字段）：`backlog → ready → in_progress → in_review → done | failed`

标准路径：读 spec/ticket → RED（写失败测试，commit 含 "TDD: RED"）→ GREEN（实现，commit）→ 验证（§3 命令）→ 推进阶段。

## 3. Gate 命令表（shell 调用，零框架依赖）

| 时机 | 命令 | 作用 |
|------|------|------|
| RED commit 前 | `bash .devflow/scripts/test-gate.sh` | C0.1-C0.9 秒检，不过阻断 |
| GREEN commit 前 | `bash .devflow/scripts/green-gate.sh` | G2.1-G2.3：测试文件未被 GREEN 改 / 无硬编码空数据 / 无 skip、only 残留 |
| GREEN commit 前 | `bash .devflow/scripts/g0-inject.sh <源文件> [测试名]` | G0 故障注入——验证测试真能拦住 Bug（注入→测试必须 RED→恢复→GREEN） |
| 阶段推进验证 | `bash .devflow/scripts/stage-verify.sh <stage:done>` | I1-I5 证据检查（**只读验证，不推进状态**）。合法值：spec:done / tickets:done / tickets:reviewed / tdd:done / implement:done |
| 阶段状态推进 | `echo "implement:done" > .devflow/stage` | 手动模式唯一写入口（无 CC hooks 时） |
| ticket 宪法检查 | `python3 .devflow/scripts/check_constitution.py <ticket.md>` | 16 项自动检查 + 安全红线。需先 `pip install python-frontmatter` |
| 分层检查 | `bash .devflow/scripts/check-layer.sh [git-range]` | 业务代码 vs 管线文件判定（默认 main..HEAD） |
| 事件记录 | `bash .devflow/scripts/trace.sh <event_type> <key=value> ...` | 追加事件到 `.devflow/trace.jsonl` |
| 角色查看/切换 | `.devflow/scripts/devflow role [switch <R>|list]` | owner / developer / agent-b |

**commit message 规范（硬性）**：RED commit 必须含 `TDD: RED` 字样——stage-verify I1 检查依赖 `git log --grep="TDD: RED"`，缺失即阶段验证失败。

## 4. 质量宪法与知识

- `.devflow/knowledge/` 下 01-12 份宪法（核心方法论 / Step-Gate 流程 / Spec 质量 / Ticket 质量 / 脚本质量 / 测试质量 / 断言强度 / 安全红线等）——写代码前按当前阶段读对应份
- `.devflow/knowledge/stacks/` 技术栈知识（按项目 tech_stack tags 部署）

## 5. CC 独有能力 → 其他 agent 适配

| Claude Code 能力 | 其他 agent 替代 |
|------------------|----------------|
| PreToolUse/PostToolUse hooks 自动拦截 | 手动跑 §3 gate 命令（能力已全部 CLI 化，无功能损失） |
| 斜杠命令（/tdd /implement /code-review） | 按 §2 流程手动执行各阶段 + §3 命令验证 |
| CLAUDE.md 角色段自动注入 | 本文件即注入载体 |
| stage-tracker 自动阶段追踪 | 手动 `echo "stage:done" > .devflow/stage` + `stage-verify.sh` 验证 |
| /code-review 独立审查产物 | 审查后写 `.devflow/code-review-report.md`（stage-verify I5 依赖该文件存在且非空） |

## 6. 硬性规则（所有 agent 必须遵守）

**合并铁律**：合并 master 的唯一条件（四者缺一不可）：
1. 开发完毕
2. 测试验证完毕
3. 用户手动测试通过
4. **用户明确下达合并命令**

- 用户下令前 master 保持只读，所有改动只在 worktree/分支中；禁止主动提议合并
- 收到合并命令后：rebase → diff against expected → merge → push

**代码隔离**：有 wt 工具 → `wt create <任务名>` 创建隔离 worktree，禁止直接改主仓库；无 shell → 分支即隔离（`ai/<issue>-<desc>`，禁止直推 master/main）

**A 模式**：issues/ 下存在 `blocked_by` 依赖链 ticket 组时，单 worktree 按依赖序顺序开发，末票 GREEN 前不合并 master；同层无冲突票可并行（开第二 worktree）

**修改安全**：改前备份 `cp file file.bak`；全局替换前先 grep 列清单确认范围；永不 `git checkout -- <file>`（用 stash/.bak 恢复）；每完成一个逻辑改动立即提交
<!-- ai-dev-flow-server:AGENTS-END -->
<!-- 角色段（agent-b 时追加）：由 templates/roles/agent-b/AGENTS.md 提供，带独立标记区间 -->
