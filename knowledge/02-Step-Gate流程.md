# Step-Gate 开发流程规范（服务器版）

> 基于 AI 开发指南 v4.0 框架。采用 **Step Gate** 结构，覆盖从需求到合入的完整生命周期。
> 服务器版与本地版的核心差异：AFK 执行由 dispatch.sh + Archon workflow 替代 ralph-once.sh。

## 流程总图

```
                      ┌─────────────┐
                      │  Gate 0      │  项目初始化（install.sh 一键安装）
                      │  初始化      │
                      └──────┬──────┘
                             │
                      ┌──────v──────┐
                      │  Gate A      │  捕捉原始需求（口述/草案/链接）
                      │  需求草案    │
                      └──────┬──────┘
                             │
                      ┌──────v──────┐
                      │  Gate 1      │  /grill-me 全方位拷问
                      │  需求对齐    │
                      └──────┬──────┘
                             │
                      ┌──────v──────┐
                      │  Gate 2      │  /to-prd → PRD.md
                      │  产出 PRD    │
                      └──────┬──────┘
                        ▲    │
                        │    v  不通过（回 Gate 1）
                        │  ┌─────────────┐
                        │  │  Gate 3      │  /to-issues → 垂直切片
                        │  │  拆解 Issue  │
                        │  └──────┬──────┘
                        │    ▲    │
                        │    │    v  不通过
                        │  ┌─────────────┐
                        │  │  Gate 4      │  Issue 评审
                        │  │  Issue 评审  │
                        │  └──────┬──────┘
                        │         │
                        │  ┌──────v──────┐
                        │  │  Gate 5      │  环境准备（检查 .devflow/）
                        │  │  环境准备    │
                        │  └──────┬──────┘
                        │    ▲    │
                        │    │    v  不通过
                        │  ┌─────────────┐
                        │  │  Gate 6      │  AFK 管线确认
                        │  │  AFK 就绪    │
                        │  └──────┬──────┘
                        │         │
                        │  ┌──────v──────┐
                        │  │  Gate 7      │  人审 QA + PR 合入
                        │  │  审查合并    │
                        │  └──────┬──────┘
                        │         │
                        │  ┌──────v──────┐
                        │  │  Gate 8      │  踩坑记录 + 宪法更新
                        │  │  复盘改进    │
                        │  └─────────────┘
                        │
                        └── 回退到 Gate 3/5 继续下一轮
```

## Gate 间流转规则

### 正向流转

每个 Gate 是**顺序依赖**的：前序 Gate 未通过（`.gate-state` 中 status ≠ `passed`），后续 Gate 拒绝执行。workflow 脚本在入口处自动检查。

### 回退机制

| 触发条件 | 回退目标 | 操作 |
|---------|:------:|------|
| Gate 2 PRD 出口检查不通过 | Gate 1 | 修正需求理解偏差，重新 `/gate-1-grill` |
| Gate 4 Issue 评审不通过 | Gate 3 | 按评审意见重拆 Issue |
| Gate 7 审查不通过 | Gate 5 | 创建新 issue → Gate 6 重新 AFK |
| Gate 8 复盘发现问题 | Gate 0-6 | 视问题归属回退到对应 Gate |

回退时人手动将 `.gate-state` 中对应 Gate 设为 `blocked`，修正后重新进入。

### Issue 状态机

```
backlog → ready → in_progress → done
```

| 状态 | 含义 | 谁操作 |
|------|------|:------:|
| `backlog` | 阻塞未解除，不可开工 | 人 |
| `ready` | 可被 dispatch 抢占 | 人（通过质量门禁后） |
| `in_progress` | dispatch 正在消化 | dispatch.sh |
| `done` | 完成，PR 已合并 | 人 |

### Issue 拆分原则

- **单 issue 工时 ≤1d**，超过则拆
- **能独立验证、独立交付**的算一个 issue
- Issue 正文自带"分阶段"描述的，**直接按阶段拆成独立 issue**
- 拆分后依赖链清晰：每个 issue 明确 `blocked_by`
- 类型标记：`type: AFK` / `type: HITL`

---

## Gate 0 — 项目初始化

一次性。新项目启动时执行 `install.sh`。

**进入条件**：无（项目的第一个门）

**执行规范**：

```bash
bash install.sh /path/to/project --tech-stack <python|node|go>
```

install.sh 做的事：
1. 预检：git repo? CLAUDE.md? issues/? 测试套件?
2. 生成 `.devflow/config.yaml`
3. 复制 workflows/ → `~/.claude/workflows/`
4. 复制 `.gate-state` 模板
5. 追加 CLAUDE.md 片段
6. 复制 archon/ + scripts/ + knowledge/ → `.devflow/`
7. 输出 root 段命令（激活 systemd timer）

**出口检查**：

