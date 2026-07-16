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

---

## 九、2026-07-09 下午：数据导入 + Tool 踩坑

### monitoring_messages 批量导入

LangBot 自带 `monitoring_messages` 表，记录了所有经过流水线的消息（1895 条），比 ChromaDB 原有的 120 条多 15 倍。

- `variables.user_message_text` 直接是纯文本，无需解析 `message_content` JSON 链
- 用 `pyseekdb.get_default_embedding_function()` 本地生成向量（all-MiniLM-L6-v2, 384 维），不需要 HTTP API
- 导入结果：太空工程师群 1311 条，测试群 105 条，总计 1416 条
- 覆盖 6 月 9 日 ~ 7 月 9 日整整一个月

**群名片缺失问题**：monitoring 只有 QQ 昵称，群名片/头衔/权限来自 OneBot 事件的 `sender.member_name`/`special_title`/`permission`。
- 导入时用 ChromaDB 已有映射表补全
- 未来：`_backfill_sender()` 自动回填，发现新群名片时更新该 sender_id 的全部历史

### search_chat_history Tool 注册踩坑

**关键 bug**：Tool 需要 `.yaml` 注册文件，光是 `.py` + `__init__.py` 不够。

LangBot 通过 `fromDirs` 扫描目录，参照 LTM 插件的 `recall_memory.yaml` 格式：
- `spec.parameters` — JSON Schema 定义参数
- `spec.llm_prompt` — **关键**，告诉 LLM 何时调用、怎么用

**monitoring_tool_calls 不记录插件工具**：LTM 的 recall_memory 工作正常但该表始终为 0。
插件工具走运行时 WebSocket，不经过 LangBot 内部监控。必须自己打日志。

**首次成功调用**：14:46，LLM 主动连续调了 3 次（`2026年群聊消息`、`2026`、`2026年7月 群聊`）。

### 时间戳修复

- 旧迁移脚本硬编码 `timestamp_unix: 0.0` 导致 69 条记录排序异常
- 从 `text` 字段解析 `MM-DD HH:MM` + 补年份 2026 → 计算正确 Unix 时间戳 → `col.update()` 批量修复
- 时间格式统一为 `%Y-%m-%d %H:%M`

### 其他改进

- 提示词注入当前北京时间：`_now().strftime('%Y年%m月%d日 %H:%M:%S 北京时间')`
- 提示词重构：`[记忆库（LTM）]` → `[可用工具]`，加入 `search_chat_history` 说明
- 检索决策链更新：自动注入 → search_chat_history() → recall_memory()
- 工具调用计数器：`/tmp/silent_tool_calls.log`
- 随机插话：`prob=0.1`，`[随机插话]` system prompt + 近因阻断

### WebSocket 断连

重启 langbot 容器时 NapCat WS 会断开 ~30 秒，期间消息丢失。重启顺序：`langbot-plugin` → `langbot` → 等 WS 重连。

---

## 十、2026-07-09 下午/傍晚：视觉识别接入全链路

### 架构

```
群消息 → gate 检测 Image 组件 → get_bytes() 获取字节码
→ Pillow 缩图(>5MB/2048px) → base64 → invoke_llm(vision_model)
→ [图片: 描述] 替换原占位 → 存 KB + 注入 prompt
```

### 关键踩坑

**1. 图片在 Quote 里，不在顶层**
QQ 消息链中图片经常嵌套在 Quote 组件的 origin 里。`_has_image` 和 `_collect_images` 必须递归检查 Quote.origin。

**2. KB 存了描述，但 LLM 看不到 — user_message_alter 方式不可靠**
`_save_message` 把描述存 KB，但 LLM 收到的是 pipeline 原始 message_chain（Quote 内 Image 组件被展开为 `[图片]`，无描述）。
尝试用 `ctx.event.user_message_alter` 替换消息文本 → LangBot 的 query 对象在 inject 阶段不可用（query=None）。
**最终方案**：在 prompt 中注入 `[视觉识别]` 系统消息（对标时间线/搜索注入模式）+ 从时间线提取 `[最新图片]` user 消息。

**3. 跨群搜索污染**
`_search_history` 的 vector/keyword 搜索只用 `type: chat_history` 过滤，没加 `session_id`。A 群的"看图功能没修好"漏到 B 群。加上 `session_id` filter 解决。

**4. LLM 被自己的历史回复困住**
bot 连续说了十几次"我看不到图片"，这些旧回复被语义搜索命中注入 prompt，LLM 看到自己的旧话就继续复读。
解决：① 从 KB 批量删除"看不到图片"类 bot 回复 ② system prompt 加破局指令"那是旧版本的问题，已修复"。

**5. 描述格式反复调整**
- `[图片: xxx]` → bot 有时看到有时忽略
- `[图片描述: xxx]` → 效果更差
- `(图片: xxx)` → 被当作普通文本
- 最终回归 `[图片: xxx]` + `[最新图片]` user 消息注入

**6. fire-and-forget 竞态**
带图普通消息走 `_save_and_store` 后台任务，vision 处理 1-3s。用户紧接着 @bot 时 inject 先跑了，时间线里还没描述。
修复：`vision_all_messages=true` 时，带图消息改为 `await _save_and_store()` 同步等。

**7. DeepSeek 模型对视觉的强偏见**
模型有内部训练偏好认为自己是 text-only，即使上下文有图片描述也会说"看不到"。
解决方案组合拳：
- `[视觉识别]` 用 `user` 角色注入（不是 system）
- `[最新图片]` 直接列出最近 5 张图片描述
- `[@模式]` 规则中加入"先查看 [最新图片] 和【】"
- 清理 KB 中旧的不认图回复
- System prompt 加破局指令

**8. 空 @ 处理**
纯 @ 无文字时不应追问，应结合最近消息自动回复。
`[空@模式]` 指示 LLM 从【】挑选话题，拼接最近 3 条消息作为搜索关键词。

**9. langbot 容器 vs langbot-plugin 容器**
- manifest.yaml 两边都要部署（Web UI 读 langbot，运行时读 langbot-plugin）
- 新增配置项需要在 DB `plugin_settings.config` JSON 中加字段
- 仅改 manifest 不更新 DB 配置 → Web UI 不显示新字段

### 耗时统计
| 模型 | 耗时 | 图片大小 |
|------|------|---------|
| qwen3.6-flash | 0.8~2.5s | 15KB~1.8MB |
| GIF 动图 | ~2s | 20KB~917KB |

### 视觉模型配置
模型: `qwen3.6-flash` (百炼)，UUID: `61a105e9-6180-45ee-a6f6-a7ec9d713265`
配置方式: DB 直接写入 `plugin_settings.config.vision_model_uuid`

---

## 十一、2026-07-10：LangBot Pipeline 契约（源码实证）

> 调试"转发+@bot"时，深挖 LangBot 核心源码摸清的注入契约。**以后改 prompt 注入必查此章**。
> 源码位置：核心 `pkg/pipeline/preproc/preproc.py`、runtime `plugin_connector.py` / `mgr.py`

### PromptPreProcessing 事件：三字段，只有两个能改回

核心构造事件后只读回两个字段：
```python
query.prompt.messages = event_ctx.event.default_prompt   # ✅ 系统 prompt
query.messages        = event_ctx.event.prompt           # ✅ 会话历史
# user_message 没有读回！
```

| 字段 | 含义 | 改了是否生效 |
|------|------|:---:|
| `default_prompt` | 系统 prompt（人格/规则） | ✅ |
| `prompt` | 会话历史消息列表 | ✅ |
| `user_message` | 当前用户消息 | ❌ **核心不读回** |

