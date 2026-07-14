# Silent Observer 项目文档索引

> 最后更新: 2026-07-14(napcat 转发卡死根因 + 文档更新)

---

## 新会话接手 → 看这一个就够了

**[claude-handoff-silent-observer.md](claude-handoff-silent-observer.md)** — 完整交接文档，包含：
- 已完成工作清单
- 当前架构（gate → inject → vision → KB）
- 配置文件位置（DB 表、ChromaDB）
- 部署流程 + 容器管理
- UUID 速查 + 日志解读
- 待办事项

---

## 快速导航

| 目的 | 文档 | 内容 |
|------|------|------|
| 📋 **交接（新会话必读）** | [claude-handoff-silent-observer.md](claude-handoff-silent-observer.md) | 已完成工作、架构、部署、配置、待办 |
| 📖 **开发日志** | [silent-observer-dev-journal.md](silent-observer-dev-journal.md) | 22 章全链路踩坑记录、Pipeline 契约、视觉接入、Forward 处理、napcat 转发卡死根因 |
| 🔧 **容器+SSH 运维** | [container-restart-best-practices.md](container-restart-best-practices.md) | 重启顺序、SSH 僵尸防护、Tailscale WSL 冲突、Docker 路径、DSM 清理脚本 |
| 🖥️ **NAS 运维** | [nas-access-best-practices.md](nas-access-best-practices.md) | SSH/Docker 命令、DB 操作、日志解读、UUID 表、Tailscale 性能诊断 |
| ⚙️ **终版配置** | [bot.md](bot.md) | NapCat/LangBot 配置、人设、记忆压缩、联网搜索 |
| 🧬 **进化方向** | [evolution-roadmap.md](evolution-roadmap.md) | 四级进化落地方向、技术选型结论、参考项目清单（配 [evolve.md](evolve.md) 初稿） |
| 🔬 **调研报告** | [research-agent-memory.md](research-agent-memory.md) | Reflexion/A-Mem/Mem0/Letta/Zep/Judge/self-evolving 全景调研 + 来源 |
| 🧠 **记忆插件研究** | [memory-plugins-study.md](memory-plugins-study.md) | 5 个开源记忆插件深度分析(机制+坐标+可移植清单+许可证) |
| ✅ **代码评审** | [code-review-against-official.md](code-review-against-official.md) | 对照官方 SDK/示例的 default.py P0-P2 基线(rubric) |
| 🧩 **插件开发参考** | [langbot-plugin-dev-reference.md](langbot-plugin-dev-reference.md) | LangBot v4.0+ 插件 API/组件/事件/向量操作速查 |
| 🧪 **自动化测试指南** | [automated-testing-guide.md](automated-testing-guide.md) | 测试金字塔(单元/集成/E2E)+lbp run+CI 方案 |
| 💥 **事故报告** | [incident-20260713-docker-hang.md](incident-20260713-docker-hang.md) | Docker 僵尸会话崩守护进程——时间线/根因/修复/预防 |
| 💥 **MCP 超时事故** | [incident-20260714-mcp-timeout.md](incident-20260714-mcp-timeout.md) | MCP 工具调用超时导致会话锁死 9 小时 |

---

## 按场景选文档

| 你要做… | 看哪个 |
|---------|--------|
| **接手续盘/开新会话** | **交接文档**（必读）→ 容器运维 → 事故报告 |
| 写插件/查 LangBot API | 插件开发参考（langbot-plugin-dev-reference.md） |
| 写/跑自动化测试 | 自动化测试指南（automated-testing-guide.md） |
| 开发新功能/改代码 | **代码评审**（先看已知缺陷）→ 开发日志 |
| 研究 bot 进化/记忆 | 进化方向 → 调研报告 → 记忆插件研究 |
| 运维/部署/容器重启 | 容器运维 → NAS 运维 → 事故报告 |
| 改人设/调参数 | 终版配置（bot.md） |
| 查日志/调 bug | NAS 运维 → 开发日志对应章节 |
