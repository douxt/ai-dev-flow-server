# 计划文档（历史参考）

这些是 DevFlow 演进过程中的设计计划，已固化为当前实现。状态标注仅供参考。

| 文件 | 内容 | 状态 |
|------|------|------|
| [01-archon-fleet-manager.md](01-archon-fleet-manager.md) | MAF-Hub 完整实施计划 v4.1：Archon workflow 编码 8 Gate + 14 宪法，7 Phase | ✅ 已落地 |
| [02-prd-draft.md](02-prd-draft.md) | CC Fleet Manager 需求草案 v0.3：Lumbergh 底座 + Fleet 扩展 | 📦 已归档（并入 MAF-Hub） |
| [03-platform-evaluation.md](03-platform-evaluation.md) | 平台方案调研：profClaw / n8n / Dify / Windmill / Dagu 五平台对比 | 📦 已归档 |
| [04-human-gate-design.md](04-human-gate-design.md) | 人工介入前置化设计：两段式架构（人环内规划 + AI 自动执行），对标 5 个业界项目 | ✅ 已落地 |
| [05-adaptation-to-server.md](05-adaptation-to-server.md) | ai-dev-flow 服务器版设计：install.sh 通用化、三种部署模式、四种调度器 | ✅ 已落地 |

## 2026-09 计划（NAS 运维线）

| 文件 | 内容 | 状态 |
|------|------|------|
| [2026-09-11-nas-health-check-repair.md](2026-09-11-nas-health-check-repair.md) | 巡检静默失效修复（阶段一）：`set -e` 吞分支、路径失效、探针误判，13 项 AC | ✅ 已完成 |
| [2026-09-11-nas-observability-hardening.md](2026-09-11-nas-observability-hardening.md) | 可观测性与运维加固（阶段二）：告警出口、深度金丝雀、漂移对账、nas-ops skill | ✅ 已完成 |
| [2026-09-11-dsh-in-code-server.md](2026-09-11-dsh-in-code-server.md) | DSH 装入 code-server 容器：Node 22、状态根落卷、Tailscale 暴露、重建不丢验收 | ✅ 已完成 |