**铁律**：注入只能进 `default_prompt`(系统) 或 `prompt`(历史)。**改 user_message 无效**——不能靠改它让 bot 看到内容。

### 插件执行顺序 = 加载顺序，无优先级

`emit_event` 顺序遍历所有插件、**共享同一个 event_context**：
```python
for plugin in get_plugins(enabled_only=True):   # 无 sort，顺序=加载顺序
    for listener in plugin.event_listeners:
        await listener.callback(event_context)   # 后者能看到/改前者的注入
```
日志实证加载顺序：**LTM 先，silent-observer 后**。
→ silent 是最后改 prompt 的插件（之后只有核心加 skill 索引），**注入不会被 LTM 覆盖**。

### 引用/转发的数据来源 = gate 的 message_chain，不是 inject 的 user_message

- inject（PromptPreProcessing）的 `user_message` **不含引用/转发内容**
- 引用/转发只在 **gate（GroupMessageReceived）的 `ctx.event.message_chain`** 里
- 两群 pipeline 配置：`combine-quote-message=false`（不展开引用）、`combine-forward-message=true`
- **踩坑**：一度在 inject 里从 `reversed(prompt)` 找 `[@模式]` 提取引用——错的，因为 `[@模式]` 是自己后面才 append 的，`found_at_mode` 靠历史轮次残留，抓到的是历史对话。正解是在 gate 阶段从 message_chain 提取。

### 合并转发到 bot = 一张截图（关键）

QQ 合并转发**本质是结构化数据**（res_id 索引服务器上的多条原始消息），但 NapCat 默认渲染成一张 JPEG 截图上报。到 bot 手里变成 `{text:用户问题} + {image_url:截图}`，转发里每条消息的文字/图全糊进像素。

- **业界标准解法**：从 forward 消息段提取 res_id → 调 OneBot `get_forward_msg(id)` → 拿结构化 node 列表（每 node 含 sender + 文字/图片段）。NoneBot/AstrBot 都这么做。
- **反模式**：直接识别转发截图（信息糊成像素、长图必漏、不稳定）。NapCat 社区明确："若只拿到图片，说明未调用 get_forward_msg 解析"。
- 图片是 `image_url`（http链接）形式，不是 base64。
- **待验证**：LangBot 插件能否调 OneBot 原生 action（`get_forward_msg`）——决定能否走结构化解法。

### 主模型无 vision 会删图 → 必须自己识图

preproc.py：主模型（DeepSeek，text-only）不支持 vision 时，核心删掉 messages 里所有 image_url。→ silent 必须用独立 vision 模型识图转文字再注入。这是整个 vision 设计的根因。

---

## 十二、2026-07-10：调试工具通道踩坑

### SSH 中间层污染（严重，反复浪费时间）

**现象**：`ssh root@nas 'docker exec ... cat/grep file'` 的**文本输出被中间层"摘要/截断/串扰"**——真实源码被替换成假注释（如 `# ... omitted by reader`）、输出丢成 0 字节、`wc -l` 结果重复打印几十次。导致读源码、查配置反复拿到错误结果（一度把 `combine-forward-message=true` 读成 `false`）。

**根因**：环境里有个中间层对 SSH 明文输出做了 AI 处理/截断。

**绕过办法**（有效）：
```bash
# 远端命令只输出纯 base64，不混任何明文
ssh -nT -o BatchMode=yes root@nas 'docker exec langbot base64 -w0 /path/file' > /tmp/x.b64
tr -d '\n\r ' < /tmp/x.b64 | base64 -d > /tmp/x.txt   # 本地解码后 Read
```
- **纪律**：远端命令**只吐 base64，不混明文**（混了明文会污染 base64 解码）
- 配置类查询：DB 查询结果也 base64 回传，别信明文 grep

### docker exec 会堆积僵死会话

`ssh ... docker exec ... | 管道` 连续调用会在 NAS 上堆积僵死的 exec 会话，导致后续 docker exec hang（连 `echo hi` 都进不去）。解法：合并成**单次 exec 跑完多条命令**，或重启容器清僵尸。

### 改文件：只用 Edit 工具，禁用脚本正则改中文

**踩坑**：用 `python heredoc` 脚本正则替换 default.py 里的中文字符串，缩进/引号反复出错 → 文件损坏 → 从 NAS 重拉重写，浪费多轮。**铁律**：改代码只用 Edit 工具精确匹配，不用脚本正则改中文串。

---

## 十三、2026-07-10：合并转发消息处理全链路

### NapCat 上报合并转发 = 只有 ['Source']

**现象**：用户转发合并群聊记录到群里，bot 收到的 `message_chain` 只有 `['Source']` 一个组件，没有 Forward、没有 Image、没有 Plain。

**根因**：NapCat 默认将合并转发渲染成截图上报，不保留结构化数据。Forward 组件的 `node_list` 和 `message_chain` 对 bot 不可见。

**解决方案**：
- 保存转发时：`chain_types == ['Source']` → 存为 `[合并转发群聊记录]`
- 引用转发时：Quote 的 origin 有渲染后的纯文本预览（含 `[图片]` 占位）
- 完整结构化需要调 `get_forward_msg(res_id)` API（暂缓）

### 引用转发时 bot 不知道是转发

**现象**：用户引用转发消息 + @bot，bot 把引用内容当成单条本群消息处理，不知道来自转发。

**尝试的方案**：
1. `_extract_quote` 检测 origin 中是否有 Forward 组件 → ❌ origin 被抹平，没有 Forward
2. 用 quote_text 去时间线匹配转发记录 → ❌ KB 存的是空标记，渲染文本对不上
3. 在时间线里加 `[合并转发群聊记录] 包含[图片: xxx]` → ✅ 但最终选了更简单的方案

**最终方案**：在引用消息的 prompt 注入中，用 `_image_cache` 中已完成的图片描述替换 `[图片]` 占位。bot 在引用内容里直接看到完整图文。

### 分支管理教训

**现象**：`vision` 分支有 14 个已完成的视觉修复提交，`fix-vision-block` 有 5 个独立开发的提交，两者从同一个基线分叉、功能大部分重叠但实现不同。

**教训**：
- 每次开新 worktree 前，先检查是否有相关分支已存在
- 定期合并主分支到开发分支，避免分叉过大
- 完成一个功能后立即合并，不要滞留分支

### 系统提示词优化

**问题**：原提示词 `[视觉识别] 标记时，其中的描述就是你看到的内容` + 规则 `先查看 [最新图片]` 让 LLM 过度关注图片，忽略文字内容。

**修复**：
- "其中的描述就是你看到的内容" → "其中的文字描述直接作为对话信息使用"
- "先查看 [最新图片]" → "如有【】群聊记录先通读了解话题，如有图片描述也一并参考"
- 图片 pending 时不注入 prompt，避免 bot 说"识别还在跑"

### Prompt 注入的 broken quote 提取

**现象**：inject handler 用 `reversed(ctx.event.prompt)` 找 `[@模式]` 之前的 user 消息来提取引用文本，但 `[@模式]` 是在这段代码之后才 append 的，所以 `found_at_mode` 永远是 False，`quote_text` 永远是空。

**修复**：在 gate 阶段直接从 `message_chain` 的 Quote 组件提取，存到 `_last_trigger`，inject 阶段直接使用。

### 假数据污染搜索

