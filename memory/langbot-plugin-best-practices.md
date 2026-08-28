---
created: pre-2026-07
name: langbot-plugin-best-practices
description: LangBot v4 插件开发最佳实践与踩坑记录
metadata: 
  node_type: memory
  type: reference
  originSessionId: ce5705ee-9449-4465-9669-d16ceba28729
---

# LangBot v4 插件开发最佳实践

> 2026-07-07 | 基于官方文档 + 实测踩坑

## 核心架构

- **三层进程模型**：主进程 → Plugin Runtime → 插件子进程（stdio/WebSocket 通信）
- 每个插件独立子进程，进程隔离，崩溃不影响主服务
- 插件安装后自动 pip install `requirements.txt`

## manifest.yaml 强制规则

| 规则 | 后果 |
|------|------|
| `metadata.label` 必须有 `en_US` | Pydantic 校验失败，插件静默跳过 |
| `metadata.description` 必须有 `en_US` | 同上 |
| `metadata.author` 必须匹配 `^[a-zA-Z0-9_-]+$` | 校验失败 |
| `metadata.name` 必须匹配 `^[a-zA-Z0-9-]+$` | 校验失败 |
| `spec.components` 必须声明所有组件 | 组件不被加载 |
| 配置项 `label`/`description` 也需要 `en_US` | UI 渲染异常 |

## 各组件的 YAML 结构

### EventListener
```yaml
# components/event_listener/default.yaml
apiVersion: v1
kind: EventListener
metadata:
  name: default
  label:
    en_US: MyListener
    zh_Hans: 我的监听器
spec:
execution:
  python:
    path: default.py    # 必填！否则组件实例为 null
    attr: DefaultEventListener  # 必填！
```

### Tool
```yaml
apiVersion: v1
kind: Tool
metadata:
  name: my_tool
  label:
    en_US: MyTool
spec:
  parameters:
    type: object
    properties: {}
    required: []
  llm_prompt: 'Description for LLM'
execution:
  python:
    path: my_tool.py
    attr: MyTool
```

### Command
```yaml
apiVersion: v1
kind: Command
metadata:
  name: mycmd
  label:
    en_US: MyCommand
spec:
execution:
  python:
    path: mycmd.py
    attr: MyCommand
```

## 已踩坑实录

### 1. 缺 `en_US` → 静默失败
- **根因**：manifest.yaml 的 label/description 只有 zh_Hans，Pydantic 校验要求 en_US 必须存在
- **表现**：插件文件存在，DB 记录 enabled=1，但运行时日志无任何错误
- **定位**：手动 `/app/.venv/bin/python3 -m langbot_plugin.cli.__init__ run -s --prod` 看到 `label.en_US: Field required`

### 2. 缺 `requirements.txt` → 不被发现
- **根因**：运行时安装阶段用 `pip install -r requirements.txt` 来识别插件
- **表现**：`Installed dependencies` 日志中从不出现，`launch all plugins` 计数少 1
- **解决**：即使无依赖也加空 `requirements.txt`

### 3. 缺 `spec.components` → 组件未加载
- **根因**：manifest.yaml 未声明组件，运行时无从发现
- **表现**：main.py 正常执行，但 EventListener 从未初始化

### 4. 缺 `spec.execution.python` → 组件实例 null
- **根因**：组件 YAML 未声明 path/attr，运行时不知道加载哪个文件
- **表现**：组件被识别但 `component_instance: null`
- **参考**：LongTermMemory 的 YAML 显式指定 `path` 和 `attr`

### 5. 非官方 `lbp build` 打包可能有问题
- 用 `shutil.make_archive` + 改名 `.lbpkg` 可行，但必须确保内部无嵌套目录
- 推荐最终用 `lbp build` 打包发布

## 开发调试黄金法则

