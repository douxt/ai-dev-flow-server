# default.py 代码评审(对照官方 SDK/示例)

> 2026-07-11(初版) → 2026-07-13(更新:对齐最新 17 个提交) → 2026-07-14(更新:对齐补丁体系+默认文件 1223 行) | 依据:Explore agent + 精读 + 对照官方 SDK 与示例
> 用途:地基重构([计划](../../.claude/plans/codegraph-structured-yeti.md))的**验收 rubric**——每步重构后,新代码不得引入已列坏味道。

---

## 一、总体评价

**方向正确,短板在健壮性与可维护性。**

- ✅ 全程走官方 API(`vector_*`/`invoke_embedding`/`invoke_llm`/`get_config`),未直连 ChromaDB
- ✅ 异步并发得当(Semaphore/gather/run_in_executor/wait_for)
- ❌ **1223 行**全塞在一个 `DefaultEventListener` 闭包 → 不可单测
- ❌ 状态零持久化、异常吞没、无 logger、超长函数、大量重复与硬编码
- ❌ 根版(1223行含vision)与 docker 包版(613行无vision)两份不一致

评分(1–5):功能完整 4 / 官方合规 4 / 健壮性 2 / 可维护性 2 / 可测性 1。

---

## 二、新修复(2026-07-13,其他会话,纳入评审)

以下修复已落地,标注对应 commit,重构时应**保留**:

| 修复 | commit | 说明 |
|------|--------|------|
| SQLite WAL 统一 | `bc88c6e` | `_get_db()`(WAL+10s 超时),修复并发写锁 |
| KB flood 修复 | `93aa8e9` + `f212a8d` | `save_reply` 用 finish_reason 过滤流式 chunk + debounce 策略 |
| vision 超时 20s→45s | `32b9eae` | qwen3.7-plus 推理模型需更长时间 |
| vision 统计修复 | `c655d61` | 描述含冒号→改用 `:` 判断 |
| 时间线去重+时区 | `90e0ea2` | 防 LLM 自我引用级联误报凌晨 |
| QQ 表情识别 | `f651520` + `2b545dc` + `bf05c87` | Face→Plain 转换 + classmethod double-wrap 修复 + monkey-patch MessageChain |
| 引用/转发修复 | `bd160e9` + `8fa2277` | Forward 识别 + 合并转发标记 |
| 图片注入优化 | `b069fe` + `f12e88d` | 处理中图片不注入 prompt + 仅替换触发消息行 |
| **测试基础设施文档** | `34bb168` + `b3480c4` | [automated-testing-guide.md](automated-testing-guide.md)(测试金字塔/lbp run/CI)+ `test_face_unit.py` 等诊断脚本 |
| **生产事故** | `c1e70a9` | [incident-20260713-docker-hang.md](incident-20260713-docker-hang.md):15 个 docker logs 僵尸进程崩 Docker 守护进程,部署文档已更新 |

**现状评估**(2026-07-14):
- ✅ Bug 修复积极、测试意识已成型
- ✅ **补丁体系已建**([docker/langbot/patches/](../../docker/langbot/patches/)):直接 patch LangBot 源码防事件循环阻塞
- ⚠️ **代码结构仍为 1223 行单文件**(未拆分,无 pytest 栈,无 FakePlugin 桩)
- ⚠️ 已有测试基础设施:10+ 诊断脚本 + `test_face_unit.py` + 499 行自动化测试指南——**但均未达地基计划目标**(本地 pytest、handler 级模拟、approval 快照)

**补丁体系对反思层设计的启示**:
反思层所有操作必须非阻塞。大文本处理、文件 IO、LLM 调用需用 `run_in_executor` 或 `asyncio.create_task`。避免在事件循环里做同步大操作(如大转发消息处理)。详见 [memory/event-loop-blocking-patches.md](../../memory/event-loop-blocking-patches.md)。

| 项 | 位置 |
|----|------|
| 官方 API 写入 KB | `invoke_embedding`+`vector_upsert` (565-571) |
| 官方 API 检索 | `vector_search`(844)、`vector_list`(805)、`full_text`(885-892) |
| 官方 LLM 调用 | `invoke_llm`(678-692) |
| 官方配置读取 | `get_config`(28),非直读 DB |
| 异步并发 | `Semaphore(2)`、`gather(return_exceptions=True)`(615)、`run_in_executor`(664)、`wait_for`(633/691) |
| 视觉熔断+配额思路 | `_check_vision_quota`(743) |