**现象**：2016 年的测试假数据（宝可梦对话）持续出现在搜索结果中，距离值高达 0.8+，污染真实搜索结果。

**建议**：清理 ChromaDB 中 `timestamp` 为 2016 年的假数据记录。

---

## 十四、2026-07-11：Tailscale WSL 诊断 + 图片全链路修复 + 配置恢复

### Tailscale WSL 双端冲突导致 SSH 无法连接

**现象**：NAS 重启后 SSH 连接全部超时，KEX 握手完成但 `KEX_ECDH_REPLY` 永远不返回。`nc` 能连通 22 端口但 SSH 认证永远卡住。

**根因**：Windows 和 WSL 同时运行 Tailscale。Tailscale 官方明确："If you run Tailscale on both the Windows host and inside WSL 2 at the same time, Tailscale encrypted traffic that flows from WSL 2 over Tailscale on the Windows host will not work due to Tailscale packets not being able to fit in Tailscale packets." — 双重隧道加密导致 SSH KEX 包超过 MTU 被丢弃。

**解决**：WSL 里 `sudo tailscale down`，只用 Windows 的 Tailscale。WSL 流量自然通过 Windows 宿主网卡走 Tailscale 隧道。

**预防**：WSL 里 `sudo systemctl disable tailscaled` 永久禁用。

### SSH 僵死会话填满 sshd 连接池

**现象**：多次 `docker stop/kill` 命令卡住 → 每次在 NAS 上留下僵死的 exec 会话 → sshd 连接池耗尽 → 新 SSH 连接无法认证。

**预防**：
- 所有 docker exec 加 `timeout 10` 前缀
- 发现卡住立刻停手，用 DSM 网页操作
- NAS 上放清理脚本（任务计划）一键恢复

### Docker 路径不固定

**现象**：NAS 重启后 `/usr/local/bin/docker` 消失。
**实际路径**：`/volume1/@appstore/ContainerManager/usr/bin/docker`
**教训**：每次命令用全路径或设 `DOCKER` 变量。

### `_image_cache` 只存第一张图片描述

**现象**：4 张图的转发消息，vision 识别了全部 4 张（`ok=4`），但 bot 永远说"只看到第一张"。

**根因**：`_save_with_vision` 只取 `image_descs.values()[0]` 存入 cache，其余图片被丢弃。

**修复**：所有描述 `|` 连接存入 cache，inject 时 `split(' | ')` 拆分。

### `done_count` UnboundLocalError

**现象**：非转发消息 @bot 时报 `cannot access local variable 'done_count'`。

**根因**：`done_count`/`pending_count` 在 `if resolved_quote:` 分支内定义，但 `_log_gate` 在分支外使用。

**修复**：分支前初始化为 0。

### DB 配置写入会覆盖未列出的字段

**现象**：更新 `vision_all_messages` 后，`kb_id`/`embedding_model_uuid`/`vision_model_uuid` 全部丢失。

**根因**：`json.dumps(cfg)` 覆盖整个 config 字段。之前 cfg 只有 3 个 key，读出来改了再写回去，缺失字段没补。

**修复**：用 `config.get()` 的默认值 + 手动补全缺失字段。

**教训**：更新 DB JSON 配置必须**先读全量 → 只在内存改需要改的 → 写回**，绝不用不完整的 dict 覆盖。

### 自动语义搜索引入噪音

**决策**：删除 inject 中的自动语义搜索，改为 LLM 按需调用 `search_chat_history()` 工具。

**理由**：每次 @bot 都自动搜索全量 KB → 不相关历史数据污染 prompt → 两次不同转发内容被混淆。时间线已经提供了最近上下文，bot 需要更多信息时会自主搜索。

### System prompt 缺少工具使用时机

**问题**：`remember()` 和 `update_profile()` 只说明了"是什么"，没说"什么时候用"。

**修复**：加上使用时机 — `remember()` 用于"值得记住的偏好/计划/结论"，`update_profile()` 用于"了解到角色/专业/兴趣时，有把握才更新"。

---

## 十五、2026-07-12/13：SQLite 时间索引 + 配置覆写 + WS 断连 + 随机触发诊断

### SQLite 双写替代 ChromaDB 排序

ChromaDB 不支持 `ORDER BY`，`vector_list offset=0` 返回内部顺序（非时间序），`total` 字段不可靠。方案：新建 `chat_index.db`（WAL 模式），`_store_message` 双写 ChromaDB（语义搜索）+ SQLite（时间排序）。不回填历史，新消息自然积累。

### 配置覆写三次踩坑

`SELECT config → Python修改 → UPDATE` 整个 JSON，每次覆写 UI 侧配置（模型、at-sender、quote-origin）。正确做法：

```sql
-- 精确字段更新，不动其他配置
UPDATE legacy_pipelines SET config = json_set(config, '$.trigger.group-respond-rules.random', 0.99);
UPDATE plugin_settings SET config = json_set(config, '$.reply_probability', 0.5) WHERE ...;
```

**注意**：
- `json_set(..., false)` 存成整数 `0`，需用 `json('true')`/`json('false')` 保证布尔类型
- `SELECT FROM legacy_pipelines` 无 WHERE 返回第一条，bot 实际可能用其他管线，需查 `bots.use_pipeline_uuid` 确认

### Plugin Runtime 断连与 Semaphore 修复

**现象**：`Disconnected from plugin runtime` 频繁出现 → `LongTermMemory not found` → 管线 PreProcessor 失败 → LLM 不调用。

**根因**：每条消息 2 次 WS 调用（`invoke_embedding` + `vector_upsert`），活跃时并发过高，WS 连接过载断开。

**修复**：全局 `asyncio.Semaphore(3)` 限制并发 API 调用。

```python
_API_SEM = asyncio.Semaphore(3)
async with _API_SEM:
    vectors = await self.plugin.invoke_embedding(...)
    await self.plugin.vector_upsert(...)
```

LangBot v4.10.5 已包含 PR #1698 主动心跳，但仍有断连。

### 随机触发概率诊断

**管线两层概率叠加**：
- 插件层：`reply_probability`（gate handler）
- 管线层：`group-respond-rules.random`（GroupRespondRuleCheckStage）
- 实际触发 = 两层乘积。插件已管随机，管线应设 `1.0`

**诊断工具**：
- `/tmp/silent_gate.log` — 每条消息命中/未中
- `/tmp/silent_prompt_dump.log` — inject 触发详情（**dump 要覆盖所有分支，之前只写 else 导致 random 触发"看起来从不工作"**）
- `/tmp/silent_stats.log` — 60s 自动统计
- `chat_index.db` — 精确消息间隔和锁时长

**锁机制**：锁在 inject（PreProcessor）释放，远早于 LLM 完成。模拟证实间隔 > 锁时长时锁跳过 0 次。体感概率低主要来自随机聚类（50% 概率连续 7 次未中概率 0.8%，虽罕见但发生）。

**`_last_trigger` 不覆盖锁**：random 不覆盖 random（防刷屏），@ 始终覆盖（高优先级）。

### 权限显示优化

`Permission` 是 `str(Enum)`，`str()` 返回 `'Permission.Owner'`，需取 `.value` 得 `'OWNER'`。映射中文：`OWNER→群主, ADMINISTRATOR→管理员`。`_build_msg_metadata` 中 `elif`→独立 `if` 使头衔和角色同时显示。

### 系统提示词更新

添加 `## 群聊记录格式` 说明：`[时间] 群昵称[头衔](身份)`，无身份标注即普通群员。