1. **开发时用 debug 模式**：`lbp run` 通过 WebSocket 热加载，无需重启
2. **排查静默失败**：手动运行 `python -m langbot_plugin.cli.__init__ run -s --prod` 看 Pydantic 报错
3. **加文件日志**：`print()` 到 stderr 可能被吞，写 `/tmp/` 或插件目录下文件
4. **对比参考插件**：找 LongTermMemory 等官方插件对比 manifest 格式
5. **验证顺序**：manifest 语法 → 插件进程启动 → 组件实例化 → 事件触发

## 事件驱动关键点

- `EventContext.set_query_var`/`get_query_var` 可跨事件共享数据
- `BaseEventModel.query` 在插件运行时中被 exclude，不可直接访问
- `prevent_default()` 阻止默认行为，`prevent_postorder()` 阻止后续插件
- 同一 query 生命周期内，事件按 Pipeline 顺序依次触发

## 安装与部署

- Docker 环境：Runtime 容器名默认 `langbot-plugin`（非 `langbot_plugin_runtime`）
- `.lbpkg` = zip 文件，包含 manifest.yaml + main.py + components/
- 安装 API：`POST /api/v1/plugins/install/local`（需先 `/preview`）
- 重启 Runtime 即可重载所有插件：`docker restart langbot-plugin`

## 2026-07-07 新增踩坑

### 6. `GroupNormalMessageReceived` 时 @ 已被删除

- **根因**：Pipeline 的 `GroupRespondRuleCheckStage`（atbot 规则）匹配到 @ 消息后，会**把 At 组件从 message_chain 中删除**（`atbot.py: remove_at()`）。后续 `ChatMessageHandler` emit 的 `GroupNormalMessageReceived` 事件里，`message_chain` 已不含 @。
- **表现**：插件拿到「被去除了 @ 的消息链」，`is_at` 永远是 False。即使 @消息，也被概率拦截，LLM 从未调用。
- **定位过程**：
  1. 初始怀疑：monitoring DB 显示消息 `status=success` 但 `monitoring_llm_calls` 无新记录 → LLM 未被调用
  2. 读源码发现 `ChatMessageHandler.handle()` 会 emit `GroupNormalMessageReceived`，`prevent_default()` 则 skip LLM
  3. 读 `resprule/atbot.py` 确认 `remove_at()` 修改了 `query.message_chain`
  4. napcat 日志可确认消息正常接收，但 LLM 调用计数始终不涨
- **解决**：改用 `GroupMessageReceived`（在 `process_query` 中 emit，早于 Pipeline 执行，@ 尚未被删除）。从源头拦截，管道都不走，更省资源。
- **教训**：**事件时机决定数据状态**。同一条消息在不同事件中，message_chain 的内容可能已被前面的 stage 修改。做 @ 检测要在最早的 `GroupMessageReceived` 而不是 `GroupNormalMessageReceived`。

### 7. `docker logs` 在 Synology NAS 上可能永久超时

- **根因**：Synology Docker 使用定制 `db` 日志驱动（非标准 json-file），`docker logs` 命令在管道传输时易卡死
- **表现**：`ssh root@nas "docker logs langbot --tail 5"` 永远不返回；但 `docker ps`、`docker exec` 正常
- **绕过**：通过 `docker exec` + 数据库查询（查 `monitoring_messages`、`monitoring_llm_calls`）代替读日志
- **napcat 日志正常**（用 json-file 驱动），可作为消息收发的旁证

### 8. 插件 `enabled=0` 不等于不运行

- **根因**：插件 DB 中 `enabled=0` 但 Runtime 在重启后仍然加载了部分 handler
- **表现**：`plugin_settings.enabled=0` 但 `binary_storages` 中仍有 buffer 数据持续写入
- **教训**：不要依赖 DB enabled 字段判断插件是否活跃，以实际行为（如 buffer 是否增长）为准

### 9. Pipeline respond rules `regexp: [".+"]` + `random: 0` 的诡异行为

- **规则执行顺序**：`atbot → prefix → random → regexp`（按文件名排序，OR 逻辑，首个匹配即放行）
- `regexp: [".+"]` 匹配一切非空消息，放在最后相当于「兜底放行所有」
- 但实测该组合存在不确定性，建议不依赖 regexp 做放行，用插件 `GroupMessageReceived` 门禁更可控

