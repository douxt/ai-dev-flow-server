# CC Fleet Manager — 平台方案调研

@author: Claude Code
@created: 2026-06-22

抛开 MAF-Hub，从零评估适合做 CC 集群管理的轻量平台。

## 核心需求回顾

- 轻量云主机运行（512MB~2GB RAM）
- 聊天界面管理 CC 会话
- 任务队列 + 依赖 DAG
- 人工干预（待干预列表 → 接入回复）
- 多 CC 实例并行监控
- 开源自托管

## 候选平台对比

| 维度 | [profClaw](https://github.com/profclaw/profclaw) | [n8n](https://github.com/n8n-io/n8n) | [Dify](https://github.com/langgenius/dify) | [Windmill](https://github.com/windmill-labs/windmill) | [Dagu](https://github.com/dagucloud/dagu) |
|------|:---:|:---:|:---:|:---:|:---:|
| **定位** | AI Agent 运行时 | 通用自动化引擎 | LLM 应用平台 | 脚本→工作流平台 | 轻量工作流引擎 |
| **语言** | TypeScript | TypeScript | Python | Rust+Svelte | Go |
| **最小内存** | **140MB** ⭐ | ~512MB | ~2GB+ | ~2GB | **~50MB** ⭐ |
| **部署** | npm / Docker | Docker | Docker | Docker | **单二进制** ⭐ |
| **数据库** | 可选 Redis | SQLite/Postgres | Postgres+Redis | **Postgres** | **无** ⭐ |
| **Chat 界面** | ✅ TUI+Web | ❌ 需自建 | ✅ 开箱即用 | ❌ 需自建 | ❌ Web UI（无聊天） |
| **任务队列** | ✅ BullMQ | ✅ 原生 | ✅ Celery | ✅ 原生 | ✅ 内置 |
| **人工干预** | ❌ 需开发 | ✅ 审批节点 | ✅ 审批+接管 | ✅ 审批步骤 | ❌ 需开发 |
| **MCP** | ✅ 内置 | ❌ | ❌ | ❌ | ✅ 内置 |
| **多 Agent** | ✅ 原生 | ✅ AI节点 | ✅ Agent模式 | ❌ | ❌ |
| **CC 集成** | ✅ CLI + SDK | ⚠️ 命令节点 | ⚠️ API调用 | ⚠️ Bash脚本 | ⚠️ 命令步骤 |
| **License** | AGPL-3.0 | Sustainable Use | Apache 2.0 | AGPL-3.0 | MIT |
| **GitHub Stars** | — | 180k | 130k | 16k | — |

---

## 逐平台评估

### 1. profClaw — 最接近需求的现成方案 ⭐

**已有（需要什么它有什么）**：
```
✅ AI Agent 运行时       → 可直接管理 CC 作为 agent
✅ BullMQ 任务队列       → 持久化、重试、优先级、死信队列
✅ 22 个聊天频道        → Slack/Telegram/Discord/Web/...
✅ MCP Server           → 原生协议，CC 可直接连接
✅ 72 个内置工具        → git/文件/浏览器/cron/web search
✅ 50 个 slash 命令     → /review-pr, /deploy, /ticket ...
✅ 35 个 AI 提供商      → 包含 Claude（通过 API）
✅ PWA Web UI + TUI     → 管理和聊天界面
✅ 140MB 内存 (Pico)    → Raspberry Pi 可运行
```

**缺少（需要开发）**：
```
🔧 CC 进程管理           → CC 不是 profClaw 的"agent"，需要扩展 Worker
🔧 干预队列 UI           → 需新增"待干预"面板
🔧 终端接入              → 需集成 xterm.js（或通过 WebSocket 代理）
🔧 CC stream-json 解析   → 需开发 stream-json ↔ profClaw 事件桥接
```

**评估**：profClaw 已经把"AI Agent 基础设施"做完了——队列、频道、MCP、工具、任务、多模型。我们只需要在上面加 CC Worker 管理层。

### 2. n8n — 最成熟的工作流引擎

**优势**：
- 400+ 集成节点，几乎可以连接任何系统
- 原生审批节点：暂停等待人工确认
- 成熟的错误处理 + 重试 + 人工介入路由
- 庞大的社区和文档

**劣势**：
- **没有聊天界面**——n8n 是后台自动化引擎，前端是工作流画布，不是聊天窗口
- AI Agent 节点基于 LangChain，多 Agent 编排不如 Dify
- 许可证非标准开源
- 需要 500MB+ 内存 + SQLite/Postgres

**适用场景**：需要"CC 执行完成 → 发 Slack 通知 → 人工审批 → 继续下一步"这样的确定性流程。

### 3. Dify — 最完善的 AI 应用平台

**优势**：
- **开箱即用的聊天 UI**——不需要开发聊天界面
- 知识库 + RAG 已内置
- 审批节点 + 人工接管对话
- Workflow 画布支持分支、循环、fan-out
- Apache 2.0 许可证

**劣势**：
- **重量级**：需要 Python + Postgres + Redis + Celery，起码 2GB RAM
- 定位是"面向用户的 AI 应用"，不是"管理 CC 集群的后台"
- CC 只能作为外部 API 调用，无法管理 CC 进程/会话生命周期

**适用场景**：如果你想给最终用户一个 AI 聊天机器人，而不是管理 CC 集群。

### 4. Windmill — 最强的脚本→工作流引擎

**优势**：
- **审批步骤**：流程可暂停，发送审批链接
- 多语言脚本（Python/TS/Go/Bash）自动生成 UI 和 API
- Rust 后端，性能极高（13x Airflow）
- 16k stars，Y Combinator 支持

**劣势**：
- **必须 Postgres**——最轻也得 1-2GB RAM
- AGPL-3.0 许可证
- 没有聊天界面、没有 AI Agent 概念
- CC 只能通过 Bash 脚本调用，比较底层

**适用场景**：偏 DevOps 的自动化，而不是 AI Agent 集群管理。

### 5. Dagu — 最轻量的工作流引擎

**优势**：
- **单 Go 二进制**，无数据库，50MB 内存
- YAML 定义 DAG，Web UI 监控
- MCP Server 内置
- MIT 许可证
- `dagu start-all` 一条命令启动

**劣势**：
- **不是 AI 平台**——没有聊天、没有 Agent、没有 AI 提供商集成
- 人工干预只能通过"暂停步骤 + 外部通知"实现
- 需要从零构建 AI 相关功能

**适用场景**：作为底层任务调度器（替代 ralph-dispatcher.sh），而不是完整 Fleet Manager。

---

## 推荐

### 方案 A：profClaw 做底座（最省开发量）

```
profClaw 提供：
  ✅ 任务队列 (BullMQ)
  ✅ 聊天频道 (Slack/Telegram/Web Chat)
  ✅ MCP Server
  ✅ 多模型路由 (35 提供商)
  ✅ Web UI + TUI
  ✅ 轻量 (140MB)

我们只需开发：
  🏗️ CC Worker 管理 (CC 作为 profClaw 的 tool/agent)
  🏗️ 干预检测 + 队列 UI (profClaw 插件)
  🏗️ stream-json ↔ profClaw 桥接
```

**开发量：约 40%**

### 方案 B：Dagu（调度）+ 自建 UI（最灵活）

```
Dagu 提供：
  ✅ 任务 DAG 调度（单二进制）
  ✅ Web UI（监控面板）
  ✅ MCP Server

自建：
  🏗️ 聊天界面 (FastAPI + React)
  🏗️ CC Worker 管理
  🏗️ 干预通道
  🏗️ 知识提取
```

**开发量：约 70%**

### 方案 C：纯自建（最大控制）

```
FastAPI + React + taskcore + libtmux/stream-json
```

**开发量：100%**

---

## 最终推荐：方案 A（profClaw 底座）

| 对比维度 | MAF-Hub 方案 | profClaw 方案 |
|---------|:-----------:|:------------:|
| 需要开发 | 11 个模块 | ~5 个模块 |
| 已有任务队列 | ❌ 需开发 | ✅ BullMQ |
| 已有聊天频道 | 部分（REPL） | ✅ 22 个频道 |
| 已有 Web UI | ❌ 需开发 | ✅ PWA |
| 多模型路由 | ✅ ModelRouter | ✅ 35 提供商 |
| MCP | ✅ 部分 | ✅ 原生 Server |
| CC 进程管理 | 需开发 | 需开发（相同） |
| 轻量云部署 | ✅ Python | ✅ 140MB |
| License | MIT | AGPL-3.0 |

AGPL-3.0 的风险：如果我们 fork profClaw 做深度修改并以服务形式提供，需要开源。但如果我们以插件/MCP 方式扩展而不改源码，AGPL 只影响分发，不影响使用。

**自建 CC Worker 管理层 + profClaw 提供基础设施 = 最少开发量、最快验证。**
