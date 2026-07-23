---
name: process-v2-design
description: 开发全流程 Step Gate 重构方案
author: Claude Code
created: 2026-06-01
updated: 2026-07-23 (v3.0)
status: active
---

# 开发全流程 Step Gate 重构方案

> **v3.0 (2026-07-23)**: 架构已升级为 Skill-Harness 分离模式。Matt Pocock v1.1 五命令直接调用，约束由基础设施层（hooks/checkers）兜底。详见 [CHANGELOG.md](../../CHANGELOG.md) 和 [v2→v3 迁移指南](../references/v2-to-v3-migration.md)。
>
> **v3.0 核心变化**：9 Gate → 5 阶段（explore→spec→tickets→implement→done），workflow-gate hook 入口拦截，stage-tracker hook 产物检测，全流程 trace 日志。

## 一、动机

现有 `开发全流程最佳实践.md`（600 行）是全流程单一汇编文件：
- 流程步骤与宪法引用是**松耦合**——`§三` 说宪法，`§四` 说流程，读者需要前后翻页
- 各步骤缺少"出口门禁"——做完后没有量化检查清单确认"可以走下一步"
- 产物/消费者关系不明确——不知道当前步骤产出的文档被谁消费、什么时候消费

目标：改成 **Step Gate** 结构，每步自带门禁。

## 二、Step Gate 设计

Gate = 每一步 == 三段式 == 进入条件/执行规范/出口检查。

```
[Step N] 步骤名

**进入条件（前置）**
  □ 条件 A
  □ 条件 B

**执行规范**
  - 宪法/规范文件引用
  - 使用的 skill/命令
  - 各端角色说明

**出口检查**
  □ 检查项 1（来源：宪法 #X）
  □ 检查项 2（来源：实践要求）
  （全部通过才进入下一步）

**产物 → 消费者**
```

### 流程总图