### 10. LangBot 重启后 napcat WebSocket 可能不自动重连

- **表现**：`docker restart langbot` → napcat 日志 `ECONNREFUSED` → 30s 后重试一次 → 失败后再无重连日志
- **解决**：`docker restart napcat` 强制重建 WebSocket 连接
- **预防**：改 langbot 配置时同步重启 napcat；或按 napcat→langbot 顺序重启

### 11. 缓冲读取出错会静默覆盖已有数据

- **根因**：`get_plugin_storage` 抛非 `not_found` 异常（如 `ActionCallError: TypeError: a bytes-like object is required, not 'str'`）时，`except Exception` 创建空 `{'messages': []}`，随后 `set_plugin_storage` 覆盖原有缓冲
- **表现**：群缓冲从 16 条突然变为 0，所有历史记录丢失
- **定位**：`docker logs langbot-plugin | grep ActionCallError` 发现两次 `TypeError`；迁移脚本直接写 `binary_storages` 表导致格式与 Runtime API 不一致
- **解决**：区分 "not found"（新建缓冲）vs 其他异常（return 跳过，保留旧数据）；加 `isinstance(raw, str)` 兼容字符串返回值；`set_plugin_storage` 也加异常捕获
- **教训**：**存储读写必须保守**。读失败绝不能写空数据覆盖。插件 storage API 返回类型可能因版本/调用路径不同而变化（bytes vs str），兼容两种

### 12. Quote/Forward 内的 @ 检测不到

- **根因**：转发消息的 @ 在 `Quote.origin` 或 `Forward.node_list[i].message_chain` 内部，顶层 `message_chain` 遍历不到
- **表现**：转发聊天记录 + @bot 的消息被概率拦截，bot 不回复
- **定位**：monitoring 显示消息 status=pending 且 component types 有 Quote+At 但 LLM 未调用；确认与 6 号坑同类（数据嵌套+事件遍历不完整）
- **解决**：递归 `_has_at()` 进入 `Quote.origin` 和 `Forward.node_list[].message_chain`
- **教训**：**消息组件树是嵌套结构，不是扁平列表**。Quote、Forward 都包含子 MessageChain，@ 检测、文本提取都要递归

### 13. 转发消息文本提取为 Python repr 垃圾

- **根因**：`str(message_chain)` 对 Quote/Forward 组件调用 `__repr__`，输出 `type='Quote' id=None origin=MessageChain([...])` 而非实际内容
- **表现**：缓冲里出现 `type='Quote' id=None group_id=None sender_id=... origin=MessageChain([Plain('...')])` 这种不可读文本
- **解决**：新增 `_extract_text()`，递归提取：Quote→`[转发] {origin文本}`，Forward→`[转发 sender] {node文本}`，Image→`[图片]`，Face→`[表情]`
- **教训**：**别信任 str() 可读**。MessageChain 的 `__str__` 只在 Plain 组件上有意义，复杂组件需手动递归提取

### 14. Synology Docker daemon 僵死 + SSH 连接积压连锁故障

- **根因**：`docker restart langbot` 超时 → 容器进入半死状态（进程存在但不可 exec）→ 后续 `docker exec`/`docker kill` 全部阻塞 → SSH 连接积压到 MaxStartups 上限 → 新连接排队 → `Bash` 工具自动进 background → 更多超时任务堆积
- **表现**：`docker ps` 正常，但 `docker exec langbot echo alive` 永久卡死；`docker logs` 不返回；只有 `docker ps` 和 `docker logs napcat` 正常
- **解决**：① `pkill -9 -f "ssh.*nas"` 清理本地 ② `pkill -f "sshd: root"` 清理 NAS 僵死连接 ③ `docker kill langbot && docker start langbot` 强杀重启（需在 NAS 本地执行，SSH 不可靠）
- **预防**：`docker restart` 加 `--time 5` 限制优雅退出时间；NAS 上直接用终端操作，不依赖 SSH 链路做长耗时操作
- **教训**：**NAS + Docker + SSH 三重组合下，任何超过 5 秒的操作都不可靠**。关键操作（重启容器）在 NAS 本地终端跑，命令返回后用 SSH 做验证

