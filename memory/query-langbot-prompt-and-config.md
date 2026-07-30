---
name: query-langbot-prompt-and-config
description: 快速查询 LangBot 系统提示词、Pipeline 配置、插件配置的方法
metadata:
  type: reference
---

## 系统提示词（静态 Prompt）

**Pipeline 配置存于 `langbot.db` 的 `legacy_pipelines` 表**：

```python
import sqlite3, json
db = sqlite3.connect("/app/data/langbot.db")
# 1. 找到 bot 使用的 pipeline UUID
cur = db.execute("SELECT use_pipeline_uuid FROM bots WHERE enable=1 LIMIT 1")
pipeline_uuid = cur.fetchone()[0]
# 2. 读取 pipeline 配置中的 prompt
cur = db.execute("SELECT config FROM legacy_pipelines WHERE uuid=?", (pipeline_uuid,))
cfg = json.loads(cur.fetchone()[0])
prompt_items = cfg['ai']['local-agent']['prompt']
for i, item in enumerate(prompt_items):
    print(f"=== [{i}] {item['role']} (len={len(item['content'])}) ===")
    print(item['content'])
```

**关键点**：
- `prompt` 是一个数组，每个元素有 `role` 和 `content`
- `[0]` 是 system prompt，包含身份、工具说明、规则等
- 注入的动态内容（时间线、搜索结果、图片描述）是**追加**到这个数组后面的

## 插件配置

**plugin_settings 表**，通过 `plugin_author` + `plugin_name` 定位：

```python
cur = db.execute("SELECT config FROM plugin_settings WHERE plugin_author='dou' AND plugin_name='langbot-silent-observer'")
cfg = json.loads(cur.fetchone()[0])
# 得到: kb_id, embedding_model_uuid, vision_model_uuid 等
```

表结构：`plugin_author`, `plugin_name`, `enabled`, `priority`, `config`(JSON)

## 快速命令（一行搞定）

```bash
ssh root@nas 'docker exec langbot /app/.venv/bin/python3 -c "
import sqlite3,json;
db=sqlite3.connect(\"/app/data/langbot.db\");
uuid=db.execute(\"SELECT use_pipeline_uuid FROM bots WHERE enable=1 LIMIT 1\").fetchone()[0];
cfg=json.loads(db.execute(\"SELECT config FROM legacy_pipelines WHERE uuid=?\",(uuid,)).fetchone()[0]);
[print(f\"[{i}] {x[\"\"role\"]} ({len(x[\"\"content\"])}字)\") for i,x in enumerate(cfg[\"\"ai\"][\"\"local-agent\"][\"\"prompt\"])]"
"'
```

## KB 查询

```python
import chromadb
c = chromadb.PersistentClient(path="/app/data/chroma")
col = c.get_collection("da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc")  # Dou KB
r = col.get(where={"session_id": "group_1104330614"}, include=["metadatas", "documents"])
```
