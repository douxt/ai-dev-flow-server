# Silent Observer 插件 — 交接文档

> 2026-07-09 | 由会话 52cb34d 移交

---

## 一、项目概况

LangBot QQ 机器人插件，静默观察者。**核心功能**：群聊消息全量归档到 KB，@/随机触发时从 KB 注入时间线 + 语义搜索。

### 仓库

```
/home/dou/dev/ai-dev-flow-server/
```

当前分支：`kb-archive`（worktree 路径：`.claude/worktrees/kb-archive`）

---

## 二、已完成的工作

### 架构
- ✅ 删除 buffer，消息直写 ChromaDB Dou KB（唯一存储）
- ✅ 注入双通道：`vector_list` 时间线 + 混合搜索（向量 + keyword RRF 融合）
- ✅ `search_chat_history` Tool（三维检索：语义/用户/时间）
- ✅ 全面对标 LTM API：`invoke_embedding` + `vector_search` 直连 ChromaDB
- ✅ jieba 中文分词 + 停用词过滤
- ✅ 搜索查询 L2 归一化 + 距离阈值 5.0
- ✅ 触发消息同步写入，其余 fire-and-forget（防竞态）
- ✅ 北京时间（UTC+8）

### System Prompt
- ✅ 分离：[记忆库（LTM）] + [群聊历史检索]，各司其职
- ✅ 措辞统一为"群聊记录"，禁止"全量上下文历史"等说法

### 文档
- 📄 开发计划：`/home/dou/.claude/plans/nas-langbot-docker-shimmering-bubble.md`
- 📄 开发日志：`docs/bot/silent-observer-dev-journal.md`（架构、踩坑、Prompt 迭代、部署清单）
- 📄 本文档：`/tmp/claude-handoff-silent-observer.md`

### 已提交
- ✅ worktree 已 commit，未合并到 main

---

## 三、已完成（2026-07-09 下午）

### 合并与部署
- [x] 合并 kb-archive 到 main 分支
- [x] 清理测试假数据（比特币、养猫、海南旅游、VR头盔）— 25 条 `sender_id=fake`
- [x] 在另一个群（太空工程师）验证搜索效果
- [x] 随机插话模式验证 — `prob=0.1`，机制完整
- [x] `search_chat_history` Tool 端到端验证 — 首次成功调用 14:46，连续 3 次
- [x] 修复 Tool YAML 缺失 bug — 补充 `search_chat_history.yaml`
- [x] 修复 `timestamp_unix=0` — 69 条旧记录补时间戳
- [x] monitoring_messages 全量导入 — 1478 条 → KB 从 130 膨胀到 1416
- [x] 群名片回填机制 — `_backfill_sender()` 自动补全历史
- [x] 提示词注入当前北京时间
- [x] 提示词加入 search_chat_history 工具说明 + 检索决策链

### KB 当前状态
| 群 | 条数 | 时间跨度 |
|---|------|---------|
| 太空工程师群 | 1311 | 2026-06-09 ~ 07-09 |
| 测试群 | 105 | 2016-07-09 + 2026-07-08~09 |

### 新增文件
- `components/tool/search_chat_history.yaml` — 工具注册
- `components/tool/__init__.py` — 包初始化
- `backfill_senders.py` — 存量回填脚本
- `fix_zero_ts.py` — 时间戳修复脚本
- `import_monitoring.py` — 批量导入脚本

### 踩坑记录
详见 `docs/bot/silent-observer-dev-journal.md` 第九章

## 四、待完成

### 高优先级
- [ ] KB 定期 compact / 过期策略
- [ ] 后台任务队列溢出时告警
- [ ] 监控 embedding 调用延迟
- [ ] 太空工程师群进一步验证（更多真实场景）

### 中优先级
- [ ] 更换 embedding 模型评估（text-embedding-3-small）
- [ ] ChromaDB 开启 WAL 模式
- [ ] 存储向量 L2 归一化（避免每次查询归一化）

### 低优先级
- [ ] 清理项目根目录中的一次性脚本（seed_*.py, test_*.py, update_prompt*.py 等）
- [ ] 统一 scripts/ 目录管理工具脚本

---

## 四、NAS 访问

### SSH
```bash
ssh root@nas
```

### Docker 容器
| 容器 | 作用 | 关键路径 |
|------|------|---------|
| `langbot` | LangBot 主进程 | DB: `/app/data/langbot.db`, ChromaDB: `/app/data/chroma/` |
| `langbot-plugin` | 插件运行时 | 插件代码: `/app/data/plugins/dou__langbot-silent-observer/` |
| `napcat` | QQ 协议 | 配置: `/app/napcat/config/onebot11_3228649756.json`, token: `udimc123` |

### Docker 命令
```bash
# 查看容器
ssh root@nas '/usr/local/bin/docker ps'

# 容器内执行 Python
ssh root@nas '/usr/local/bin/docker exec langbot /app/.venv/bin/python3 ...'
ssh root@nas '/usr/local/bin/docker exec langbot-plugin /app/.venv/bin/python3 ...'

# 重启
ssh root@nas '/usr/local/bin/docker restart langbot langbot-plugin'

# 传文件进容器
scp file.py root@nas:/tmp/ && ssh root@nas '/usr/local/bin/docker cp /tmp/file.py langbot:/tmp/'

# 读日志
ssh root@nas '/usr/local/bin/docker logs langbot --tail 50'
ssh root@nas '/usr/local/bin/docker logs langbot-plugin --tail 50'
```

### ChromaDB 操作
```python
import chromadb
c = chromadb.PersistentClient(path="/app/data/chroma")
col = c.get_collection("da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc")  # Dou KB
col = c.get_collection("992ae019-e8ff-47b1-81f7-94519ef2fb6d")  # LTM Long KB
```