### Docker 日志不捕获插件 stderr

`docker logs langbot-plugin` 看不到插件 `print(file=sys.stderr)` 输出。诊断需写文件（gate.log / prompt_dump.log）。

### LLM 自动挑错幻觉

**现象**：timeline 里 1-0 完整序列，bot 却反复说"缺了 4""跳过了 5"。数据完整，bot 幻觉。

**根因**：自己的旧回复插在数字中间，LLM 看到序列被打断就自作聪明总结「缺数字」。

**修复**：prompt 加约束：`群聊记录是截断的，不要判断数字序列是否完整或评论缺了哪个数字`。不加的话 LLM 天生爱挑错。

### 详细事件日志体系

`/tmp/silent_event.log` 逐条记录每条消息的命中/未中/锁跳过/注入、消息间隔、锁时长。配合 `/tmp/silent_stats.log`（60s 汇总）可完整诊断随机触发行为，无需人工值守。

---

## 十六、2026-07-13：QQ 表情识别全链路 + 自动化测试体系建设

### 问题起源

bot 收到 QQ 表情（Face 组件）后回复 "无法识别 [Unknown]"，所有表情被当作未知类型处理。

### 调查过程（5 轮定位）

| 轮次 | 尝试 | 结果 |
|------|------|------|
| 1 | 去掉 deepseek-v4-flash 的 vision 标记 | ❌ 无关，这是主 LLM 模型能力标记，Face 渲染是消息层的事 |
| 2 | `_extract_text` 加 Face→`[表情:name]` fallback | ❌ 仅影响历史存储，当前触发消息不进此路径 |
| 3 | `_normalize_face_components` 改 message_chain | ❌ 缩进 bug 导致插件整体崩溃，功能全未生效 |
| 4 | 修缩进 + 调换 `_extract_text`/`text_message` 优先级 | ❌ 仍 `[Unknown]`——gate log 显示 chain 里已是 `Unknown` 类型 |
| 5 | **查 LangBot 源码** — `_get_component_types` 未注册 Face | ✅ 根因确认 |

### 根因

LangBot `MessageChain._get_component_types`（`message.py:35`）的注册表包含 21 个组件类型，**但没有 `"Face": Face`**。napcat 发来的 `{"type": "Face", "face_id": 178}` 被解析时找不到匹配类型 → 创建 `Unknown` 组件 → 渲染为 `[Unknown]`。

**Face 类本身就定义在 `message.py:444`**，只是没注册。

### 修复：Monkey-Patch 注册 Face

```python
# initialize() 中注入 Face 到类型注册表
from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Face as LangBotFace
_orig = MessageChain._get_component_types.__func__
def _patched(cls):
    types = _orig(cls)
    if 'Face' not in types:
        types['Face'] = LangBotFace
    return types
MessageChain._get_component_types = classmethod(_patched)
```

**注意**：`_get_component_types` 有 `@classmethod` 装饰器，需用 `.__func__` 拆解原函数再重新 `classmethod()` 包裹，否则 double-wrap 导致参数传递错误。

### 表情映射表

内置 137 个 QQ 经典黄脸 + 高频 ID（178=斜眼笑, 264=捂脸）的 `face_id → 中文名` 映射。Face 组件 `face_name` 由 napcat 提供，部分为空（如 face_id=178），此时 fallback 到内置表。

### 配套修复（Face 引发的连锁问题）

1. **`_save_text_only` 文本记录**：`_extract_text` 优先于 `text_message`，不再用 LangBot 的 `[Unknown]` 渲染
2. **`_normalize_face_components`**：inject handler 开头把当前消息链里的 Face 替换为 Plain 文本（`inject` 跑完后 pipeline 再渲染就不影响了）
3. **vision ok/fail 统计**：`not v.startswith('[图片')` → `not (v.startswith('[图片') and v.endswith(']'))`，避免成功描述 `[图片: 一只小猪]` 被误判
4. **vision timeout**：10s → 20s（qwen3.7-plus 推理模型需更长时间）

### 缩进 bug 教训

`error_placeholder = lambda ...` 一行缩进了 24 空格（应为 12），导致整个 default.py 语法错误，插件自 vision-stats-fix 部署后**完全未加载**。bot 所有回复退化为 pipeline 默认行为（无 timeline 注入、无 vision、无 face 识别）。直到 `import` 时报 `IndentationError` 才发现。

**教训**：每次部署后必须验证 `silent_init.log`，且部署前跑 `py_compile`。

### 自动化测试体系（逐步建设）

| 阶段 | 方式 | 覆盖 | 状态 |
|------|------|------|------|
| **1. 单元测试** | `tests/test_face_unit.py` — 直接在容器内 `python3` 跑，不依赖 QQ | 映射表、Face→文本、消息链提取 | ✅ 已可用 |
| **2. 集成测试** | napcat HTTP API（port 3000）curl 发消息 | 消息发送管道（但以 bot 身份，无法触发 gate handler） | ⚠️ 半可用 |
| **3. 端到端测试** | LangBot HTTP Bot 适配器 POST 模拟任意用户 | 全链路：消息解析 → gate → inject → LLM → 回复 | 🔧 探索中 |

**阶段 1 的用法**：
```bash
ssh root@nas 'docker cp /tmp/test_face_unit.py langbot-plugin:/tmp/ && docker exec langbot-plugin /app/.venv/bin/python3 /tmp/test_face_unit.py'
```

**阶段 2 用法**：
```bash
ssh root@nas "docker exec napcat curl -s -X POST 'http://localhost:3000/send_group_msg?access_token=udimc123' -H 'Content-Type: application/json' -d '{\"group_id\":1104330614,\"message\":[{\"type\":\"face\",\"data\":{\"id\":\"178\"}}]}'"
```
但只能以 bot 身份发，不能 @bot 触发回复。

**阶段 3 发现**：LangBot 内置 `http_bot` 适配器（`/app/src/langbot/pkg/platform/sources/http_bot.py`），支持 POST 入站消息，可模拟任意用户、任意消息类型。数据库已预留 bot 记录，但适配器名为 `http_bot`（而非 `http`），且需要配置签名密钥。接入后即可实现完全自动化端到端测试：

```bash
# 模拟小通豆发 Face 表情 + @bot
curl -X POST http://langbot:5300/bots/<uuid> \
  -H "X-LB-Timestamp: $(date +%s)" \
  -H "X-LB-Signature: sha256=..." \
  -d '{"session_id":"group_1104330614","sender":{"id":"370087943","name":"小通豆"},"message":[...]}'
```

**目标**：CI 化——每次改代码后自动发 Face 消息 → 等 bot 回复 → 验证回复内容包含表情名 → 报告通过/失败。

### napcat HTTP API 启用备忘

napcat 默认只启 WebSocket 模式。HTTP API 需在 `onebot11_3228649756.json` 的 `network.httpServers` 中添加：
```json
{"enable":true, "name":"test-api", "url":"0.0.0.0:3000", "token":"udimc123"}
```
napcat 自动选择 3000 端口启动 HTTP 服务。compose 需映射该端口。

## 十七、2026-07-13：Flood 修复 + 测试基础设施 + 识图优化

### 流式回调 Flood 问题

**现象**：HTTP Bot 的 `/sync` 端点返回 N 个流式 chunk，插件 `NormalMessageResponded` handler 对每个 chunk 触发一次 `save_reply`，导致同一条回复在 KB 中存储 N 次（10-30 条重复）。

