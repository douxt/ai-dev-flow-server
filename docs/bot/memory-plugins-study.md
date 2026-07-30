# 记忆/反思插件深入研究

> 2026-07-11 | 来源:3 个 Explore agent + codegraph 探索 `~/dev/references/bot-evolve-refs/`
> 用途:为 Silent Observer 反思层进化([evolution-roadmap.md](evolution-roadmap.md))提供可借鉴的成熟机制。**本文档记录机制与坐标,不搬运代码**(许可证见末节)。

---

## 一、概览

| 插件 | 生态 | 语言 | 许可证 | 一句话价值 |
|------|------|------|--------|-----------|
| **langbot-longterm-memory** | LangBot 官方 | Python | 无 LICENSE | **最贴场景**:双层记忆+候选审核+作用域隔离+分层架构+测试范式 |
| **memory-lancedb-pro** | OpenClaw(CortexReach) | JS/TS | 无 LICENSE | **反思纠错标杆**:反思分片存储+衰减打分+混合检索 |
| **astrbot_plugin_livingmemory** | AstrBot | Python | **AGPL-3.0** | **薄 handler 架构范例**+图记忆+agent tools |
| **astrbot-plugin-persistent-memory** | AstrBot | Python | MIT | 多重打分(recency/importance/decay)+作用域隔离 |
| **QQ酒馆(QQSillyTavern)** | LangBot | Python | 待查 | 对照组(角色扮演向,已否决) |

---

## 二、langbot-longterm-memory(官方,最该照抄结构)

### 分层架构(对标目标)
```
main.py                              # LongTermMemoryPlugin(BasePlugin) 主类,持状态
store/memory_store.py                # LongTermMemoryStore:存储/作用域/持久化(23 callers)
components/
├── knowledge_engine/memory_engine.py  # LongTermMemoryEngine(KnowledgeEngine) 检索引擎
├── event_listener/memory_injector.py  # MemoryInjector 薄:监听+注入
├── tools/{remember,recall_memory,update_profile,forget}.py  # 每工具一文件(Tool)
├── commands/memory.py                 # !memory 命令(Command)
└── pages/memory_console/              # WebUI(Page)
tests/{store,tools,event_listener,knowledge_engine,commands,pages}/  # 每层配套
```

### 双层记忆 L1/L2
- **L1 = profile**(用户画像,稳定):`update_profile` 工具写
- **L2 = episodes**(情景记忆):`remember` 写、`recall_memory` 读、`forget` 删
- 不把全量聊天灌进上下文,分层存储、按需检索

### 候选审核机制(防噪声固化,最值得借鉴)
- 监听 **`NormalMessageResponded`** 事件,存"候选记忆"到当前 scope
- 候选**不直接改** L1/L2,除非被接受
- 命令:`!memory candidates [page]` 查看、`!memory candidate accept <id>` 落库、`reject <id>` 保留可查但不写
- 对应我们反思层的"≥3 次确认才升级为常驻规则"

### 作用域隔离(scope_key/user_key)
`store/memory_store.py:593` `resolve_user_context()`:
- `session_key = get_session_key(bot_uuid, launcher_type, launcher_id)`
- `user_key = get_user_key(session_key, isolation, bot_uuid)`,`isolation` 默认 `"session"`
- 记忆按 `bot:xxx:group_123` 维度隔离 → 不同群/用户记忆不串

### 持久化 + consolidate
- `_read_json`/`_write_json` 走 `plugin_storage`(如 `_KB_CONFIGS_KEY="kb_configs"`,`memory_store.py:630`)
- `!memory consolidate preview|run`:巩固(合并/去重历史记忆)

### 测试范式(轻量,官方实证)
`tests/store/test_memory_store_episode_lifecycle.py`:
- `_FakeVectorAPI`(:14):内存 dict 模拟向量库 + 确定性假 embedding `[len(t)%7,1.,0.]`
- `_make_plugin`(:34):`LongTermMemoryStore.__new__(...)` **绕过 `__init__`/运行时**,直接塞 `store._api=fake`、`_kb_id`、`_plugin_storage={}`
- `@pytest.mark.asyncio`;依赖仅 `pytest/pytest-asyncio/pytest-cov`

---

## 三、memory-lancedb-pro(反思纠错标杆,JS/TS,⭐4450)

### 反思分片存储 `src/reflection-store.ts`
`storeReflectionToLanceDB()`(:185)把一次反思拆成**四类 payload** 分别存,各带 importance:
| kind | importance | 含义 |
|------|-----------|------|
| `event` | 0.55 | 反思事件本身 |
| `item-invariant` | 0.82 | 不变量(强规则) |
| `item-derived` | 0.78 | 推导项(弱规则) |
| `combined-legacy` | 0.75 | 合并兼容格式 |
- `resolveReflectionImportance()`(:219)
- **向量去重**:`dedupeThreshold=0.97`(:193),combined-legacy 存前先 `vectorSearch` 查相似,>0.97 跳过
- **logistic 衰减模型**:`REFLECTION_DERIVE_LOGISTIC_MIDPOINT_DAYS=3`、`K=1.2`、fallback base weight 0.35(:22-24)