```
                      ┌─────────────┐
                      │  Gate 0      │  项目初始化（工具+脚本框架，一次性的）
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
                             │
                      ┌──────v──────┐
                      │  Gate 3      │  /to-issues → 垂直切片
                      │  拆解 Issue  │
                      └──────┬──────┘
                        ▲    │
                        │    v  不通过
                        │  ┌─────────────┐
                        │  │  Gate 4      │  /review 宪法评审
                        │  │  Issue 评审  │
                        │  └──────┬──────┘
                        │         │
                        │  ┌──────v──────┐
                        │  │  Gate 5      │  prep-once 脚本适配
                        │  │  脚本准备    │
                        │  └──────┬──────┘
                        │         │
                        │  ┌──────v──────┐
                        │  │  Gate 6      │  ralph-once/dispatcher
                        │  │  AFK 实施    │
                        │  └──────┬──────┘
                        │    ▲    │
                        │    │    v  不通过
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

回退机制：
- Gate 4（评审）不通过 → **回 Gate 3** 重拆 Issue
- Gate 7（审查）不通过 → **回 Gate 5** 重跑 AFK
- Gate 8（复盘）无回退，持续积累

### 对现有流程的拆解

现有流程（按 `开发全流程最佳实践.md` 章节）：

| 当前 § | 内容 | 拆入 Gate |
|:------:|------|:---------:|
| §一 | 核心流程总图 | 保留为总览 |
| §二 | Issue 质量门禁（宪法） | 嵌入 Step 3-5 出口 |
| §三 | issue 模板与 frontmatter | 嵌入 Step 4 执行规范 |
| §四 | AFK 实施规范（6 节） | 拆入 Step 7 |
| §五 | 架构约束与数据流 | 嵌入所有步骤 |
| §六 | 检查点 | 嵌入 Step 6 出口 |
| §七 | AFK 后审查 | 嵌入 Step 8 |
| §八 | 工具链总览 | 保留 |
| §九 | TDD 规范 | 嵌入 Step 7 |
| §十 | 脚本规范引用 | 嵌入 Step 7 |

### 重新组织为 9 个 Gate

```
Gate 0  项目初始化（工具 + 脚本框架搭建）
Gate A  需求草案（捕捉原始需求→输入到 Grill）
Gate 1  需求对齐（/grill-me）
Gate 2  产出 PRD（/to-prd）
Gate 3  拆解 Issue（/to-issues）
Gate 4  Issue 评审（宪法 14 项 + review）
Gate 5  脚本准备（prep-once 环境准备）
Gate 6  AFK 实施（ralph-once / ralph-dispatcher）
Gate 7  审查合并（QA + PR 合入）
Gate 8  复盘改进（踩坑记录 + 宪法更新）
```

## 三、新增内容

各 Gate 的**出口检查**是本次重构的核心新增。以下列出各 Gate 的出口检查项及其来源。

### Gate 0 — 环境初始化

**进入条件**：无（项目启动的第一个门）

**执行规范**：
- `afk-script-spec.md` §二（生成约定）
- `script-quality-constitution.md`（12 项）

**出口检查**：

| # | 检查项 | 来源 | 方法 |
|---|--------|:----:|------|
| 0.1 | 宪法检查 | 脚本宪法 12 项 | `bash prep-once.sh` 全绿灯 |
| 0.2 | 目录规范 | afk-spec.md §2.1 | 脚本在根目录，lib/、scripts/ 分离 |
| 0.3 | settings-afk 权限 | afk-spec.md §2.6 | deny 配置正确，per-worker 可生成 |
| 0.4 | 基础工具就绪 | 实践要求 | git/python3/uv/claude 可访问 |

**产物**：`prep-once.sh`、`ralph-once.sh`（→ Gate 5/6 消费）

---

### Gate A — 需求草案

**进入条件**：有原始需求输入。输入形式不限：
- 需求提出人口述（当前会话直接输入）
- 对话记录、聊天截图
- 文字草案文件
- 竞品分析、用户反馈、技术方案链接
- 现场可运行原型

此 Gate 的目标是 **确认原始需求已明确表达**，不加工、不评估。

可以进行的操作：
- 需求提出人把想法写入 `docs/requirements/` 下任意格式草案文件
- 直接引用外部资料链接（竞品、技术方案、PRD 草稿等）
- 现场实验/原型验证（可选，对不确定的需求快速做可运行原型）

**出口检查**：

| # | 检查项 | 来源 | 方法 |
|---|--------|:----:|------|
| A.1 | 需求已明确表达 | 实践要求 | 口述/文件/链接，至少一种形式传达给了 CC |
| A.2 | 关键背景信息完整 | 实践要求 | 解决什么问题、现有方案是什么、为什么现在做 |
| A.3 | 核心约束已提及 | 实践要求 | 技术栈、时限、质量要求（如有） |

**不做什么**（此 Gate 的 Out-of-Scope）：
- 不评估可行性（那是 Gate 1 的事）
- 不拆需求
- 不写 PRD
- 不做设计

**产物**：口述场景下为当前会话上下文（→ Gate 1 直接消费）；有文件时落 `docs/requirements/<name>-draft.md`

---

### Gate 1 — 需求对齐

**进入条件**：
- Gate 0 已完成（基础设施就绪）
- Gate A 已通过（需求草案就位，作为 /grill-me 的输入材料）

**执行规范**：
- AI 开发指南 v4.0 §阶段 1
- `/grill-me` 或 `/grill-with-docs`
- 输入为 Gate A 的草案文件，Grill 过程围绕草案内容做拷问与补全

**出口检查**：

| # | 检查项 | 来源 | 方法 |
|---|--------|:----:|------|
| 1.1 | 所有关键决策已覆盖 | 实践要求 | 审查 grill 产出，无"待定"事项 |
| 1.2 | 分歧已消除 | 实践要求 | 无未关闭的 question |

**产物**：设计决策记录（→ Gate 2 消费）

---

### Gate 2 — 产出 PRD

**进入条件**：Gate 1 已通过

**执行规范**：
- AI 开发指南 v4.0 §阶段 2
- `/to-prd`

**出口检查**：

| # | 检查项 | 来源 | 方法 |
|---|--------|:----:|------|
| 2.1 | PRD 含 Problem/Solution/User Stories | 实践要求 | 人快速浏览 |
| 2.2 | PRD 含 Implementation/Tests/Out of Scope | 实践要求 | 审查 §Implementation Decisions |
| 2.3 | Risks & Mitigations 章节存在 | PRD 评审经验 | 至少 5 项风险 |
| 2.4 | Out of Scope 明确 | 实践要求 | 不含 Phase N+1 内容 |
| 2.5 | 工作量估算合理 | 实践要求 | 横向对比同类工作 |

**产物**：`docs/requirements/*-prd.md`（→ Gate 3 消费）

---

### Gate 3 — 拆解 Issue

**进入条件**：Gate 2 已通过，PRD 文件就位

**执行规范**：
- `/to-issues`
- `issue-quality-constitution.md`（宪法 14 项）
- `vertical-slice-rules`（垂直切片原则）

**出口检查**：

| # | 检查项 | 来源 | 方法 |
|---|--------|:----:|------|
| 3.1 | 每条 estimate ≤1d | 宪法 #1 | grep estimate: |
| 3.2 | type 正确（AFK/HITL） | 宪法 #2 | AFK 不含人工步骤 |
| 3.3 | AC 全可量化 | 宪法 #3 | 无"质量好"等模糊表述 |
| 3.4 | 目录已指定 | 宪法 #4 | AC 或正文写明代码路径 |
| 3.5 | 前置准备完整 | 宪法 #5 | 外部服务/token/文件已写明 |
| 3.6 | mock/E2E 策略明确 | 宪法 #6 | AC 明确测试方式 |
| 3.7 | SDK 用法可参考 | 宪法 #7 | 依赖表格已记录 |
| 3.8 | 验收无主观判断 | 宪法 #8 | 无"代码整洁"等表述 |
| 3.9 | blocked_by 无循环、接口稳定 | 宪法 #9 | 共享类型使用 Optional |
| 3.10 | 架构约束已引用 | 宪法 #10 | 参考 docs/history.md |
| 3.11 | AC 覆盖集成层 | 宪法 #11 | 不只是模块，含编配层 |
| 3.12 | Scope 边界清晰 | 宪法 #12 | In/Out 清单 |
| 3.13 | needs_* 已声明 | 宪法 #13 | needs_llm/vision/pdf/docker/mcp |
| 3.14 | test_files 已指定 | 宪法 #14 | 精确路径 |
| 3.15 | 依赖链形成 DAG   | 实践要求 | blocked_by 无循环 |
| 3.16 | 整体工作量与 PRD 一致 | 实践要求 | sum(estimate) 与 PRD ±20% |
| 3.17 | 切片方向明确（垂直 vs 水平） | 实践要求 | 标注每条的垂直度 |

**产物**：`issues/phase2-compiler/###-*.md`（→ Gate 4 评审 / Gate 6 消费）

---

### Gate 4 — Issue 评审

**进入条件**：Gate 3 complete，切片方案 + issue 文件就位

**执行规范**：
- `/review —deep —rubric plan`
- `issue-quality-constitution.md`（评审员逐条对照）

**出口检查**：

| # | 检查项 | 来源 | 方法 |
|---|--------|:----:|------|
| 4.1 | 至少 1 轮评审完成 | 实践要求 | IEEE 1028 标准 |
| 4.2 | verdict 为 APPROVED | 实践要求 | 不接受 CHANGES_REQUESTED |
| 4.3 | 评审员按宪法检查 | 实践要求 | prompt 中携带宪法文件 |
| 4.4 | 阻塞项全部修复 | 实践要求 | 跟踪表闭环 |
| 4.5 | slices.md 与各 issue 一致 | 实践要求 | 对比 slices 和 issue 的 estimate/blocked_by |

**产物**：`.review-report-*.json` → 归档

---

### Gate 5 — 脚本准备

**进入条件**：Gate 4 已通过

**执行规范**：
- `afk-script-spec.md` §4.2（脚本检查点）
- `script-quality-constitution.md`（12 项）

**出口检查**：

| # | 检查项 | 来源 | 方法 |
|---|--------|:----:|------|
| 5.1 | 搜索路径正确 | afk-spec §4.2 | grep ISSUE_DIR |
| 5.2 | 依赖过滤完整 | afk-spec §4.2 | grep blocked_by |
| 5.3 | 代码位置映射正确 | afk-spec §4.2 | grep PULSE8_DIR |
| 5.4 | per-worker 设置到位 | afk-spec §4.2 | grep ISSUE_DIRS |
| 5.5 | 依赖表格更新 | afk-spec §4.2 | 读 prompt-builder.sh |
| 5.6 | 宪法 12 项全部通过 | 脚本宪法 | grep/shellcheck 验证 |
| 5.7 | prep-once 空跑通过 | 实践要求 | `bash prep-once.sh` 全绿灯 |

**产物**：环境就绪（/tmp/maf-env.sh、依赖已安装）→ Gate 6 消费

---

### Gate 6 — AFK 实施

**进入条件**：Gate 5 已通过（prep-once 全绿灯）

**执行规范**：
- `ralph-once.sh` 或 `ralph-dispatcher.sh`
- AI 开发指南 v4.0 §阶段 4（AFK）
- TDD 规范（RED → GREEN → REFACTOR）
- 最多 3 次重试 /diagnose 流程

**出口检查**：

| # | 检查项 | 来源 | 方法 |
|---|--------|:----:|------|
| 6.1 | 全部 AC 实现 | 实践要求 | 逐条对照 AC 清单 |
| 6.2 | 测试全绿 | 实践要求 | `uv run pytest <test_files> -q` |
| 6.3 | 外部依赖已接通 | 实践要求 | 不是只留接口 |
| 6.4 | 无越界文件 | 实践要求 | `git diff --stat` 确认范围 |
| 6.5 | 每模块独立 commit | TDD 规范 | `git log` 可读 |
| 6.6 | ≤3 次重试 | 实践要求 | 失败日志可查 |
| 6.7 | reset 不影响其他 issue | 实践要求 | trap 只释放自身 |

**产物**：代码 + 测试 + PR（→ Gate 7 消费）

---

### Gate 7 — 审查合并

**进入条件**：PR 已创建，CI 通过

**执行规范**：
- QA 清单
- 同 §三 出口检查 6.1-6.7 人审

**出口检查**：

| # | 检查项 | 来源 | 方法 |
|---|--------|:----:|------|
| 7.1 | AC 逐条对照代码 | 实践要求 | 读 AC → 看产出 |
| 7.2 | 测试不是假测试 | 实践要求 | 读断言逻辑 |
| 7.3 | E2E 测过 | 实践要求 | 日志或运行记录 |
| 7.4 | 外部依赖真接通 | 实践要求 | 调用链可查 |
| 7.5 | commit 粒度合理 | 实践要求 | 每模块独立提交 |
| 7.6 | 无越界文件 | 实践要求 | `git diff --stat` |

**产物**：PR 合入 master（→ Gate 8 复盘）

---

### Gate 8 — 复盘改进

**进入条件**：PR 已合入

**执行规范**：无

**出口检查**：

| # | 检查项 | 来源 | 方法 |
|---|--------|:----:|------|
| 8.1 | 踩坑记录已追加 | 实践要求 | 新 pitfall 写入 maf-pitfalls.md |
| 8.2 | 宪法是否需要更新 | 实践要求 | 新坑 → 提炼 → 追加宪法 |
| 8.3 | issue 状态更新 done | 实践要求 | 全部 issue 同步 |

## 四、不涉及修改的内容

- AI 开发指南 v4.0 框架（上层方法论，不嵌入）
- review rubrics（评审标准，独立维护）
- 脚本宪法 / issue 宪法（规范文件，Gate 引用不复制）
- afk-script-spec.md（脚本规范，Gate 引用不复制）

## 五、实施步骤

| 步骤 | 操作 | 产出 |
|:----:|------|------|
| 1 | 本设计方案审批 | 人确认方向 |
| 2 | 重写 `开发全流程最佳实践.md`（Step Gate 结构） | 新流程文档 |
| 3 | 各宪法文件增加 Gate 映射（frontmatter 标注引用的 Gate） | 宪法可追溯 |
| 4 | 删除旧版流程文档（可选） | 清理 |

## 六、风险与限制

| 风险 | 缓解 |
|------|------|
| 600 行重写可能引入遗漏 | 保留原文档作为"历史"，新文档完成后对比覆盖率 |
| Gate 过多增加形式感 | 出口检查是"速查"不是"填表"，每条检查都对应过往踩坑 |
| 宪法变更后 Gate 不同步 | 宪法 frontmatter 标注 `applies_to_gates: [3, 4]`，自动可审计 |