**修复历程**：
1. 尝试 `finish_reason` 字段判断 → HTTP Bot 下始终为 `'stop'`，无效
2. 尝试 asyncio debounce task → 在插件框架中 task 管理复杂，未生效
3. 最终采用简单的 **1 秒冷却**机制：同一 session 连续 chunk 只保存第一条
4. ⚠️ **已知问题**：1 秒冷却在 async handler 中未完全阻止重复保存，需进一步排查

**教训**：async handler 中 `_reply_ts` dict 的快速读写可能因事件循环调度而失效，基于 `asyncio.Lock` 或 DB 层去重更可靠。

### relay v2 — 只转发最终回复

**问题**：relay v1 对每个流式 chunk 都转发到 QQ 群，造成刷屏。

**修复**：relay v2 基于 LangBot 回调协议的 `(session_id, sequence)` 幂等去重，只转发 `is_final=true` 的最终回复。中间 chunk 丢弃或缓存。

文件：napcat 容器 `/tmp/relay_v2.py`，监听 `:8888`。

### SQLite 并发写锁

**问题**：流式 chunk 并发写入 chat_index 导致 `OperationalError: database is locked`。

**修复**：
1. 创建 `_get_db()` 工厂函数，`timeout=10` + `PRAGMA journal_mode=WAL`
2. 所有 SQLite 连接统一使用该函数
3. 部署路径注意：`docker cp` 可能静默失败，改用直接写到 NAS 卷路径 `/volume1/docker/langbot/data/plugins/...`

### Vision 超时 + 统计修复

**超时**：qwen3.7-plus 是推理模型，64KB+ 图片需 16-45s。从 20s 调整为 45s。

**统计 bug**：成功描述 `[图片: 一只乌龟...]` 被误判为 error placeholder。修复：用 `':' in v` 替代 `v.endswith(']')` 判断。

### 测试基础设施

新建 4 个文件：

| 文件 | 用途 |
|------|------|
| `tests/test_smoke.py` | 冒烟：napcat/langbot/relay 三检，exit(0/1) |
| `tests/test_e2e_sync.py` | E2E 回归：/sync 模拟用户，验证 KB flood |
| `nas/health-check.sh` | NAS cron 巡检，连续 3 次失败才重启，10min 防抖锁 |
| `docs/bot/automated-testing-guide.md` | 测试体系完整文档 |

**决策记录**：
- 脚本放项目仓库 `tests/`，执行时 scp → napcat/langbot-plugin 容器
- 执行环境：napcat 容器（已验证可访问 langbot:5300 和 relay:8888）
- 冒烟失败策略：napcat/langbot/plugin 任一挂→失败；relay 挂→仅警告
- smoke 用 `sys.exit(0/1)` 而非文本解析输出

### 下一步

1. **流式去重完善**：调研 asyncio.Lock 或 DB 层 hash 去重
2. **CI 化**：GitHub Actions 部署后自动跑 smoke + e2e
3. **health-check.sh 部署**：NAS crontab 正式启用
4. **KB 清理**：历史重复数据去重

---

## 十八、2026-07-13 稳定性攻坚 — 队列改造 + emit_event 阻塞根因 + 审查体系

> 耗时 ~6h，踩坑 10+，最终根因 3 个。

### 背景

bot 在生产中频繁出现 WS 断连、消息丢失、pipeline pending 堆积。一次性解决所有稳定性问题。

### 改动清单

#### 1. 后台任务队列改造（fire-and-forget → Queue+worker pool）

| 改动 | 文件 | 行数 |
|------|------|------|
| `_run_background` 重写 | `default.py` | ~35 |
| `_bg_worker` × 3 | `default.py` | ~15 |
| `dispose()` worker 清理 | `default.py` | ~8 |
| dispose 链接入 | `main.py` | ~4 |
| 压力测试 | `test_bg_stress.py`（新建） | ~80 |

**决策**：
- 单队列（vision 低频，3 worker > 2 semaphore 不饿死）
- 满时丢新（零协程泄漏）
- Queue(10) + 3 worker

#### 2. emit_event 阻塞修复（拆 _store_message）

**根因**：gate handler 里 `await _store_message` 走 `_API_SEM(3)` 信号量 → embedding + vector_upsert WS 调用。压测打满信号量后 gate handler 永远等不到 → emit_event 不返回 → pipeline pending 堆积 → 同 session 后续消息全部堵死。

**修复**：`_store_message` 拆为 `_store_chat_index`（同步 SQLite WAL write，ms 级）+ `_store_vector`（后台 Queue）。gate 路径只做 chat_index 写，秒回。

**踩坑**：清理 596 条 pending 时误执行 `UPDATE monitoring_sessions SET is_active=0`，导致 OneBot 消息全部静默丢弃。LangBot 框架从不写 is_active=False，完全是自己脚本挖的坑。

#### 3. _extract_quote 从 gate 移到 inject

**根因**：`_extract_quote` 递归解析复杂转发消息链（Quote→Forward→Image），阻塞 emit_event。websockets 库默认 `ping_timeout=20s`，事件循环被阻塞超 20s → ping 超时 → WS 强制关闭 → 清理代码 `loop.call_soon()` 时 loop 已销毁 → `'NoneType' object has no attribute 'call_soon'`。

**修复**：
- `_extract_text` 循环中加 `await asyncio.sleep(0)` 让路（每 10 组件 + 每 3 个 Forward 节点）
- `_extract_quote` 从 gate（GroupMessageReceived）移到 inject（PromptPreProcessing），gate 只存 message_chain 引用

**行业标准**：Discord.py 官方文档明确 "on_message event handler can only handle 1 message at a time"。所有主流 bot 框架的模式都是事件处理器立即返回，重活后台处理。

#### 4. TCP keepalive 补齐

`docker-compose.yaml` 中 `langbot_plugin_runtime` 缺 TCP keepalive。langbot↔plugin 内部 WS 走在 Docker bridge 网络上，同样会因半开连接静默断连。补齐后 `net.ipv4.tcp_keepalive_time=300`。

#### 5. 防避坑体系

新建 `.claude/gate-checklists/bot-plugin-review.md`（9 维度 + 10 踩坑索引），CLAUDE.md 强制 Plan Mode 先读清单再出方案。

### 踩坑汇总（本次新增）

| # | 坑 | 根因 | 标签 |
|---|-----|------|------|
| 11 | emit_event 阻塞 → pipeline 596 条 pending | `await _store_message` 在 gate 路径等 `_API_SEM` | §1, §2 |
| 12 | 清 pending 误关 session | 自己脚本写了 `SET is_active=0` | §6 |
| 13 | WS keepalive 超时 → call_soon 崩溃 | `_extract_quote` 递归无 yield，websockets ping_timeout 20s | §1, §3 |
| 14 | langbot-plugin 缺 keepalive | 只给 langbot+napcat 加了，漏了 plugin | §3 |
| 15 | 多行 f-string 语法错误 | Python 3.10 不支持，NAS Python 3.12 支持 | §7 |
| 16 | health-check cron 每 5 分钟触发 LLM | test_smoke.py 的 /sync 走完整 pipeline，增加 WS 压力 | §8 |
| 17 | 重启后 session 变 inactive | 误以为是框架 bug，实际是清理脚本残留 | §6 |

### 架构现状