### LangBot DB 操作
```python
import sqlite3, json
db = sqlite3.connect("/app/data/langbot.db")
# 关键表：plugin_settings, legacy_pipelines, binary_storages, monitoring_messages, monitoring_sessions, knowledge_bases, embedding_models
```

### 清除测试对话
```sql
DELETE FROM monitoring_messages WHERE session_id='group_1104330614';
DELETE FROM monitoring_sessions WHERE session_id='group_1104330614';
```

### 读取/修改 System Prompt
```bash
scp read_prompt.py root@nas:/tmp/ && ssh root@nas '/usr/local/bin/docker cp ...'
# 脚本位置：/home/dou/dev/ai-dev-flow-server/.claude/worktrees/kb-archive/read_prompt.py
```

---

## 五、部署流程

```bash
# 1. 部署代码到 langbot-plugin 容器
scp default.py root@nas:/tmp/silent_default.py
ssh root@nas '/usr/local/bin/docker exec langbot-plugin sh -c \
  "find /app/data/plugins/dou__langbot-silent-observer -name __pycache__ -exec rm -rf {} +"'
ssh root@nas '/usr/local/bin/docker cp /tmp/silent_default.py \
  langbot-plugin:/app/data/plugins/dou__langbot-silent-observer/components/event_listener/default.py'

# 2. 同样部署 manifest.yaml 和 search_chat_history.py 到对应路径

# 3. 重启两个容器
ssh root@nas '/usr/local/bin/docker restart langbot-plugin langbot'

# 4. 验证
ssh root@nas '/usr/local/bin/docker exec langbot-plugin cat /tmp/silent_init.log'
# 应看到：kb_enabled=True

# 5. 查看调试日志
ssh root@nas '/usr/local/bin/docker exec langbot-plugin cat /tmp/silent_gate.log'
```

### 插件文件清单
| 文件 | 容器路径 |
|------|---------|
| `docker/langbot/plugins/silent-observer/manifest.yaml` | `/app/data/plugins/dou__langbot-silent-observer/manifest.yaml` |
| `.../components/event_listener/default.py` | `/app/data/plugins/dou__langbot-silent-observer/components/event_listener/default.py` |
| `.../components/tool/search_chat_history.py` | `/app/data/plugins/dou__langbot-silent-observer/components/tool/search_chat_history.py` |

### 配置项（在 Web UI 或 DB 设置）
- `kb_id`: `da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc`（Dou KB）
- `embedding_model_uuid`: `62e075f9-733f-458c-8ce8-d983c411cad9`（seekdb-local）
- `bot_qq`: `3228649756`
- `reply_probability`: `0.1`
- `history_count`: `40`

---

## 六、调试方法

### 插件日志
- `/tmp/silent_init.log` — 初始化日志（在 langbot-plugin 容器内）
- `/tmp/silent_gate.log` — gate/inject/search 全链路日志（在 langbot-plugin 容器内）
- 读取：`ssh root@nas '/usr/local/bin/docker exec langbot-plugin cat /tmp/silent_gate.log'`

### 日志内容解读
```
[silent] gate: allowed (at) doc_id=chat:xxx    ← @触发
[silent] inject START                            ← inject handler 被调用
[silent] at_text="纳西火锅" sender=小通豆        ← 提取到的查询文本
[silent] search: 2 queries                       ← 搜索 query 数量
[silent] _search_history ENTER: 2 queries        ← _search_history 方法入口
[silent] vector: 10 results                      ← 向量搜索返回数
[silent] keyword: 3 docs from 2 words            ← 关键词搜索：3条文档，2个关键词
[silent] search: 5 results (after dedup)         ← 去重后结果数
  [3.5312] [07-08 07:32] 机器豆: 纳西火锅是...   ← 具体搜索结果（dist, 时间, 发送者, 内容）
[silent] INJECTED 5 search lines, prompt_msgs=65 ← 注入成功
```

### 直接测试搜索
```bash
# 在 langbot 容器内用 ChromaDB 直连测试
scp test.py root@nas:/tmp/ && ssh root@nas '/usr/local/bin/docker cp ...'
# 参考脚本：test_search3.py, test_invoke_embed.py 等
```

### 假数据注入
```python
# 见 seed_btc.py, seed_cat.py, seed_hainan.py 等
# 直接写 ChromaDB，设 timestamp_unix 为历史时间
```

---

## 七、关键 UUID 速查

| 资源 | UUID |
|------|------|
| Dou KB | `da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc` |
| Long KB (LTM) | `992ae019-e8ff-47b1-81f7-94519ef2fb6d` |
| seekdb-local | `62e075f9-733f-458c-8ce8-d983c411cad9` |
| text-embedding-3-small | `c3037d01-1f6e-497a-8fb8-9bc5a69a874d` |
| Pipeline | `dc0ff402-edc3-4dab-8054-d2a855241dea` |
| 测试群 | `group_1104330614` |
| 太空工程师群 | `group_116381172` |

---

## 八、参考文档

- 📄 开发计划：`/home/dou/.claude/plans/nas-langbot-docker-shimmering-bubble.md`
- 📄 开发日志：`docs/bot/silent-observer-dev-journal.md`
- 📄 完整提示词：SSH 到 NAS 执行 `read_prompt.py`
- 📄 测试脚本：`test_search3.py`, `test_invoke_embed.py`, `test_norm.py`, `seed_*.py`

---

## 九、Suggested Skills

后续会话建议加载的 skills：

- **grill-with-docs** — 如有新方案，需要多维面试式评审
- **review-cc-cli** — 代码改动后独立评审
- **diagnose** — 出现异常时系统化排障
- **simplify** — 清理调试日志和冗余代码
