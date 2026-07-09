# Silent Observer 插件开发日志

> 2026-07-08 ~ 2026-07-09 | KB 归档 + 混合搜索 全链路开发

---

## 一、架构演进

### 初版：buffer 滑动窗口

```
消息 → buffer（插件 JSON 存储）→ inject 注入最近 N 条
```

- buffer 40 条滑动窗口，溢出丢弃
- 注入时全量注入最近 N 条时间线
- 问题：旧消息静默丢弃，无法回溯

### 终版：KB 唯一存储 + 混合搜索

```
消息 → KB（ChromaDB）→ inject: 时间线 + 混合搜索（Vector + Keyword RRF）
                     → search_chat_history Tool（LLM 自主检索）
```

- 删除 buffer，消息直写 KB
- 注入双通道：`vector_list` 时间线 + 混合搜索（向量 + 关键词 RRF 融合）
- 全面对标 LTM 的 API 模式（`invoke_embedding` + `vector_search`）

---

## 二、关键技术决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 存储引擎 | ChromaDB（复用 Dou KB） | LangBot 已有基础设施，无需新建 |
| Embedding 模型 | seekdb-local（384 维） | 本地免费，不消耗 API |
| 写入策略 | 触发消息同步写，其余 fire-and-forget | 解决 gate→inject 竞态，确保时间线完整 |
| 时间线排序 | `timestamp_unix` 客户端排序 | fire-and-forget 下 ChromaDB 插入序 ≠ 时间序 |
| 语义搜索 | Vector（L2 归一化）+ Keyword（jieba 分词 + ChromaDB $contains）RRF 融合 | 纯向量搜索语义区分力不足，关键词通道补强 |
| 距离阈值 | 5.0 | 归一化查询向量 + 未归一化存储向量场景下的合理值 |
| 文档去重 | SHA-256 内容哈希 ID | 确定性幂等，upsert 不会重复写入 |
| 会话隔离 | `session_id` + `$and` filter | 防止跨群信息泄露 |
| 搜索去重 | 排除 timeline 已有消息 + 排除触发消息 | 避免近期消息污染检索结果 |
| 中文分词 | jieba | n-gram 产出大量无意义碎片词 |
| 时区 | 北京时间 UTC+8 | 容器默认 UTC |
| 注入结构 | `[@模式]/[随机插话]` → `【时间线】` → `[群聊历史检索]` → 近因阻断 → 用户消息 | 清晰分层 |

---

## 三、关键踩坑记录

### 1. LangBot 双容器架构
- **现象**：修改代码后重启 `langbot` 容器不生效
- **根因**：插件运行在独立容器 `langbot-plugin` 中，需单独重启
- **教训**：`docker ps` 确认所有相关容器，部署后两个都要重启

### 2. `__pycache__` 缓存导致旧代码运行
- **现象**：部署新代码后 `set_plugin_storage` 等已删除的方法仍在被调用
- **根因**：Python `.pyc` 字节码缓存，容器重启也不会清理
- **教训**：每次部署前 `find -name __pycache__ -exec rm -rf {}`

### 3. launcher_type.value vs launcher_type
- **现象**：`AttributeError: 'str' object has no attribute 'value'`
- **根因**：`GroupMessageReceived` 事件中 `launcher_type` 已是字符串，不是枚举。`PromptPreProcessing` 中 `.value` 才需要
- **教训**：不同事件类型的字段类型不同，需逐一确认

### 4. Query 对象无 text_message/message_chain
- **现象**：`ctx.event.query.text_message` 返回空
- **根因**：`PromptPreProcessing.query` 对象的文本需通过 `get_query_vars()['user_message_text']` 获取（对标 LTM 的做法）
- **教训**：不要假设 query 对象有直接文本属性，用 `QueryBasedAPIProxy.get_query_vars()`

### 5. 向量未归一化导致搜索距离膨胀
- **现象**：直接 ChromaDB `query()` 距离 0.02→0.67，但 `vector_search` 返回距离 15+
- **根因**：`invoke_embedding` 返回未归一化向量（norm≈5.9），存储向量 norm≈3.8，squared L2 距离膨胀
- **解决**：查询向量 L2 归一化，阈值从 1.0 放宽到 5.0