### 衰减打分引擎 `src/decay-engine.ts`
`DEFAULT_DECAY_CONFIG`(:48)+ `scoreOne()`(:192):
- **composite = recency×0.4 + frequency×0.3 + intrinsic×0.3**
- **recency**(:153):Weibull 拉伸指数 `exp(-λ·daysSince^β)`,半衰期 30 天,**重要性调制** `effectiveHL = halfLife·exp(μ·importance)`(μ=1.5);dynamic 记忆衰减快 3×
- **三层 tier 不同 β**:core 0.8(亚指数,衰减慢)/ working 1.0 / peripheral 1.3(超指数,衰减快);各有 decay floor 0.9/0.7/0.5
- **frequency**(:170):对数饱和 `1-exp(-accessCount/5)` + 访问间隔 recentness bonus
- **intrinsic** = importance × confidence
- `applySearchBoost`:检索结果按 composite 加权,新记忆不因零访问被压

### 混合检索 + rerank + 自动捕获
- `src/retriever.ts`:向量 + BM25/FTS 融合,Jina reranker,健康探测 `test()`
- `src/embedder.ts test()`(:1362):探测 embedding 维度(呼应我们的 P0 维度 bug)
- 自动捕获正则:`AUTO_CAPTURE_EXPLICIT_REMEMBER_RE`(index.ts:1239)匹配"记住/别忘了/remember this"多语言触发写入

---

## 四、astrbot_plugin_livingmemory(薄 handler 架构范例,AGPL,⭐279)

`core/event_handler.py` `EventHandler`(:47)——**可测架构黄金范例**:
```python
async def handle_all_group_messages(self, event):
    await self._group_capture.handle_all_group_messages(event)   # 只委托,零逻辑
async def handle_memory_recall(self, event, req):
    await self._memory_recall.handle_memory_recall(event, req)
```
- 逻辑全在**构造注入**的子模块:`GroupCapture`/`MemoryRecall`/`MemoryReflection`/`MessageUtils`(`core/event_handler_modules/`)
- `MemoryReflection`(:24)独立子模块,后台存储任务用 `set`+`asyncio.Lock` 跟踪
- 图记忆(graph_memory)+ agent memory tools(`recall_long_term_memory`/`memorize_long_term_memory`)
- 测试:`monkeypatch.setattr` 替换依赖 + `Fake*` 类 + `AsyncMock`;分 `tests/{integration,smoke,unit}`
- ⚠️ **AGPL-3.0:仅读架构思路,禁复制代码**

---

## 五、astrbot-plugin-persistent-memory(多重打分,MIT)

`main.py` 三类分离:`EmbeddingClient`(嵌入+重试+chunk fallback,:522)、`LanceMemoryStore`(:572 存储)、`MemoryRetriever`(检索)。
- `on_llm_request` 注入召回 / `on_llm_response` 自动捕获
- 混合检索:向量 + BM25(FTS)融合;Jina reranker
- 多重打分:recency / importance / length normalization / time decay
- 作用域:`global` / `session` / `session+global`
- 注入块用 `UNTRUSTED DATA` 包裹(**防提示词注入**——值得抄)
- 上游 = `win4r/memory-lancedb-pro` 的 AstrBot 移植;MIT,可安全参考代码

---

## 六、QQ酒馆(对照组,已否决)

- 角色扮演向:角色卡(`png/`)+ 世界书(`shijieshu/`),文件式存储,非语义检索
- 记忆 = "定期 LLM 总结对话",不是"错误反思→结构化→按需检索"——与需求两码事
- 唯一可借鉴:**世界书"常驻+关键词触发"双通道**(已并入 [evolution-roadmap.md](evolution-roadmap.md) 第三级)
- v0.1.1(2025-02-07)一年未更新,活跃度低

---

## 七、可移植到反思层的机制清单

| 机制 | 来源 | 移植要点 |
|------|------|---------|
| 双层记忆(profile/episode) | longterm-memory | 反思层可类比:通用规则 vs 情景反思 |
| **候选审核**(先候选后接受) | longterm-memory | 防噪声固化,对应"≥3 次确认" |
| **作用域隔离** scope_key | longterm-memory / persistent-memory | 按 bot+group+sender 隔离反思,不串群 |
| **反思分片 + importance 权重** | lancedb-pro reflection-store | invariant(强规则)权重高于 derived |
| **向量去重** 0.97 阈值 | lancedb-pro | 存前查相似,避免重复反思 |
| **衰减打分**(recency/freq/intrinsic) | lancedb-pro decay-engine | 时间衰减 + 重要性调制,老反思自然降权 |
| **薄 handler + 注入式子模块** | livingmemory | 我们地基拆分的架构目标(可测前提) |
| **UNTRUSTED DATA 包裹注入** | persistent-memory | 防提示词注入 |
| **embedding 维度探测** | lancedb-pro embedder.test() | 直接修我们的 P0 维度 bug |
| **__new__ + FakeVectorAPI 测试** | longterm-memory | 我们测试基础设施的范式 |

---

## 八、许可证注意

| 插件 | 许可证 | 可否借鉴代码 |
|------|--------|-------------|
| astrbot_plugin_livingmemory | **AGPL-3.0** | ❌ 仅读思路,禁复制 |
| longterm-memory / memory-lancedb-pro | 无 LICENSE | ⚠️ 参考机制,不直接搬代码 |
| astrbot-plugin-persistent-memory | MIT | ✅ 可参考/借用(注明来源) |
| 官方 SDK(langbot-plugin-sdk) | Apache-2.0(runtime/ 为 AGPL,不传染插件) | ✅ 插件只 import api/entities |