---

## 三、明确缺陷(按优先级)

### P0(阻塞进化,必先修)

**1. 状态零持久化 → 日限重启失效**(65-72, `_check_vision_quota` 743-755)
- `_vision_daily_count`/`_vision_daily_date`/`_image_cache`/`_last_trigger`/`_vision_stats` 全实例内存,重启清零,`vision_daily_limit` 形同虚设
- 对照官方 [DailyLimitPlugin]():`set_plugin_storage` 单键 JSON + `asyncio.Lock` + 逻辑日期;[GroupChatSummary] `initialize` 恢复
- **当前无相关修复**;测试指南(automated-testing-guide.md)未涉及持久化测试

**2. 硬编码嵌入维度 384**(887)
- 全文检索传 `query_vector=[0.0]*384` 占位;若 seekdb 实际维度≠384 → 报错/静默失效
- 修:启动探测真实维度(参考 lancedb-pro `embedder.test()` 返回 dimensions)

**3. 两份 default.py 不一致**
- 根 `default.py`(1085行含 vision)vs `docker/.../silent-observer/components/event_listener/default.py`(613行无 vision)+ 该副本 manifest 缺 vision/timeline 配置项
- 部署真身不清 → 改错文件风险

### P1(应修)

**4. 裸 `except: pass` 遍布**(21/82/107/118/279/313/821/863/869/904/910/916…)
- 吞 `KeyboardInterrupt`/`SystemExit`,隐藏错误。多为写日志的 try/except
- 修:收敛为单个 `_safe_log()`,业务处捕获具体异常

**5. 无 logger + /tmp 日志无限增长**
- 全 `print(..., file=sys.stderr)` + `open('/tmp/silent_*.log','a')`,无轮转、无级别
- 修:`logging` + 大小上限

**6. 检索逻辑双实现**
- `_search_history`(816-922,RRF 融合)与 tool `search_chat_history.py`(纯向量)策略不一、不共享
- 修:抽公共 `retrieval` 模块

### P2(可维护性)

| # | 问题 | 位置 |
|---|------|------|
| 7 | 超长函数 | `initialize`(26-335,310行)、`inject`(144-322,178行)、`_search_history`(107行)、`_migrate_buffer`(74行) |
| 8 | 重复代码 | sender 元数据×3(478/525/548)、文本截断×3、日志 try/except×8、`_has_at`/`_has_image` 同构、迁移块×2(942/970) |
| 9 | 硬编码/魔法数字 | 群组 ID(943/971)、TTL 300/600、RRF K=60、timeout 5/10、jieba 停用词内联(876) |
| 10 | 控制流坏味道 | `if 'done_imgs' in dir()`/`if 'combined' in dir()`(271/275) |
| 11 | 缺类型注解 | 37 函数仅约 8 个有返回注解 |

---

## 四、可借鉴的官方 API / 示例

| 能力 | 官方 API / 示例 | 坐标 |
|------|----------------|------|
| **rerank 精排**(当前手工 RRF 可加) | `invoke_rerank` | langbot_api.py:361 |
| 混合检索权重 | `vector_search(..., vector_weight=)` | :430 |
| 持久化状态 | `set/get_plugin_storage` | :178/:185 |
| 日限计数范式 | DailyLimitPlugin(Lock+逻辑日期+持久化) | demo |
| buffer 持久化+恢复 | GroupChatSummary(每10条存+initialize恢复) | demo |
| 会话级状态+超时 | HumanTakeover(session_key+惰性超时) | demo |
| 关键词+冷却 | KeywordAlert(substring+cooldown dict) | demo |
| 规范命令 | `@self.subcommand`(把 `/反思` 做成 Command) | Command 组件 |

---

## 五、进化层借鉴(反思层用,详见 [memory-plugins-study.md](memory-plugins-study.md))

- 反思分片存储 + importance 权重(lancedb-pro reflection-store)
- 衰减打分 recency/freq/intrinsic(lancedb-pro decay-engine)
- 候选审核 + 作用域隔离(longterm-memory)
- UNTRUSTED DATA 包裹注入防注入(persistent-memory)

---

## 六、许可证注意

- runtime/ 是 AGPL 但**不传染插件**(插件只 import api/entities 的 Apache 2.0 部分)——ARCHITECTURE.md:15
- 参考记忆插件:AGPL(livingmemory)仅读;longterm-memory/lancedb-pro 无协议只借机制;persistent-memory MIT 可用
