# LangBot 插件开发参考（v4.0+）

> 2026-07-11 | 摘自官方文档 [docs.langbot.app](https://docs.langbot.app/zh/plugin/dev/tutor)
> 用途：Silent Observer 进化开发速查，重点标注实现反思层要用的 API

---

## 一、架构基础

v4.0 引入 **Plugin Runtime**（插件运行时），管理插件生命周期，两种模式：
- `stdio`：LangBot 源码直接启动（未带 `--standalone-runtime`），个人/轻量环境
- `websocket`：容器内运行（官方 docker-compose），生产环境。Runtime 独立容器，5401 端口

> **当前 Silent Observer 部署在容器里 = websocket 模式**，Runtime 在 langbot-plugin 容器。

插件 = `main.py`（生命周期）+ 若干**组件（Components）**。组件类型：

| 组件 | 用途 |
|------|------|
| **EventListener** | 监听流水线事件（每插件仅 1 个，内部可注册任意多事件） |
| **Command** | 响应 `!` 开头命令 |
| **Tool** | 供 LLM Function Calling 调用 |
| **KnowledgeEngine** | 知识库索引/检索 |
| **Parser** | 文档解析（PDF/Word） |
| **Page** | WebUI 侧边栏自定义页 |

---

## 二、目录结构

```
HelloPlugin/
├── assets/icon.svg              # 插件市场图标
├── components/
│   ├── event_listener/
│   │   ├── default.py           # 事件处理逻辑（= 当前 Silent Observer 的核心文件）
│   │   └── default.yaml
│   ├── commands/{info.py, info.yaml}
│   └── tools/{get_weather.py, get_weather.yaml}
├── main.py                      # 插件主类，继承 BasePlugin
├── manifest.yaml                # 元信息 + 配置格式定义
├── requirements.txt
└── .github/workflows/release.yml # 版本号变更自动发 Release
```

---

## 三、CLI（langbot_plugin 包）

```bash
pip install -U langbot_plugin      # 安装 CLI + SDK
lbp init [PluginName]              # 初始化插件（交互填 Author/Description）
lbp comp EventListener             # 生成组件（Command/Tool/EventListener/KnowledgeEngine/Parser/Page）
lbp run                            # 连接运行中的 LangBot 调试（需 Runtime 监听 5401）
lbp build                          # 打包为可分发 zip
lbp publish                        # 发布到插件市场
lbp rt                             # 独立启动 Runtime（control 5400，debug 5401）
```

若 `lbp` 找不到：`python -m langbot_plugin.cli.__init__ init HelloPlugin`

调试：复制 `.env.example` → `.env`，改 `DEBUG_RUNTIME_WS_URL`，`lbp run`。

---

## 四、事件监听器写法（v4.0）

```python
from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events, context

class DefaultEventListener(EventListener):
    async def initialize(self):
        await super().initialize()

        @self.handler(events.PersonMessageReceived)
        async def handler(event_context: context.EventContext):
            await event_context.reply(
                platform_message.MessageChain([
                    platform_message.Plain(text="Hello!"),
                ])
            )
```

- 事件类型定义在 `langbot_plugin.api.entities.builtin.events`
- `EventContext.event` 是具体事件对象；完整事件列表见[流水线事件](https://docs.langbot.app/zh/plugin/dev/apis/pipeline-events)
- 当前 Silent Observer 用的 `GroupMessageReceived`（gate）、`PromptPreProcessing`（inject）均在此列表

---

## 五、通用 API（实现反思层的关键）

访问方式：组件内 `self.plugin.xxx`，事件处理器内 `event_context.xxx`。

### ★ RAG API — 反思层存储/检索直接复用

```python
# 生成向量
vectors = await self.plugin.invoke_embedding(embedding_model_uuid, ["文本1", "文本2"])

# 向量写入（反思记录入库）
await self.plugin.vector_upsert(
    collection_id="reflections",           # 独立 collection，与聊天 KB 分离
    vectors=[[...]], ids=["refl_001"],
    metadata=[{"error_type": "假设过多", "created_at": 1700000000, "importance": "high"}],
    documents=["反思正文"],                 # 支持全文/混合检索需传
)

# 向量搜索（回答前检索相关反思）
results = await self.plugin.vector_search(
    collection_id="reflections",
    query_vector=[...], top_k=3,
    search_type="hybrid",                   # vector | full_text | hybrid
    query_text="当前消息文本",
    filters={"importance": {"$in": ["high", "mid"]}},  # Chroma 风格 where
)
# 返回 [{"id", "score", "metadata"}]，文本需从 metadata 取

# 向量删除（去重/衰减清理）
await self.plugin.vector_delete(collection_id="reflections", filters={"error_type": {"$eq": "过时"}})
```

> **过滤器注意**：Chroma/Qdrant/SeekDB 存完整 metadata 可任意字段过滤；Milvus/pgvector 仅存 `text/file_id/chunk_uuid`，其他字段过滤被静默忽略。当前用的是 **seekdb-local**（`62e075f9...`），支持完整过滤。
> 运算符：`$eq $ne $gt $gte $lt $lte $in $nin`

### ★ LLM 调用 — 生成反思 / LLM-as-Judge

```python
llm_message = await self.plugin.invoke_llm(
    llm_model_uuid="...",                   # 如 qwen3.6-flash 的 UUID
    messages=[provider_message.Message(role="user", content="把这段交互压缩成结构化反思...")],
    funcs=[], extra_args={},
)
```

### 持久化存储 — 轻量状态（计数/开关/日限）

```python
await self.plugin.set_plugin_storage("key", b"value")   # 仅本插件可读，值须 bytes
data = await self.plugin.get_plugin_storage("key")
keys = await self.plugin.get_plugin_storage_keys()
await self.plugin.delete_plugin_storage("key")
# set/get/delete_workspace_storage — 跨插件共享
```

### 知识库 API（高层封装，不受流水线限制）

```python
kbs = await self.plugin.list_knowledge_bases()          # [{uuid, name, description}]
results = await self.plugin.retrieve_knowledge(kb_id, query_text, top_k=5, filters=None)
```

### 其他常用

```python
await event_context.reply(message_chain, quote_origin=False)   # 回复
await event_context.get_bot_uuid()
await event_context.set_query_var(key, value) / get_query_var(key)
await self.plugin.send_message(bot_uuid, target_type, target_id, message_chain)  # 主动发消息
await self.plugin.get_llm_models()                             # 列出 LLM UUID
await self.plugin.list_tools() / call_tool(name, params, session, query_id)
config = self.plugin.get_config()                              # 读 manifest 配置
```

---

## 六、反思层落地映射

| 反思层需求 | 用哪个 API |
|-----------|-----------|
| 反思记录入库 | `invoke_embedding` + `vector_upsert`（collection=`reflections`） |
| 回答前检索反思 | `vector_search`（hybrid + filters） |
| LLM 生成结构化反思 | `invoke_llm`（qwen3.6-flash） |
| 去重/衰减清理 | `vector_search` 找相似 + `vector_delete` |
| 日限计数/开关 | `set/get_plugin_storage` |
| 触发注入到 prompt | 在 `PromptPreProcessing` 事件里拼接 |

**结论**：反思层所需 API 官方全部提供，无需引入外部向量库，直接复用宿主 seekdb-local。

---

## 七、发布流程

1. `lbp build` 打包
2. push 版本号变更 → GitHub Actions 自动发 Release
3. `lbp publish` 或在 LangBot 仓库提 Issue 审核上架[插件市场](https://space.langbot.app/market)

---

## 八、官方资源

| 资源 | 链接 |
|------|------|
| 插件开发教程 | https://docs.langbot.app/zh/plugin/dev/tutor |
| 通用 API | https://docs.langbot.app/zh/plugin/dev/apis/common |
| 流水线事件列表 | https://docs.langbot.app/zh/plugin/dev/apis/pipeline-events |
| 事件监听器 | https://docs.langbot.app/zh/plugin/dev/components/event-listener |
| 消息平台实体 | https://docs.langbot.app/zh/plugin/dev/apis/messages |
| 插件 SDK 源码 | https://github.com/langbot-app/langbot-plugin-sdk |
| 官方插件示例 | https://github.com/langbot-app/langbot-plugin-demo |
| AI 辅助开发 Skill | https://github.com/TyperBody/skills-LangBotplugin |

---

## 九、可参考的记忆类开源插件

见 [evolution-roadmap.md](evolution-roadmap.md) 参考项目清单，重点：

| 插件 | 生态 | 亮点 | 许可证 |
|------|------|------|--------|
| [langbot-longterm-memory](https://github.com/langbot-app/langbot-longterm-memory) | **LangBot 官方** | 双层记忆(L1 profile+L2 episodes) + 候选审核机制 + `!memory` 命令 | 待查 |
| [memory-lancedb-pro](https://github.com/win4r/memory-lancedb-pro) | OpenClaw | **支持自我反思和纠错** + 混合检索 + rerank | 待查 |
| [astrbot_plugin_livingmemory](https://github.com/lxfight-s-Astrbot-Plugins/astrbot_plugin_livingmemory) | AstrBot | 277★ 动态记忆 + 图组件 + agent memory tools | AGPL-3.0 |
| [astrbot-plugin-persistent-memory](https://github.com/zhanzhao2/astrbot-plugin-persistent-memory) | AstrBot | LanceDB + 混合检索 + 多重打分(recency/importance/time decay) | MIT |