| # | 检查项 | 方法 |
|:-:|--------|------|
| 0.1 | 基础工具就绪 | `git` `python3` `claude` 可访问 |
| 0.2 | .devflow/ 目录完整 | `ls .devflow/config.yaml .devflow/knowledge/` |
| 0.3 | gate 脚本已注册 | `ls ~/.claude/workflows/gate-*.js` |
| 0.4 | dispatch timer 已激活 | `systemctl is-active dispatch-*.timer` |

**产物**：`.devflow/` 目录、`.gate-state`、注册的 gate 脚本

---

## Gate A — 需求草案

**进入条件**：有原始需求输入。形式不限（口述/对话/文件/链接/原型）。

**执行规范**：无强制规范。此 Gate 的目标是**确认原始需求已明确表达**，不加工、不评估。

**出口检查**：

| # | 检查项 | 方法 |
|:-:|--------|------|
| A.1 | 需求已明确表达 | 口述/文件/链接，至少一种形式 |
| A.2 | 关键背景信息完整 | 解决什么问题、现有方案、为什么现在做 |
| A.3 | 核心约束已提及 | 技术栈、时限、质量要求（如有） |

**产物**：口述场景为会话上下文；有文件时落 `docs/<name>-draft.md`

---

## Gate 1 — 需求对齐（/gate-1-grill）

**进入条件**：Gate 0 已完成，Gate A 已通过。

**执行规范**：调用 `/grill-me` 围绕草案做全方位拷问。

**出口检查**：

| # | 检查项 | 方法 |
|:-:|--------|------|
| 1.1 | 所有关键决策已覆盖 | 审查产出，无"待定"事项 |
| 1.2 | 分歧已消除 | 无未关闭的 question |
| 1.3 | 否决项已明确 | 明确说了"不做"的已记录 |

---

## Gate 2 — 产出 PRD（/gate-2-prd）

**进入条件**：Gate 1 已通过。

**执行规范**：调用 `/to-prd` 时附带 `.devflow/knowledge/03-PRD质量宪法.md`。

**出口检查**（对照宪法 9 项）：

| # | 检查项 | 宪法条目 |
|:-:|--------|:--------:|
| 2.1 | 六段齐全 | #1 |
| 2.2 | Risks ≥5 + 缓解 | #2 |
| 2.3 | AC 定量可测 | #3 |
| 2.4 | 异常路径 4 类覆盖 | #4 |
| 2.5 | 外部依赖接口签名 | #5 |
| 2.6 | 估算 ≤5d | #7 |
| 2.7 | US 有独立 AC | #8 |
| 2.8 | Out of Scope 不含 N+1 | #9 |
| 2.9 | 架构约束已引用 | #11 |

**产物**：`docs/<项目>-prd.md`

---

## Gate 3 — 拆解 Issue（/gate-3-issues）

**进入条件**：Gate 2 已通过，PRD 文件就位。

**执行规范**：调用 `/to-issues` 附带 `.devflow/knowledge/04-Issue质量宪法.md`。

**出口检查**：

| # | 检查项 | 来源 |
|:-:|--------|:----:|
| 3.1 | 每条 estimate ≤1d | 宪法 #1 |
| 3.2 | type 正确 | 宪法 #2 |
| 3.3 | AC 全可量化 | 宪法 #3 |
| 3.4 | 代码目录已指定 | 宪法 #4 |
| 3.5 | 前置准备完整 | 宪法 #5 |
| 3.6 | mock/E2E 策略明确 | 宪法 #6 |
| 3.7 | SDK 用法可参考 | 宪法 #7 |
| 3.8 | 验收无主观 | 宪法 #8 |
| 3.9 | blocked_by 无循环 | 宪法 #9 |
| 3.10 | 架构约束已引用 | 宪法 #10 |
| 3.11 | AC 覆盖集成层 | 宪法 #11 |
| 3.12 | Scope 边界清晰 | 宪法 #12 |
| 3.13 | needs_* 已声明 | 宪法 #13 |
| 3.14 | test_files 已指定 | 宪法 #14 |
| 3.15 | 总体工作量与 PRD 一致 | 实践 |
| 3.16 | 切片方向标注 | 实践 |

**产物**：`issues/<###>-<描述>.md`

---

## Gate 4 — Issue 评审（/gate-4-review）

**进入条件**：Gate 3 完成，issue 文件就位。

**执行规范**：调用 `/review-cc-cli --rubric plan --explore` 评审 issues/ 目录。

**出口检查**：

| # | 检查项 | 方法 |
|:-:|--------|------|
| 4.1 | 至少 1 轮评审完成 | 产生 `.review-report-*.json` |
| 4.2 | 最终 verdict APPROVED | 不接受 CHANGES_REQUESTED |
| 4.3 | 评审员按宪法检查 | prompt 携带宪法文件 |
| 4.4 | 阻塞项全部修复 | 跟踪表已闭环 |
| 4.5 | 各 issue 一致 | estimate/blocked_by 对齐 |

---

## Gate 5 — 环境准备（/gate-5-prep）

