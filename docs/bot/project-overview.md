# Silent Observer 项目总纲

> 一页纸速览：项目是什么、做到哪了、下一步做什么

## 项目定位

群聊 Bot 插件，运行在 NAS 上，通过 QQ 协议接入群聊。

**核心能力**：
- **消息存储**：所有群消息存入 KB（ChromaDB）
- **智能回复**：@触发 / 20%随机插话，基于时间线+上下文生成回复
- **视觉理解**：自动识别图片，注入视觉描述到 prompt
- **工具调用**：群成员可通过 @bot 触发 search_chat_history

## 当前状态（2026-08-06）

### ✅ 已完成

1. **调研阶段**（2026-07-11）
   - Reflexion 框架、记忆系统、自我进化 Agent 全景调研
   - 下载 7 个参考项目到 `~/dev/references/bot-evolve-refs/`

2. **代码评审**（2026-07-12）
   - 对照官方 SDK/示例，识别 P0-P2 缺陷

3. **基础重构**（2026-07 ~ 2026-08）
   - default.py 拆分为 util/store/service 模块
   - QQ 表情识别修复（Unknown Face → `[QQ表情:名称]`）
   - 视觉识别（图片 → AI 描述注入 prompt）
   - 增量摘要（P1 Anchored Incremental Summarization）

4. **反思层**（2026-07 ~ 2026-08）
   - 纠正检测 + 反思写入 + 检索注入闭环
   - P0 参数调优（关键词 17→31、冷却 10min→3min 等）

5. **耗时分析与诊断**（2026-08-06）
   - 全链路耗时瓶颈分析（LLM 推理占 >90%）
   - prompt 分模块 token 拆解（Tools 34%、Timeline 17% 等）
   - bench_latency.py / analyze_dump.py 诊断工具

### ⏳ 待执行

**对话成熟度**（P1 反思增强，~185 行）：
- P1.1 话语重写层——补全省略句，提升纠正捕获率
- P1.2 自我反思源——每 10 轮自我审视，主动发现错误
- P1.3 检索增强——k=3→10 + LLM Rerank
- P1.4 When-Then 格式——可执行规则替代描述性文本
- 详见 [evolution-roadmap.md](evolution-roadmap.md)

**地基重建**（7 步，计划已就绪）：
- 标准插件目录 + pytest 底座 + 渐进式拆分
- 详见 [ground-reconstruction-plan.md](ground-reconstruction-plan.md)

**进化路线第二级**：
- LLM-as-a-Judge 自我评估打分
- 详见 [evolution-roadmap.md](evolution-roadmap.md)

## 文档体系

### 核心文档（必读）

| 文档 | 用途 | 适合谁 |
|------|------|--------|
| [交接文档](claude-handoff-silent-observer.md) | 项目全貌、部署流程、UUID 速查 | 新会话/接手者 |
| [代码评审](code-review-against-official.md) | P0-P2 缺陷清单、验收 rubric | 重构执行者 |
| [地基计划](ground-reconstruction-plan.md) | 7 步拆分方案、测试金字塔 | 重构执行者 |

### 调研文档（选读）

| 文档 | 内容 | 适合谁 |
|------|------|--------|
| [调研全景](research-agent-memory.md) | Reflexion/记忆框架/Judge/自我进化 | 研究者 |
| [记忆插件研究](memory-plugins-study.md) | 5 插件深度分析、可借鉴机制 | 架构设计者 |
| [插件开发参考](langbot-plugin-dev-reference.md) | v4 API 速查、官方示例 | 插件开发者 |

### 运维文档（按需查阅）

| 文档 | 内容 |
|------|------|
| [NAS 访问](nas-access-best-practices.md) | SSH/Docker/Tailscale 最佳实践 |
| [容器重启](container-restart-best-practices.md) | 重启顺序、僵尸进程清理 |
| [自动化测试指南](automated-testing-guide.md) | 测试金字塔、CI 方案 |

### 事故报告（事后复盘）

| 文档 | 时间 | 根因 |
|------|------|------|
| [Docker 僵尸进程](incident-20260713-docker-hang.md) | 2026-07-13 | SSH 管道未正确清理 |
| [MCP 超时](incident-20260713-mcp-timeout.md) | 2026-07-13 | 网络抖动 + 无超时控制 |

## 关键决策（ADR）

详见 [docs/decisions/](../decisions/)

- ADR-001：插件目录结构选 plugins/
- ADR-002：测试策略选核心层单测优先
- ADR-003：可测性设计用依赖注入
- ADR-004：不用 QQ 酒馆插件

## 参考资源

- **官方 SDK**：`~/dev/references/bot-evolve-refs/langbot-plugin-sdk/`
- **参考项目**：`~/dev/references/bot-evolve-refs/`（7 个，详见 [参考资产地图](reference-assets-map.md)）
- **Codegraph 索引**：`~/dev/.codegraph/`（含 ai-dev-flow-server 和 references）

---

*最后更新：2026-07-13*