### 6. if/else 缩进 bug 导致搜索未执行
- **现象**：`search: 2 queries` 日志出现但搜索实际未运行
- **根因**：`kb_results = await ...` 写在了 `else` 分支而非 `if queries:` 分支
- **教训**：大段重写后用 `python3 -m py_compile` + 逐行审查缩进

### 7. LangRAG 引擎未安装导致报错
- **现象**：`Plugin langbot-team/LangRAG not found`
- **根因**：`QueryBasedAPIProxy.retrieve_knowledge` 走 `RETRIEVE_KNOWLEDGE_BASE` 需要 KB 配置的引擎，Dou KB 配置了 LangRAG 但未安装
- **解决**：改用 `self.plugin.invoke_embedding` + `self.plugin.vector_search` 直连 ChromaDB（对标 LTM 的 search_episodes）

### 8. pipeline KB 列表误加入
- **现象**：把 Dou KB 加入 pipeline `knowledge-bases` 列表后报 LangRAG 缺失
- **根因**：pipeline 的 KB 列表是给 pipeline 级别 RAG 用的，会加载 KB 引擎。我们用的是插件直连 ChromaDB，不需要加入
- **教训**：不要把插件自用的 KB 加入 pipeline 配置

### 9. 测试噪音污染搜索
- **现象**：反复测试同一问题，KB 中积累大量相似查询，搜索结果被测试噪音淹没
- **根因**：每次 @bot 测试都在 KB 新增一条消息，语义高度相似的测试消息压制了原始内容
- **教训**：测试用假数据，测完清理；或用全新话题验证

### 10. 时间线覆盖全部 KB 数据
- **现象**：删除大量 07-09 测试消息后，KB 只剩 07-08 的 ~27 条，全部在 40 条时间线窗口内，搜索 dedup 后无结果
- **根因**：过度清理导致时间线窗口覆盖全量数据
- **教训**：正常运行时 KB 数万条，时间线不会覆盖全量。保留足够数据用于测试

---

## 四、Prompt 工程迭代

| 版本 | 结构 | 问题 |
|------|------|------|
| v1-v3 | "两套记忆系统" | Bot 仍以 LTM 为唯一记忆，说"记忆库没有" |
| v4 | "二者都是你的记忆，同等地位" | Bot 说"LTM没有但在全量记忆里找到了" |
| v5 | "同一个记忆库，不区分来源" | Bot 否认时措辞混乱 |
| v6 | 分开：[记忆库(LTM)] + [群聊历史检索] | Bot 自造"全量上下文历史" |
| v7 | "+不要使用全量上下文历史等说法" | 措辞统一为"群聊记录" |

**最终原则**：LTM = 记忆库（手动），群聊历史检索 = 早期记录（自动），各司其职。

---

## 五、System Prompt 最终结构

```
[身份] 机器豆...
[记忆库（LTM）] 手动管理：recall_memory/remember/update_profile
[群聊历史检索] 自动注入，标记 [群聊历史检索]
  判断：先群聊检索 → 再记忆库 → 任一有即告知
[群聊历史] 【】时间线
[规则] 1. 先回顾 2. 回复方式 3. 平等 4. 联网 5. 纯文本 6. 不@
```

## 六、注入 Prompt 最终结构

```
System Prompt + LTM 画像
<memory-records>         ← LTM 事件记忆
[@模式] / [随机插话]      ← 触发标记
【 最近N条时间线 】       ← vector_list
[群聊历史检索] 早期记录   ← 混合搜索
近因阻断（随机专用）
用户消息
```

---

## 七、测试数据管理

- 假数据插入：直接写 ChromaDB，用 `col.add()`，ChromaDB 自动嵌入
- 假数据时间戳设为历史日期（如 2026-01-09），自动在时间线之外
- 测试完用 `col.delete(ids=[...])` 精确删除
- 对话历史通过 `monitoring_messages`/`monitoring_sessions` 表清除
- KB 通过 ChromaDB 直接操作 `col.delete()`

---

## 八、部署检查清单

- [ ] 两个容器都重启：`docker restart langbot langbot-plugin`
- [ ] 清 `__pycache__`：`find -name __pycache__ -exec rm -rf {}`
- [ ] 插件配置确认：`kb_id` + `embedding_model_uuid` 都已填
- [ ] System prompt 已更新：`read_prompt.py` 确认
- [ ] 检查 `silent_init.log`：`kb_enabled=True`
- [ ] 检查 `silent_gate.log`：gate/inject/search 链路完整