**进入条件**：Gate 4 已通过（issue 合规可发布）。

**执行规范**（服务器版）：

不再执行 `prep-once.sh`。改为检查：
1. `.devflow/` 目录完整（config.yaml + archon/ + scripts/ + knowledge/）
2. `config.yaml` 有效（YAML 可解析，必填字段齐全）
3. `dispatch-<project>.timer` 已激活

**出口检查**：

| # | 检查项 | 方法 |
|:-:|--------|------|
| 5.1 | .devflow/ 目录完整 | `ls .devflow/config.yaml .devflow/archon/ .devflow/scripts/` |
| 5.2 | config.yaml 有效 | YAML 可解析 |
| 5.3 | dispatch.timer 已激活 | `systemctl is-active dispatch-*.timer` |

**产物**：环境就绪，AFK 管线待命

---

## Gate 6 — AFK 就绪（/gate-6-afk）

**进入条件**：Gate 5 已通过。

**执行规范**（服务器版）：

不再执行 `ralph-once.sh`。改为确认 AFK 管线就绪：
- dispatch.timer 每 5 分钟扫描 ready issue
- 发现 ready issue → dispatch.sh 原子抢占 → Archon 执行 7 节点工作流
- 完成后 Telegram 通知审批

Gate 6 只做确认，不触发执行。人确认后标 passed。

**AFK 自动消化流程**：

```
dispatch.timer（每 5 分钟）
  → dispatch.sh 扫描 issues/ 找第一个 status: ready
  → check_constitution.py 7 项机器检查
  → 通过 → 原子抢占（ready → in_progress）
  → archon run auto-execute-afk <issue>
    → implement → validate → auto-review → cross-review → merge-reviews → create-pr → mark-in-review
  → notify.py 发送 Telegram 通知
```

**出口检查**：

| # | 检查项 | 方法 |
|:-:|--------|------|
| 6.1 | dispatch.timer active | `systemctl is-active dispatch-*.timer` |
| 6.2 | issues/ 目录存在 | `ls issues/` |
| 6.3 | 至少 1 个 ready issue | `grep -l "status: ready" issues/*.md` |
| 6.4 | gh auth 有效 | `gh auth status` |

**产物**：人确认后 AFK 管线开始自动消化 ready issue

---

## Gate 7 — 审查合并

**进入条件**：PR 已创建。

> Gate 7 为人工审查步骤。问题发现→创建新 issue→放入 backlog，不直接修改 AI 代码。

**出口检查**：

| # | 检查项 |
|:-:|--------|
| 7.1 | AC 逐条对照代码 |
| 7.2 | 测试不是假测试 |
| 7.3 | E2E 验证过 |
| 7.4 | 外部依赖真接通 |
| 7.5 | commit 粒度合理 |
| 7.6 | 无越界文件 |

---

## Gate 8 — 复盘改进

**进入条件**：PR 已合入。

**出口检查**：

| # | 检查项 |
|:-:|--------|
| 8.1 | 踩坑记录已追加 |
| 8.2 | 宪法是否需要更新 |
| 8.3 | issue 状态同步 done |

---

## 附录 A — 规范文件索引

| 文件 | 内容 | 引用于 |
|:----|------|:------:|
| `.devflow/knowledge/01-核心方法论.md` | AI 辅助编程方法论 v4.0 | Gate 1, 2, 6 |
| `.devflow/knowledge/03-PRD质量宪法.md` | PRD 宪法 11 项 | Gate 2 |
| `.devflow/knowledge/04-Issue质量宪法.md` | Issue 宪法 14 项 | Gate 3, 4 |
| `.devflow/knowledge/05-脚本质量宪法.md` | 脚本宪法 12 项 | Gate 5 |
| `.devflow/knowledge/06-AFK脚本栈规范.md` | 服务器 AFK 管线规范 | Gate 5, 6 |
| `.devflow/knowledge/07-Agent防护体系.md` | Agent 约束最佳实践 | Gate 6 |

## 附录 B — 角色与工具

| 环节 | 执行者 | 工具/脚本 | 产出 |
|------|:------:|-----------|------|
| 项目初始化 | 人 | install.sh | .devflow/ + .gate-state |
| 需求草案 | 人+CC | 会话 | 草案文件或对齐上下文 |
| 需求对齐 | 人+CC | /grill-me | 设计决策 |
| PRD | 人+CC | /to-prd | PRD.md |
| 拆解 Issue | 人+CC | /to-issues + 宪法 | issues/*.md |
| Issue 评审 | CC 子进程 | /review-cc-cli + 宪法 | .review-report-*.json |
| 环境准备 | 人 | /gate-5-prep | 确认 .devflow/ 完整 |
| AFK 实施 | dispatch.sh + Archon | auto-execute-afk.yaml | 代码+测试+PR |
| 审查 | 人 | QA 清单 | PR 合入 |
| 复盘 | 人+CC | 踩坑记录 | 宪法/踩坑更新 |
