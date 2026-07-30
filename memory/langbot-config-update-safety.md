---
created: pre-2026-07
name: langbot-config-update-safety
description: LangBot 配置更新安全规范 — 防止覆写 DB 中其他字段
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 181d5298-a621-4a5e-ac53-a94d916290d4
---

# LangBot 配置更新安全规范

**根因**：`legacy_pipelines.config` 是完整 JSON，`SELECT → 修改 → UPDATE` 会将被修改版本覆写整个字段，若 DB 中已有 UI 侧更新的配置，会被旧值覆盖。

**正确做法**：

1. **改前先备份完整 JSON 到文件**（非 /tmp，容器重启即失）：
```
docker exec langbot /app/.venv/bin/python3 -c "
import json, sqlite3
db = sqlite3.connect('/app/data/langbot.db')
config = json.loads(db.execute('SELECT config FROM legacy_pipelines').fetchone()[0])
with open('/app/data/config_backup.json', 'w') as f:
    json.dump(config, f, ensure_ascii=False, indent=2)
"
```

2. **精确字段更新** — 只改目标字段，不整库序列化：
```sql
UPDATE legacy_pipelines SET config = json_set(config, '$.ai.local-agent.prompt[0].content', '新内容') WHERE ...
```

3. **若必须 Python 处理**，读后立即改、立即写，不间隔异步操作

4. **改后 diff 验证** — 对比备份和当前，确认只改了预期字段：
```python
# 只改了 prompt content 和 output.misc，不应影响 model/trigger/safety
```

5. **错误覆写后的恢复**：备份文件在 `/app/data/config_backup.json`，可还原

**Why:** 2026-07-12 修改提示词时，SELECT→修改prompt→UPDATE 整库 JSON，无意将 output.misc(at-sender/quote-origin) 和 model UUID 覆写为旧值。

**How to apply:** 任何涉及 `legacy_pipelines.config` 的修改，优先用 `json_set()` SQL 函数做精确字段更新；必须 Python 处理时先备份、改后对比。

## 已验证的 json_set 示例

```sql
-- 改管线随机概率
UPDATE legacy_pipelines SET config = json_set(config, '$.trigger.group-respond-rules.random', 0.99);

-- 改提示词
UPDATE legacy_pipelines SET config = json_set(config, '$.ai.local-agent.prompt[0].content', '新提示词');

-- 改输出设置
UPDATE legacy_pipelines SET config = json_set(config, '$.output.misc.at-sender', false);
UPDATE legacy_pipelines SET config = json_set(config, '$.output.misc.quote-origin', false);

-- 改模型
UPDATE legacy_pipelines SET config = json_set(config, '$.ai.local-agent.model.primary', '模型UUID');
```

## 踩坑记录

- 2026-07-12 第1次：改提示词 → 覆写 output.misc + model
- 2026-07-12 第2次：改提示词 → 同上
- 2026-07-12 第3次：改 group-respond-rules.random → 再次覆写 model

**三次都是 SELECT→Python修改→UPDATE整个JSON 导致的。永远不再用这个模式。**
