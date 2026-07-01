# CC Fleet Manager — 需求草案 v0.3

@author: Claude Code
@created: 2026-06-22
@updated: 2026-06-22
@workflow: 需求分析 + 调研 + 技术选型

## 技术选型：Lumbergh 做底座

[Lumbergh](https://github.com/voglster/lumbergh) — Python/FastAPI/libtmux/React/xterm.js, MIT license, 68 releases。

## 开发量分析：Lumbergh 已有 vs 我们需要

### ✅ Lumbergh 已提供（不需要开发）

| 功能 | 说明 |
|------|------|
| 多会话 Web 仪表板 | React + Tailwind，xterm.js 终端面板 |
| tmux 会话管理 | libtmux 驱动：创建/销毁/attach/detach |
| 终端交互 | WebSocket 双向流，xterm.js 渲染 |
| Git 集成 | diff 查看器、commit 图、分支切换 |
| 文件浏览器 | 语法高亮、项目文件树 |
| 多 Agent 支持 | Claude Code / Cursor / Aider / Gemini CLI / OpenCode / Codex |
| Prompt 模板 | 可复用的提示词模板 |
| 基础 Todo 列表 | 简单任务记录 |
| Manager AI 聊天 | 内置 AI 对话面板 |
| 认证 | 密码保护 + HMAC Cookie |
| 存储 | TinyDB（JSON 文件），`~/.config/lumbergh/` |

### 🏗️ 需要开发（Fleet Manager 扩展）

| 模块 | 内容 | 预估 |
|------|------|:---:|
| **1. 干预检测引擎** | 解析 tmux `capture_pane` 输出，匹配 `[HUMAN_NEEDED]` 标记 → 更新会话状态 | 中 |
| **2. 干预队列 UI** | Lumbergh 前端新增"待干预"面板：会话列表、问题摘要、等待时长、点击接入 | 中 |
| **3. 干预通道** | 人在 xterm.js 输入回答 → 通过 libtmux `send_keys` 注入 CC 会话 → CC 继续 | 小 |
| **4. 状态机** | 会话三态 🟢工作中 / 🟡等人干预 / ⚪闲置 + 状态流转 + WebSocket 实时推送 | 小 |
| **5. 任务队列** | 待办→确认→入队→分发，DAG 依赖，优先级，taskcore/JSON 持久化 | 大 |
| **6. 常驻调度器** | Python 替代 ralph-dispatcher.sh：消费队列、启动 CC Worker、监控状态、重试 | 大 |
| **7. Worker 管理** | 本机 worker（libtmux）+ 远程 worker（HTTP 注册），能力标记，健康检查 | 大 |
| **8. 聊天增强** | 多会话聊天复用 MAF Agent REPL + FileHistoryProvider，新增 `@fleet` 指令 | 中 |
| **9. 知识提取** | 聊天→摘要→knowledge/，待办自动提取，参考 Verbatim/Inkstone 模式 | 中 |
| **10. 通知推送** | 等人干预时浏览器 Notification API + 可选 Telegram/ntfy.sh | 小 |
| **11. 远程 Worker 通信** | HTTP/WebSocket 协议，任务下发、状态上报、终端代理 | 大 |

### 🔧 需要改进（Lumbergh 有但不够）

| 功能 | 现状 | 需要的改进 |
|------|------|-----------|
| Todo 列表 | 简单文本记录 | 加状态机（构思→确认→排队→执行→完成）、优先级、依赖、来源聊天引用 |
| 会话状态 | 基本运行/停止 | 加 🟡等人干预 状态，与干预队列联动 |
| Prompt 模板 | 静态模板 | 支持变量替换、上下文注入、干预回复快捷模板 |

---

## 分阶段开发

### Phase 1：核心闭环（最小可用）
> 本机单机，聊天→待办→调度→干预

```
聊天(MAF Agent) → 待办 → 队列 → CC Worker → 等人干预 → 人在 Lumbergh 介入
```

开发内容：
- 干预检测引擎 + 状态机
- 干预队列 UI 面板（Lumbergh 前端加一个 Tab）
- 干预通道（xterm.js → libtmux send_keys）
- 通知推送
- 待办列表扩展（状态机）

**不需要开发（Phase 1）**：
- 常驻调度器（先用 ralph-dispatcher.sh 手动触发）
- 远程 Worker（先只本机）
- 知识提取（先手动）
- 任务队列 DAG（先 FIFO）

### Phase 2：自动化
- 常驻调度器（Python 替代 ralph-dispatcher.sh）
- 任务队列 DAG + 优先级
- Worker 管理（本机多 worker）

### Phase 3：分布式
- 远程 Worker 注册与通信
- 跨机任务分发
- Worker 能力匹配

### Phase 4：智能化
- 聊天自动知识提取
- 聊天→待办自动生成
- 任务执行分析与推荐

---

## Phase 1 详细开发清单

### 后端（Python，Lumbergh 内扩展）

```
backend/
├── fleet/                          # 新增
│   ├── __init__.py
│   ├── detector.py                 # 干预检测引擎
│   │   └── scan_panes() → 匹配 [HUMAN_NEEDED: ...]
│   │   └── 定时轮询或 hook 触发
│   ├── state_machine.py            # 会话状态机
│   │   └── SessionStatus: WORKING | HUMAN_NEEDED | IDLE
│   │   └── 状态流转 + 事件广播
│   ├── intervention.py             # 干预通道
│   │   └── inject_reply(session_id, text)
│   │   └── via libtmux send_keys
│   ├── notification.py             # 通知推送
│   │   └── browser push + Telegram + ntfy.sh
│   └── todo_ext.py                 # 待办扩展
│       └── 状态字段、优先级、依赖、来源引用
├── routes/
│   └── fleet_routes.py             # Fleet API 端点
│       ├── GET  /api/fleet/sessions       # 所有会话+状态
│       ├── GET  /api/fleet/interventions   # 待干预列表
│       ├── POST /api/fleet/intervene/{id}  # 注入回复
│       └── WS   /ws/fleet                  # 实时状态推送
└── main.py                         # 注册 fleet 模块
```

### 前端（React，Lumbergh 内新增）

```
frontend/src/
├── components/
│   ├── InterventionQueue.tsx        # 待干预面板
│   │   └── 列表：会话名 · 问题摘要 · 等待时长 · [介入]按钮
│   ├── SessionStatusBadge.tsx       # 状态标签
│   │   └── 🟢/🟡/⚪ 带动画
│   ├── TodoBoard.tsx                # 待办看板（扩展现有 Todo）
│   │   └── 列：构思中/已确认/排队中/执行中
│   └── FleetDashboard.tsx           # Fleet 总览
│       └── Worker 数 · 队列深度 · 今日完成
├── hooks/
│   └── useFleetWS.ts                # WebSocket 状态订阅
└── pages/
    └── FleetPage.tsx                # Fleet 主页面
```

### CLI（增强 MAF Agent REPL）

```
core/
├── fleet_commands.py                # @fleet 指令
│   ├── @fleet status                # 列出所有 CC 会话
│   ├── @fleet intervene <id>        # 快速介入
│   ├── @fleet todo list             # 列出待办
│   ├── @fleet todo add <text>       # 添加待办
│   └── @fleet todo done <id>        # 标记完成
```

---

## Phase 1 架构总览

```
                    ┌──────────────────────┐
                    │   浏览器 (Lumbergh)    │
                    │  ┌───────────────┐    │
                    │  │ 干预队列面板    │ ← 新增
                    │  ├───────────────┤    │
                    │  │ xterm.js 终端  │ ← 已有
                    │  ├───────────────┤    │
                    │  │ Todo 看板      │ ← 扩展
                    │  └───────────────┘    │
                    └──────┬───────────────┘
                           │ WebSocket + HTTP
                    ┌──────┴───────────────┐
                    │   Lumbergh 后端       │
                    │  ┌───────────────┐    │
                    │  │ Fleet 模块     │ ← 新增
                    │  │ 检测/状态/干预  │    │
                    │  ├───────────────┤    │
                    │  │ libtmux 管理   │ ← 已有
                    │  └──────┬────────┘    │
                    └─────────┼────────────┘
                              │ tmux send_keys / capture_pane
                    ┌─────────┴────────────┐
                    │  tmux 会话 (CC Worker)│
                    │  ┌─────────────────┐  │
                    │  │ CC-1  CC-2  ... │  │
                    │  └─────────────────┘  │
                    └──────────────────────┘

       ┌─────────────────────┐
       │  MAF Agent REPL      │
       │  @fleet 指令         │ ← 新增
       │  聊天→待办 (手动)    │
       └─────────────────────┘
```
