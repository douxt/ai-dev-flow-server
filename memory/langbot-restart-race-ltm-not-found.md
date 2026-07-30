---
name: langbot-restart-race-ltm-not-found
description: LangBot restarts 后 LTM not found 的根因——双容器 DB 锁竞争与根治
created: 2026-07-20
source: offline-scan
origin_session: d45c2e4d-a6ae-493e-8747-87a3f477d892
---

**根因**：`langbot` 和 `langbot-plugin` 容器同时启动，plugin 读到 `plugin_settings` 表时 db 锁冲突 → LTM 插件加载失败 → 后续调用报 "not found"，常被误判为 LTM 本身问题。

**解决**：compose.yaml 加 `depends_on: langbot: condition: service_healthy`，保证 plugin 等 langbot healthy 后才启动（`healthcheck` 已有则直接用）。改 compose 而非代码，低风险，根治 90% 竞争场景。

**预防**：凡两个容器共享同一 SQLite 且一方启动时读表另一方可能还在写，必须设启动顺序。不依赖超时靠运气。此外 LTM not found 时优先怀疑启动竞争，而非插件缺失。