### 15. 递归遍历消息组件必须防御 None 值

- **根因**：`hasattr(obj, 'attr')` 返回 True 但 `obj.attr` 可能为 None（napcat 解析失败或空引用）。当 `Quote.origin` 或 `Forward.node.message_chain` 为 None 时，递归调用 `_has_at(None)` / `_extract_text(None)` → `for c in None` → TypeError
- **表现**：插件 gate handler 崩溃，消息处理中断，bot 不再回复
- **解决**：`hasattr` + 直接访问 → `getattr(x, 'attr', None) is not None` 模式；入口加 None 守卫
- **教训**：**Pydantic 可选字段存在但值为 None 是常态**。用 `getattr(obj, 'attr', None)` 替代 `hasattr(obj, 'attr') and obj.attr`

### 16. napcat 合并转发内容不进入 message_chain

- **根因**：napcat 对合并转发（Forward）消息只发一个 `Source` 组件标记，不把 `node_list` 解包成 `Forward` 组件。转发原文不进入 `message_chain`，`text_message` 也为空
- **表现**：插件 `_extract_text` 输出空字符串，bot 无法读取合并转发的内容。但引用（Quote）正常工作——因为 napcat 会把被引用的原文放入 `Quote.origin`
- **定位**：加诊断存储发现 `mc_types=['Source']`，只有 Source 无 Forward
- **结论**：**napcat 限制，非插件 bug**。用户若需 bot 看到转发内容，应使用引用（Quote）而非合并转发（Forward）
- **教训**：插件处理的 message_chain 受限于上游适配器（napcat）的解析能力，不是所有 OneBot 事件都能完整映射

### 17. PromptPreProcessing（inject）阶段无 message_chain

- **根因**：LangBot Pipeline 在 `PromptPreProcessing` 事件中不携带 `message_chain`，`ctx.event.message_chain` 始终为 None。Pipeline 在此之前已提取 `user_message_text`，message_chain 已被消费。
- **表现**：inject handler 中任何依赖 message_chain 的逻辑（Face 替换、图片标记扫描等）都是空操作，静默无效。
- **定位**：加 `_face_texts` 收集逻辑后发现始终为空，加调试日志 `mc is None: True` 确认。
- **解决**：**gate 提取 → 缓存 → inject 注入**。gate（`GroupMessageReceived`）有完整 `message_chain`，在此阶段提取所需数据（如 Face 文本），通过实例变量（`_face_cache: dict`）传递给 inject。inject 中 pop 缓存并注入 system 消息。
- **教训**：
  - **不同事件阶段的可用数据不同**。`GroupMessageReceived` 有 message_chain，`PromptPreProcessing` 只有 prompt 列表。
  - **跨阶段数据传递模式**：gate 提取 + 实例 dict 缓存 + inject 消费（对标 `_last_trigger` 存储 `(trigger, doc_id, quote_text)` 的模式）。
  - **注入位置要在 KB 检查之前**：如果 inject 在 `if not kb_enabled: return` 之后才注入，KB 禁用时注入失效。
  - **非文本组件表示**：emoji/sticker → 结构化文本标记（`[QQ表情:xxx]`）→ system 消息通道，不混入 `user_message_text`。Discord bot、onebot-llm-agent、OpenCrabs 均同模式。

### 18. SDK 类型注册表修复需双容器 + uv cache 同步

