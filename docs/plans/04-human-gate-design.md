# 人工介入前置化 — 调研与方案

@author: Claude Code
@created: 2026-06-22

## 核心洞察

你说得对——不需要中途介入 CC。把人工介入**全部前置到规划阶段**，CC 只执行已确认的 issue。这个模式在 2026 年已经是最佳实践。

## 业界共识：Phase-Gated Pipeline

2026 年主流 AI 开发框架几乎全部采用相同的架构模式：

```
[人工密集区]                    [自动区]
  对齐 → PRD → Issue拆分  │  实现 → 测试 → 审查 → 合并
  ←── 人在 Loop 内 ──→    │  ←── AI 自主执行 ──→
          ↑ 硬性审批门       ↑ 自动流转
```

> *"Delegate execution to AI, but do not delegate decision ownership."*
> — Hyper-Waterfall 方法论

### 对标你的流程

| 你的阶段 | 业界标准术语 | 人工参与 |
|---------|------------|:---:|
| 聊天探讨 | **DEFINE / Align** | 全程 |
| Grill → PRD | **PLAN / Spec** | 审批 PRD |
| To Issues | **DECOMPOSE / Issue** | 审批拆分结果 |
| —审批门— | **Human Approval Gate** | 🔴 硬性阻塞 |
| Ralph 自动循环 | **IMPLEMENT / Build** | 无 |
| 自动测试 | **VERIFY / Test** | 无 |
| PR 审查 | **REVIEW / Merge** | 审批 PR |

## 最有参考价值的项目

### 1. pattern-stack/claudecode-patterns — 理念最接近

```
Plan → Strategy → Code → Review
  ↑ 聊天审批     ↑ label审批    ↑ PR审批
  (同步门)       (同步门)       (异部门)

核心机制：Implementer Agent 拒绝工作，除非看到 state:strategy-approved
```

**亮点**：SDLC 配置化 (`sdlc.yml`)，不改 prompt 文件；`/orchestrate` 可并行跑 epic

### 2. agent-tasks — 管道最完整

```
backlog → spec → plan → implement → test → review → done
   ↑        ↑       ↑                              ↑
   MCP      WebSocket  REST API               Web Dashboard (:3422)
```

**亮点**：7 阶段状态机 + DAG 依赖 + 审批工作流 + 337 测试，MCP 直接对接 CC

### 3. Dev Harness — 门禁最严格

```
DEFINE → PLAN → BUILD → VERIFY → SIMPLIFY → REVIEW → SHIP
   ↑                                                ↑
   人工                                             人工
              ←── 中间 5 阶段全自动 ──→
              (自动门禁，不通过则 git reset --hard)
```

**亮点**：自动门禁 + Ralph Loop 模式（失败就 fresh context 重来），多 Agent 审查委员会防自我放水

### 4. Kagan — UI 最直接

```
Kanban: BACKLOG → IN_PROGRESS → REVIEW → DONE
                                    ↑
                              人工审批硬门（无法自动化绕过）
```

**亮点**：Web Dashboard + VS Code 插件 + TUI + MCP，每个 task 隔离 git worktree

### 5. U2DIA — 最轻量

**亮点**：单个 `server.py` 文件、零依赖纯 Python、17 个 MCP 工具、Android 客户端、SSE 实时推送

## 你的流程 vs 业界对照

```
你的流程               业界标准实现              可直接参考

聊天探讨           →  DEFINE 阶段               (自建，MAF Agent REPL)
Grill → PRD        →  SPEC/PLAN 阶段 + 人工审批门   agent-tasks spec→plan
To Issues          →  DECOMPOSE 阶段              pattern-stack /orchestrate
── 审批门 ──       →  Human Approval Gate         Kagan REVIEW column
Ralph 自动循环     →  IMPLEMENT+VERIFY 阶段       Dev Harness Ralph Loop
PR 审查合并        →  REVIEW→DONE                Kagan hard gate
```

## 方案建议：两段式架构

```
┌─ 前段：人在环内 ─────────────────────────────┐
│                                              │
│  聊天界面 (MAF Agent REPL / Web Chat)          │
│    ↓                                         │
│  Grill → PRD 草稿                             │
│    ↓                                         │
│  To Issues（AI 辅助拆分）                      │
│    ↓                                         │
│  ┌─────────────┐                              │
│  │ 审批看板      │  ← 移动 Web UI              │
│  │ 每个 issue    │    人审核/修改/确认           │
│  │ [确认] [驳回] │                              │
│  └──────┬──────┘                              │
│         │ 审批通过                             │
│         ▼                                     │
│     status: ready                             │
│                                              │
├─ 审批门 ──────────────────────────────────────┤
│         │                                     │
├─ 后段：自动执行 ─────────────────────────────┤
│         │                                     │
│    Ralph Dispatcher（常驻服务）                 │
│    ├─ 扫描 ready issue                        │
│    ├─ 分发给 CC Worker                         │
│    ├─ 监控状态                                 │
│    └─ 完成后创建 PR                            │
│                                              │
│    CC-1  CC-2  CC-3 ...                      │
│                                              │
└──────────────────────────────────────────────┘
```

## 最小可行实现

不需要自建所有东西，组装即可：

| 组件 | 方案 | 说明 |
|------|------|------|
| **聊天对齐** | 现有 MAF Agent REPL | 已有，增强 Web 界面 |
| **PRD 生成** | 现有 /to-prd skill | 已有 |
| **Issue 拆分** | 现有 /to-issues skill | 已有 |
| **审批看板** | **Kagan** 或 **U2DIA** | 按需引入，MCP 协议对接 |
| **Issue 存储** | 现有 issues/*.md | 已有 |
| **自动调度** | ralph-dispatcher.sh → **agent-tasks** 或保留 | 可选替换 |
| **状态监控** | **U2DIA** SSE 实时推送 | 引入 |
| **移动端** | **U2DIA** Android + Web PWA | 引入 |

## 与之前方案的对比

| 维度 | 之前（中途介入） | 现在（前置审批） |
|------|:---:|:---:|
| 技术复杂度 | 高（stream-json 桥接、状态检测） | **低**（标准审批门） |
| CC 改造 | 需要扩展 CC 协议 | **不需要** |
| 业界对齐 | 自己发明的模式 | **2026 主流最佳实践** |
| 可用轮子 | 零 | **Kagan/U2DIA/agent-tasks** |
| 风险 | 高（detection 不可靠） | **低**（确定性状态机） |