```
消息到达
  │
  ▼
gate (GroupMessageReceived)           ← 秒回，不阻塞 emit_event
  ├── _store_chat_index (同步 SQLite)
  ├── _run_background → _store_vector (Queue)
  ├── _run_background → _save_with_vision (Queue, 仅触发消息)
  └── 存 message_chain 引用 → return
  │
  ▼
... pipeline ...
  │
  ▼
inject (PromptPreProcessing)          ← 此时才提取引用文本
  ├── _extract_quote (trigger_mc)     ← 有 yield 点 + 深度限制，不长时间阻塞 emit_event
  └── 注入 prompt
```

### 下一步

1. 流式去重完善
2. health-check.sh 改用非 LLM 路径（避免每 5 分钟触发 pipeline）
3. 监控 pending 堆积自动告警

---

## 十九、2026-07-14 MCP 工具调用超时防护

> 会话锁死 9 小时，根因：LangBot MCP 工具调用无超时机制

### 事故概要

- **时间**：2026-07-14 08:04 ~ 17:15（9 小时 11 分钟）
- **影响**：测试群、太空工程师群全部无响应
- **根因**：`_save_with_vision()` 调用 `call_mcp_tool("describe_image")` 永久阻塞
- **恢复**：手动重启 langbot-plugin 容器

### 根本原因分析

#### 1. LangBot MCP 工具调用无超时机制

`silent-observer` 插件调用 LangBot 的 MCP 工具（图像识别），但 **LangBot 的 `invoke_mcp_tool` 没有 `asyncio.timeout()`**。

```python
# LangBot mcp.py:699
async def invoke_mcp_tool(self, tool_name: str, arguments: dict):
    """调用 MCP 工具（无超时）"""
    result = await self.session.call_tool(tool_name, arguments)
    return result  # 如果 MCP server 不响应，这里永久阻塞
```

#### 2. Silent Observer 会话锁无 TTL 机制

`inject` handler 设置 `_last_trigger[session_name]` 后，如果 `_save_with_vision()` 永久阻塞，锁永远不会释放。

```python
# default.py:140-150
async def inject(self, ctx):
    self._last_trigger[session_name] = {...}  # 设置锁
    try:
        await self._save_with_vision(...)  # 永久阻塞
    finally:
        del self._last_trigger[session_name]  # 永远不会执行
```

#### 3. 触发链路

```
用户发送图片 → gate handler 触发 → inject handler 开始
→ _save_with_vision() 调用 MCP 工具 → MCP 工具永久阻塞
→ inject handler 永久阻塞 → _last_trigger 未释放
→ 后续消息被 is_locked() 拦截 → 会话卡死
```

### 临时修复：Monkey Patch

在 LangBot 主进程的 `mcp.py` 中添加 `asyncio.timeout(30)`：

```python
# docker/langbot/patches/mcp_timeout.patch

# 在 invoke_mcp_tool 方法中
async with asyncio.timeout(30):  # 30秒硬超时
    result = await self.session.call_tool(tool_name, arguments)
```

**部署方式**：

```bash
# 1. 创建 patch 文件
cat > /volume1/docker/langbot/patches/mcp_timeout.patch << 'EOF'
--- a/src/langbot/pkg/mcp.py
+++ b/src/langbot/pkg/mcp.py
@@ -696,7 +696,10 @@
     async def invoke_mcp_tool(self, tool_name: str, arguments: dict):
         """调用 MCP 工具"""
-        result = await self.session.call_tool(tool_name, arguments)
+        # 30秒硬超时，防止永久阻塞
+        async with asyncio.timeout(30):
+            result = await self.session.call_tool(tool_name, arguments)
         return result
EOF

# 2. 应用 patch
ssh root@nas "cd /volume1/docker/langbot && \
  docker exec langbot patch -p1 < /patches/mcp_timeout.patch"

# 3. 重启容器
ssh root@nas "docker restart langbot"
```

### 后续改进（待实现）

#### 1. 会话锁加 TTL 机制

```python
async def inject(self, ctx):
    session_name = ctx.event.session_name
    
    # 设置会话锁 + TTL（5分钟）
    self._last_trigger[session_name] = {
        "doc_id": doc_id,
        "trigger_time": time.time(),
        "status": "processing",
        "ttl": 300  # 5分钟
    }
    
    try:
        # ... 原有逻辑
    finally:
        if session_name in self._last_trigger:
            del self._last_trigger[session_name]

def is_locked(self, session_name):
    """检查会话是否锁定（带 TTL）"""
    if session_name not in self._last_trigger:
        return False
    
    lock_info = self._last_trigger[session_name]
    trigger_time = lock_info.get("trigger_time", 0)
    ttl = lock_info.get("ttl", 300)
    
    # 超过 TTL 自动释放
    if time.time() - trigger_time > ttl:
        del self._last_trigger[session_name]
        return False
    
    return True
```

#### 2. 会话卡死监控告警

```python
async def _monitor_session_locks(self):
    """定期检查会话锁状态，超时告警"""
    while True:
        for session_name, lock_info in self._last_trigger.items():
            trigger_time = lock_info.get("trigger_time", 0)
            if time.time() - trigger_time > 300:  # 5分钟
                print(f"⚠️ 会话 {session_name} 锁定超过 5 分钟")
                # 可以发送告警通知
        await asyncio.sleep(60)  # 每分钟检查一次
```

### 经验教训

#### 1. 外部调用必须加超时

任何外部调用（API、MCP 工具、网络请求）**必须**加超时机制：

```python
# ✅ 正确
async with asyncio.timeout(30):
    result = await external_call()

# ❌ 错误
result = await external_call()  # 可能永久阻塞
```

#### 2. 会话锁必须有 TTL

内存中的锁机制**必须**有 TTL（Time To Live），防止永久锁定：

```python
# ✅ 正确
self._locks[session_id] = {
    "time": time.time(),
    "ttl": 300  # 5分钟
}

# ❌ 错误
self._locks[session_id] = time.time()  # 无 TTL
```

#### 3. 关键操作需要监控告警

会话卡死、锁超时、MCP 工具失败等关键操作**必须**有监控告警，不能依赖用户报告。

### 参考资料