- **根因**：LangBot 双容器架构下，SDK 代码在 `langbot` 和 `langbot-plugin` 两个容器各有独立 site-packages，且 uv 缓存 `/root/.cache/uv/archive-v0/` 中也有副本。仅修一处，其他容器/缓存仍用旧代码。
- **表现**：plugin 容器识别 Face 正确，core 容器 pipeline 仍输出 `[Unknown]`。
- **解决**：`find / -path "*/langbot_plugin/api/entities/builtin/platform/message.py"` 列全副本，逐一修复。再加 `rm -rf __pycache__` 清除字节码缓存。
- **教训**：双容器 + uv 架构下，SDK 级修复先 `find` 列全副本再逐一修，缺一不可。

### 19. 容器内跑 pytest 四坑（2026-08-27）

- **rootdir 抢占**：容器 `/app/pytest.ini` 使 rootdir=/app，cd 插件目录跑 pytest 收集 0 项 + INTERNALERROR。修：`--rootdir=.`。
- **tests/scripts/ 收集崩套件**：脚本顶层 `sys.exit()` 被导入即执行。修：显式 `pytest tests/test_*.py`。
- **tests/__init__.py 缺失**：`from tests.conftest import` ImportError。修：部署时带上包标记。
- **容器 tests/ 子集漂移**：历次 scp 只传部分文件，容器回归通过≠全量通过。修：回归前对比 `ls tests/*.py` 与 worktree 清单。
- 标准命令：`cd <插件目录> && /app/.venv/bin/python -m pytest --rootdir=. tests/test_*.py -q`

### 20. 生产日志做冒烟断言四坑（2026-08-27）

- **测试污染基线**：容器 pytest 直调 store 方法会写真实 /tmp/silent_*.log，grep 计数断言失真。修：测试 fixture monkeypatch `util.logs._log_dir`；冒烟 T0 基线在测试后重取。
- **限流挡死重试**：反思 sender 10min 冷却让同 sender 重试全拒。修：每次冒烟用唯一 sender_id（`smoke-{ts}`）。
- **/sync 积压毁时序**：LLM 回复 30s+/条，群积压上百条时新消息延迟数分钟，固定 sleep 断言失效。跑冒烟前查 event.log `hit` vs `inject` 计数差。
   **⚠️ 二轮修正（同日）**：`hit − inject` 累计差含 lock_skip/历史噪声**不可当积压判据**（实测"182 条积压"真实为 0）——用目标群最后一条 hit 距今 <120s 判在途；且 init_listener 集成测试会写生产 event.log 的 group_t 假行，`_log_event` 路径已改为 `_EVENT_LOG` 模块变量，fixture 须同时 patch `util.logs._log_dir` 与它。
- **断言文件选错**：`_dump_prompt_debug` 不写 prompt 全文；注入内容断言查 `/tmp/silent_gate.log` 的 `LLM RAW PROMPT` 段。

### 21. 绕过服务直改 chroma + 插件 SDK 签名核对（2026-08-27）

- **PersistentClient 双开**：langbot 运行时直连 `/app/data/chroma` 属未定义行为；`collection.update(ids, metadatas)`（不动向量）实测可行，但服务内存缓存可能 flush 回写覆盖——**改完必须重启 langbot 并 delta 口径复查**。规范做法：apply 前 `docker stop langbot`。
- **SDK `vector_upsert(collection_id, vectors, ids, ...)` vectors 必填**：漏传 → TypeError 被 except 吞成一行日志，潜伏 6 天才在评审中发现。写 vector 操作前到容器内核对 `/app/.venv/.../langbot_plugin/api/proxies/langbot_api.py` 签名，别照抄仓库旧调用。
- **监控 DB 真路径**：`/app/data/langbot.db`（`database.db` 是 0 字节占位，连它查表返回空会误判"数据丢失"）；列名先 `PRAGMA table_info`，容器 python 用 `/app/.venv/bin/python`。

### 22. 判断 bot 行为先按通道归属分流（2026-08-28）

