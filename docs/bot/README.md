# Silent Observer 项目文档索引

> 最后更新: 2026-07-11

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
| 📖 **开发日志** | [silent-observer-dev-journal.md](silent-observer-dev-journal.md) | 14 章全链路踩坑记录、Pipeline 契约、视觉接入、Forward 处理 |
| 🔧 **容器+SSH 运维** | [container-restart-best-practices.md](container-restart-best-practices.md) | 重启顺序、SSH 僵尸防护、Tailscale WSL 冲突、Docker 路径、DSM 清理脚本 |
| 🖥️ **NAS 运维** | [nas-access-best-practices.md](nas-access-best-practices.md) | SSH/Docker 命令、DB 操作、日志解读、UUID 表、Tailscale 性能诊断 |
| ⚙️ **终版配置** | [bot.md](bot.md) | NapCat/LangBot 配置、人设、记忆压缩、联网搜索 |
| 🧬 **进化方向** | [evolution-roadmap.md](evolution-roadmap.md) | 四级进化落地方向、技术选型结论、参考项目清单（配 [evolve.md](evolve.md) 初稿） |
| 🧪 **修复计划** | [at-40-bot-bot-wondrous-owl.md](/home/dou/.claude/plans/at-40-bot-bot-wondrous-owl.md) | 异步识图+内存缓存+双限时间线 |
| 🔀 **转发综合评判** | [at-40-forward-bot-shiny-forest.md](/home/dou/.claude/plans/at-40-forward-bot-shiny-forest.md) | get_forward_msg vs 截图识图决策矩阵 |

---

## 按场景选文档

| 你要做… | 看哪个 |
|---------|--------|
| **接手续盘/开新会话** | **交接文档**（必读）→ 容器运维 |
| 开发新功能/改代码 | 开发日志（Pipeline 契约 + 踩坑） |
| 运维/部署/容器重启 | 容器运维 → NAS 运维 |
| 处理合并转发 | 转发综合评判 → 开发日志第十三章 |
| 改人设/调参数 | 终版配置（bot.md） |
| 规划下一步进化 | 进化方向（evolution-roadmap.md） |
| 查日志/调 bug | NAS 运维 → 开发日志对应章节 |