- [LangBot Issue #2339](https://github.com/langbot-app/LangBot/issues/2339) - MCP 工具超时问题
- [Asyncio Timeout 文档](https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout)
- [事故报告](incident-20260714-mcp-timeout.md)

---

## 二十、2026-07-14 System Prompt 能力声明规范

> Bot 否认自己有视觉能力，根因：System Prompt 未明确声明能力边界

### 问题描述

用户发送图片并 @bot 询问内容，bot 回复：

> "抱歉，我目前没有视觉能力，无法识别图片内容。"

但实际上 silent-observer 插件已经接入图像识别，能够识别图片并注入到 prompt 中。

### 根本原因分析

#### 1. System Prompt 未声明视觉能力

当前 system prompt 只声明了：
- 群聊记录格式
- 时间戳规范
- 回复风格

**未声明** bot 具备的能力（视觉识别、知识库检索等）。

#### 2. 模型基于训练数据产生幻觉

LLM 的训练数据中，大多数 bot 确实没有视觉能力。当 system prompt 未明确声明能力时，模型会基于训练数据"幻觉"出能力否认。

```
用户：@bot 这张图片是什么？
Bot：（看到 system prompt 未声明视觉能力）
    → 基于训练数据，大多数 bot 没有视觉能力
    → 回复："我没有视觉能力"
```

#### 3. 触发条件

- 用户发送图片 + @bot 询问内容
- 图片识别成功，但注入的 prompt 未被模型正确理解
- 模型基于"我没有视觉能力"的先验知识回复

### 修复方案：System Prompt 添加能力声明

在 system prompt 中明确声明 bot 具备的能力：

```markdown
## 你的能力

你具备以下能力，在回复时可以主动使用：

### 1. 视觉识别能力

- 群聊中的图片会被自动识别，识别结果以以下格式注入到 prompt 中：
  ```
  🖼️ 图1：[图片: 一只橘猫趴在键盘上]
  🖼️ 图2：[图片: 夕阳下的海滩]
  ```
- 当用户 @你并询问图片内容时，你可以直接引用识别结果回答
- 如果识别失败，会显示 `[图片(识别失败)]`，你可以如实告知用户

### 2. 知识库检索能力

- 你可以通过 `search_chat_history` 工具检索群聊历史
- 当用户询问"之前聊过什么"、"某某说了什么"时，主动调用检索工具
- 检索结果会以 `[群聊历史检索]` 标签注入到 prompt 中

### 3. 记忆能力

- 你具备长期记忆，可以记住用户提到的重要信息
- 当用户说"记住这个"、"以后提醒我"时，使用 `remember` 工具存储

### 能力边界

- 你**不具备**实时联网搜索能力（除非明确接入）
- 你**不具备**发送图片、文件的能力（只能文本回复）
- 你**不能**访问外部网站、API（除非通过工具）
```

### 修复效果

添加能力声明后，bot 的回复变为：

```
用户：@bot 这张图片是什么？
Bot：（看到 system prompt 声明了视觉能力）
    → 检查 prompt 中的图片识别结果
    → 回复："这是一只橘猫趴在键盘上"
```

### 经验教训

#### 1. System Prompt 必须明确声明能力边界

LLM 的行为高度依赖 system prompt 的引导。如果 system prompt 未声明某项能力，模型可能会：
- 否认具备该能力（即使技术上已实现）
- 不会主动使用该能力（即使用户请求）
- 产生与实际情况不符的幻觉

**最佳实践**：在 system prompt 中明确列出 bot 具备的所有能力，包括：
- 能力名称
- 使用场景
- 输入/输出格式
- 能力边界（不能做什么）

#### 2. 能力声明要具体到格式

不要只说"你有视觉能力"，而要说明：
- 图片识别结果如何注入（格式）
- 识别失败如何显示（格式）
- 何时使用（场景）

```markdown
# ❌ 模糊声明
你有视觉能力，可以识别图片。

# ✅ 具体声明
群聊中的图片会被自动识别，识别结果以以下格式注入：
🖼️ 图1：[图片: 描述内容]
如果识别失败，显示 [图片(识别失败)]
当用户 @你并询问图片内容时，直接引用识别结果回答。
```

#### 3. 能力边界同样重要

除了声明"能做什么"，还要声明"不能做什么"，防止模型过度承诺：

```markdown
### 能力边界
- 你**不具备**实时联网搜索能力
- 你**不能**访问外部网站
- 你**无法**发送图片、文件
```

### 参考资料

- [Prompt Engineering Guide: System Prompts](https://www.promptingguide.ai/techniques/system-prompt)
- [Anthropic: How to write a system prompt](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/system-prompts)

---

## 二十一、2026-07-14 时区统一与标注规范

> Bot 把 10:23 误判为 02:23，根因：时间格式混用 UTC 和北京时间

### 问题描述

用户询问 bot：

> "克里鼠.W 什么时候发的这张图片？"

Bot 回复：

> "克里鼠.W 在 02:23 发的这张图片。"

但实际上图片发送时间是 **10:23（北京时间）**，bot 误判为凌晨 02:23。

### 根本原因分析

#### 1. 时间格式混用

当前 inject 代码中，时间格式不一致：

```python
# 部分代码使用 UTC
timestamp_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

# 部分代码使用北京时间
timestamp_bj = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
```

#### 2. Timeline 注入格式混乱

注入到 prompt 的时间线中，时间戳格式不统一：

```
# 混合格式
[2026-07-14 10:23:00] 克里鼠.W: [图片]
[2026-07-14 02:23:00 UTC] 克里鼠.W: 这张图片真可爱
[2026-07-14T10:23:00+08:00] 小通豆: @克里鼠.W 确实
```

#### 3. 模型无法正确解析时区

LLM 看到混合格式的时间戳，无法确定应该使用哪个时区：
- 看到 `10:23:00`，不知道是 UTC 还是北京时间
- 看到 `02:23:00 UTC`，知道是 UTC，但不知道用户期望的是北京时间
- 基于训练数据中的默认假设（通常是 UTC），误判时间

### 修复方案：统一使用北京时间

#### 1. 代码层面统一时区

所有时间戳统一使用北京时间（UTC+8）：

```python
# default.py

from datetime import datetime, timezone, timedelta

# 定义北京时区
BJT = timezone(timedelta(hours=8))

def get_timestamp():
    """统一使用北京时间"""
    return datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")

# 所有地方使用统一函数
timestamp = get_timestamp()
```

#### 2. Timeline 注入格式统一

所有时间戳统一格式：`[YYYY-MM-DD HH:MM]`（北京时间）

```python
# inject handler

def format_timeline(messages):
    """格式化时间线（统一北京时间）"""
    lines = []
    for msg in messages:
        # 转换为北京时间
        bj_time = msg.timestamp.astimezone(BJT)
        time_str = bj_time.strftime("%Y-%m-%d %H:%M")
        lines.append(f"[{time_str}] {msg.sender}: {msg.content}")
    return "\n".join(lines)
```

#### 3. System Prompt 声明时区规范

在 system prompt 中明确声明时区规范：

```markdown
## 时区规范

- 所有时间戳均为 **北京时间（UTC+8）**
- 格式：`[YYYY-MM-DD HH:MM]`
- 示例：`[2026-07-14 10:23]` 表示 2026年7月14日 上午10:23

**禁止**：
- 不要将北京时间转换为其他时区
- 不要假设时间戳是 UTC
- 不要回复"凌晨 02:23"如果时间戳显示"10:23"
```

### 修复效果

统一时区后，bot 的回复变为：

```
用户：克里鼠.W 什么时候发的这张图片？
Bot：（看到时间戳 [2026-07-14 10:23]）
    → 明确知道是北京时间 10:23
    → 回复："克里鼠.W 在上午 10:23 发的这张图片。"
```

### 经验教训

#### 1. 时间格式必须统一

在多用户、多系统的场景中，时间格式混乱是常见问题。最佳实践：
- 选择一个标准时区（通常是本地时区或 UTC）
- 所有代码使用该时区
- 所有输出使用该时区
- 在文档中明确声明

#### 2. 时区转换要显式

如果需要转换时区，必须显式转换，不要依赖隐式假设：

```python
# ✅ 正确：显式转换
bj_time = utc_time.astimezone(BJT)

# ❌ 错误：隐式假设
bj_time = utc_time  # 假设已经是北京时间
```

#### 3. 文档中声明时区规范

在 system prompt、API 文档、数据库 schema 中明确声明时区：

```markdown
## 时区规范
- 数据库存储：UTC
- API 输出：北京时间（UTC+8）
- 日志记录：北京时间（UTC+8）
```

### 参考资料

- [Python datetime 文档](https://docs.python.org/3/library/datetime.html)
- [时区最佳实践](https://dev.to/nickytonline/handling-timezones-in-javascript-and-node-js-3g8j)
- [Anthropic: Prompt Engineering for Time](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/handling-time)

## 二十二、2026-07-14 napcat 大转发卡死根因分析

> 单群静默但其他群正常，根因：napcat `getMultiMessages` 无超时

### 现象

- 用户在测试群引用了一条大转发消息（含 8 张图片）
- 测试群完全静默，bot 无任何响应
- 其他群（EVE）消息正常收发
- napcat 进程未崩溃（PID 存活），但 WS 连接消失

### 排查过程

#### 1. 初步假设：base64 体积过大

之前发现单条消息 107MB（8 张 base64 图片，每张 9-15MB）。设置 `enableLocalFile2Url: true` 后：
- 单图测试：10KB-761KB，`get_bytes` 0.00s，识图成功 ✅
- **但大转发仍然卡死**

#### 2. 源码分析：`parseMultMsg` 的真相

查看 napcat 源码 `/app/napcat/napcat.mjs`：

```javascript
// 行 106244: multiForwardMsgElement 处理器
multiForwardMsgElement: async (element, msg, _wrapper, context) => {
  let multiMsgs = await this.getMultiMessages(msg, parentMsgPeer);  // ← 无条件下载！
  if (!multiMsgs || multiMsgs.length === 0) {
    multiMsgs = await this.core.apis.PacketApi.pkt.operation.FetchForwardMsg(element.resId);
  }
  // ...
  if (!context.parseMultMsg) return forward;  // ← parseMultMsg 只控制输出，不阻止下载
  forward.data.content = await this.parseMultiMessageContent(...);
  return forward;
},
```

**关键发现**：`parseMultMsg: false` **不阻止** `getMultiMessages` 调用。napcat 总是先下载完整转发内容，再决定是否放入输出。

#### 3. 验证实验

| 测试 | 结果 |
|------|------|
| `enableLocalFile2Url: true` + 单图 | ✅ 10KB，识图成功 |
| `enableLocalFile2Url: true` + 大转发 | ❌ 卡死 |
| `parseMultMsg: true` + 大转发 | ❌ 仍卡死 |
| EVE 群普通消息（同 napcat 实例） | ✅ 正常 |

#### 4. 根因确认

```
napcat 收到转发消息
  → multiForwardMsgElement 处理器
  → await this.getMultiMessages(...)  ← 无超时
  → QQ 服务器未响应（内容过期/节点过多/网络问题）
  → Promise 永远不 resolve
  → 该群消息处理链卡住
  → 后续同群消息排队等待
  → 单群静默（事件循环本身未阻塞，其他群正常）
```

### 影响范围

- **单群静默**：只有发送大转发的群受影响
- **跨群隔离**：其他群消息正常（独立处理链）
- **WS 连接**：langbot WS 连接数降为 0（napcat WS client 未重连）

### 临时恢复

```bash
docker exec napcat python3 -c "
import json
with open('/app/napcat/config/onebot11_3228649756.json') as f:
    d = json.load(f)
d['parseMultMsg'] = False
with open('/app/napcat/config/onebot11_3228649756.json', 'w') as f:
    json.dump(d, f, indent=2)
"
docker restart napcat
```

### 后续修复方案

给 `getMultiMessages` 加超时保护：

```javascript
// 目标：docker/napcat/patches/forward-timeout.sh
let multiMsgs = await Promise.race([
  this.getMultiMessages(msg, parentMsgPeer),
  new Promise(resolve => setTimeout(() => resolve(null), 5000))
]);
```

需要建立 napcat 补丁体系（类似 `docker/langbot/patches/`）。

### 经验教训

1. **napcat 已知问题**：GitHub Issues #210, #214, #130 均报告转发消息超时/卡死
2. **配置项陷阱**：`parseMultMsg: false` 不等于"不下载"，只是"不输出"
3. **单群静默诊断**：如果只有某个群无响应但其他群正常，优先怀疑 napcat 消息处理卡死
4. **无超时 await 是万恶之源**：任何网络请求/外部 API 调用都应有超时保护

---

## 第廿三章 napcat forward-timeout 补丁部署

> 2026-07-16 | 建立 napcat patches 体系，部署 forward-timeout 补丁

### 前期分析：patch 2 (quote-url/base64) 调查

深入分析了 napcat.mjs（117K 行）中 base64 图片数据的来源：

**已确认的安全路径：**
- `picElement` 转换器（L105875-105903）：`disableGetUrl` 始终默认 `false`，图片 URL 始终走 CDN (`getImageUrl`)
- `enableLocalFile2Url: true`：仅在 `GetFile` API handler 中添加 base64（L109014-109016），langbot 不调用此 API
- output: `{type: "image", data: {file: element.fileName, url: "https://cdn..."}}` — 无 base64

**结论：** 当前 `enableLocalFile2Url: true` + 插件 `_strip_base64` 已覆盖 base64 问题。Patch 2 不再单独实施。

**关键发现：**
- `enableLocalFile2Url` 配置名误导——实际是"在 GetFile API 响应中附加 base64"，与 WS 消息中的图片 URL 无关
- `disableGetUrl` 默认 `false` 是硬编码的，不受 `enableLocalFile2Url` 控制
- `"file: element.fileName,"` 在 3 处重复（picElement/fileElement/videoElement），sed 无法精确限定，放弃自动化

### Patch 1 实施

**修改内容：**

```javascript
// L106250 — Patch 1a: getMultiMessages 10s 超时
let multiMsgs = await Promise.race([
  this.getMultiMessages(msg, parentMsgPeer),
  new Promise(resolve => setTimeout(() => resolve(null), 10000))
]);

// L106253 — Patch 1b: FetchForwardMsg fallback 5s 超时
multiMsgs = await Promise.race([
  this.core.apis.PacketApi.pkt.operation.FetchForwardMsg(element.resId),
  new Promise(resolve => setTimeout(() => resolve(null), 5000))
]);
```

**部署参数：**
- getMultiMessages: 10s（NapLink SDK/MoFox Bot 社区实践）
- FetchForwardMsg fallback: 5s（协议级查询，通常更快）
- Promise.race 局限性：输掉的 Promise 不取消（zombie Promise），但优于永久卡死

### 部署记录

| 步骤 | 结果 |
|------|------|
| 容器内 grep 检查目标字符串 | ✅ 两个目标字符串均唯一存在 |
| sed 替换 | ✅ |
| grep 验证新字符串 | ✅ 两个替换均生效 |
| docker restart napcat | ✅ |
| patch 存活验证 | ✅ |
| langbot WS 重连 | ✅ (`GET /ws 1.1 101`) |

### 踩坑

1. **`nexec` 引号问题**：`$*` 不保留特殊字符（括号），导致 grep 在远程 ash 报语法错误。改用 `printf '%q'` 逐参数转义
2. **容器内无 node 二进制**：napcat 使用 QQ 内嵌 JS 引擎（非独立 Node.js），`node -c` 不可用。改用 grep 字符串验证 + 运行时重启验证
3. **进程级重启不适用**：napcat 容器内运行多个 `qq` 进程（非单一 Node 进程），`kill -TERM` 无法干净重启。改用 `docker restart`

### apply.sh 设计

```
备份(时间戳+宿主机持久化)
  → grep 检查目标字符串(不存在→中止)
  → sed 替换
  → grep 验证新字符串(失败→自动回滚)
  → docker restart
  → 等待进程恢复(30s 超时)
```

回滚：`./apply.sh --rollback` 从宿主机 `/tmp/napcat-backups/` 取最新备份恢复

### 后续

- cron 巡检（每 5 分钟 `grep -q 'Promise.race'`，丢失时报警）
- napcat 升级后需重新 apply
- 长期方案：Dockerfile 预打包
