---
name: ltm-langrag-restoration-20260729
description: LTM 不工作的根因——LangRAG 插件被禁用 + 文件在 bak 目录，恢复后 QQ 群路径正常但 /sync 路径有 pipeline 上下文限制
metadata:
  type: project
---

# LTM 故障诊断与恢复 (2026-07-29)

## 根因

LTM（LongTermMemory）不工作，两级原因：

1. **LangRAG 插件被禁用**：`plugin_settings` 表中 `langbot-team/LangRAG.enabled=0`
2. **LangRAG 插件文件在备份目录**：文件在 `plugins.v3-bak/langbot-team__LangRAG/`，不在生效目录 `plugins/`

LangRAG 是所有 KB（Dou + Long）的底层向量引擎。LangRAG 不可用 → 所有 KB 操作失败 → LTM 的 `remember()`/`recall_memory()` 调用报错 `"memory knowledge base is not configured for the current pipeline"`。

## 修复步骤

1. 启用 LangRAG：`UPDATE plugin_settings SET enabled=1 WHERE plugin_name='LangRAG'`
2. 恢复文件：`cp -r /volume1/docker/langbot/data/plugins.v3-bak/langbot-team__LangRAG /volume1/docker/langbot/data/plugins/`
3. 按文档顺序重启：langbot-plugin → langbot（等30s healthcheck） → napcat

## 验证结果

| 路径 | LTM 状态 | 说明 |
|------|---------|------|
| QQ 群 WebSocket | ✅ 正常 | Chroma 返回 3 条记忆，Bot 正确回复 |
| `/sync` HTTP Bot | ❌ | `list_pipeline_knowledge_bases()` 返回空 — 框架层 pipeline 上下文限制 |

## /sync 限制

`api.list_pipeline_knowledge_bases()` 通过 `query_pool.cached_queries[query_id]` 获取 pipeline 配置。`/sync` 端点的 HTTP Bot 适配器可能未正确填充 `pipeline_config` 的 `knowledge-bases`，导致此 API 返回空列表。

**影响**：`verify-fix.sh --ltm` 能检测到 "memory KB 未配置" 错误，但不能验证真实记忆存取。真正的 LTM 功能验证需依赖 QQ 群消息。

## 踩坑教训

- `plugins.v3-bak` 是 v3 迁移时的备份目录，插件文件可能在这里但不在生效目录
- 插件在 DB 中 `enabled=1` + 文件在 `plugins/` 目录，两者缺一不可
- Docker 容器重启顺序必须遵守 `docs/bot/container-restart-best-practices.md`
- LangBot 插件运行时通过 WS 注册，重启后可能需要等待较长时间才能重连

**How to apply:** LTM 相关问题时，首先检查 LangRAG 插件状态（DB enabled + 文件存在），确保两个 KB（Dou + Long）都在 pipeline 的 knowledge-bases 列表中。