同一 session_id 的消息可能走不同 bot/pipeline：monitoring_messages 的 `bot_name` 字段区分——真实 QQ=`AI对话`，/sync 合成消息=`HTTP测试`。**用 /sync 冒烟通道的回复风格给真实通道下结论会误判**（实测：P1.5 治理后 /sync 轮仍现"用户问…"旁白开头，一度误报"压制条款无效"；真实 QQ 轮全部人设正常）。旁白腔对合成连环轰炸消息敏感，对正常真人 @ 不敏感。规则：凡对 bot 行为做根因判断/效果评估，先查 bot_name + sender 归属，合成流量与真实流量分开评估；用户指认"看某群"时先核实是哪个群号，别拿相近活跃群代入。

### 23. prompt 注入文本新增须 grep 测试断言锚（2026-08-27）

向 system prompt 新增的固定文本（如压制条款含"[先前经验]"字样）会撞进旧测试断言的匹配串——`assert '先前经验' not in joined` 因新条款上屏必假失败。修：新增注入文本前 `grep -n` 全部测试文件的中文断言锚，断言改锚定注入模板特有文本（如 '触发条件：'）。同理，冒烟 grep 断言先确认目标文本在哪个日志落盘（gate.log RAW PROMPT 唯一含全文）。

### 24. LangBot 宿主补丁纪律（2026-08-28，详见 ADR-010）

- **只用幂等原地 patch 脚本**（marker 判重+锚缺失报错+自动 .orig），注册进 langbot 容器 entrypoint 自动重放；整文件替换=重建即丢（process/monitoring 补丁曾丢失数周无告警，md5 才发现）。
- **基线只认 langbot 容器**：langbot-plugin 容器里的同名框架源码是死代码副本（两份 aiocqhttp.py 内容分叉 610 vs 682 行，锚点行号完全不同）——从错容器导出基线会让整份计划的锚点作废。
- **NAS 与仓库 patches/ 双向漂移要定期核对**：NAS 有仓库没有的在跑脚本（mcp_timeout 曾失踪）、仓库镜像与线上 entrypoint 内容矛盾过；scp 整目录覆盖前必须三向核对，先回灌再谈同步。
- **改宿主收路径的外部调用（get_msg 等）必须包 asyncio.wait_for**——本部署曾有无超时调用致单群静默的前科；补丁降级分支要 stderr 打 traceback，静默占位=掩盖配置错误。

### 25. "脚本在跑"≠"补丁生效"（2026-08-28）

- patch_image_url 在 entrypoint 注册运行一个多月，实则每次启动 SyntaxError 被 shell 吞掉继续 exec——url 透传**从未生效**，铁证是业务日志分支计数：gate.log `url_ok=0 / b64_ok=105`。
- 纪律：**任何补丁/自动化改动的完成验证必须拿功能侧证据**（applied 日志只是一半，另一半是业务日志里该功能该出现的分支真的出现了），"进程活着、脚本在跑、日志没红"三者加起来也不等于生效。
- 同日接通实证：重写后启用，`url_ok lat=1.1s`，模型可直拉 QQ 图床外链，失败自动回退 base64（vision.py 内建）。附带修正认知：识图 url 制省的是**传输体积**非模型 token——多模态图像 token 按像素切块计，url/base64 两制同价。

### 26. 幂等 patch 脚本自身的版本升级陷阱（2026-08-28）

- **marker 判重是文件粒度，不是 hunk 粒度**：给已上线的 patch 脚本新增一段（如 forward 补丁后补 1c 超时）后，生产文件因旧 marker 存在直接 skip——**新 hunk 永远不会被施加**。正确流程：容器内 `cp .orig-<name> 目标文件`（恢复基线）→ 跑新版脚本 → py_compile → 重启。本次 1c 就靠这个重打流程救回。
- **计划锚定协议层行为时读配置/源码，别从现象反推**：forward 计划第一版假设"事件 data 带 content"，是从 8/24 引用有内容反推的——实际 napcat `parseMultMsg:false`（配置文件一 grep 便知），事件永远不带，必须 get_msg 回取。评审 agent 抓出后才修正。凡锚点建在"外部组件会给什么"上，先查它的配置开关和源码分支，反推≠实证。
