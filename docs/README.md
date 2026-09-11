# ai-dev-flow-server 文档

## 目录

| 目录 | 内容 |
|------|------|
| [business/](business/) | DevFlow 业务文档（PRD + README） |
| [design/](design/) | 设计文档（Gate 设计 + AFK 迭代史） |
| [references/](references/) | 参考文档（Archon + CLI 参考 + bash-firewall + Gate 排查 + NAS 运维 + **v2→v3 迁移** + **测试策略**） |
| [plans/](plans/) | 设计计划与执行记录（含 NAS 巡检修复、可观测性加固） |
| [decisions/](decisions/) | 架构决策记录 ADR 001–012（含 [ADR-011 NAS 可观测性架构](decisions/011-nas-observability-architecture.md)） |
| [../skills/](../skills/README.md) | 仓库自带 skill 索引（[nas-ops](../skills/nas-ops/SKILL.md) 运维流程、characterize 特征测试） |
| [bot/](bot/) | Silent Observer 插件文档（含 [NAS 运维手册 §十二 巡检与告警链路](bot/nas-access-best-practices.md)） |
| [feedback/](feedback/) | 外部反馈处理回执（UMES3 等租户 → 平台流程） |
| [research/](research/) | 专题调研报告（Claude Code PPT 生成与改造：[调研](research/claude-code-ppt-research-20260828.md) + [实战手册](research/claude-code-ppt-playbook.md)、AI 假绿根因分析） |

## 当前版本

- **v3.7** — spec 出口门禁 spec-gate（2026-09-11）
- v3.6 — 钩子角色门 pre-push/pre-commit 重写（2026-09-03）
- v3.0 — Skill-Harness 分离 + Matt Pocock v1.1 五命令（2026-07-23）
- v2.1 — 计划防覆盖 + Agent B 权限边界（2026-07-01）
- v2.0 — 通用安装器 + Docker 支持 + 测试套件（2026-06-30）

详见 [CHANGELOG.md](../CHANGELOG.md) | 迁移指南: [v2-to-v3-migration.md](references/v2-to-v3-migration.md)
