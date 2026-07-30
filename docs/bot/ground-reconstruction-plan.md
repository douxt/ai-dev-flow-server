# Silent Observer 地基重构计划

> 从 `~/.claude/plans/codegraph-structured-yeti.md` 落地,方便所有会话访问  
> **最后更新**: 2026-07-28（对照代码 1352 行 default.py + 14 测试文件重新校准）

## 〇、当前实际进度（2026-07-28 基准）

### 已超前完成

| 项目 | 原计划预期 | 实际状态 |
|------|-----------|---------|
| 插件目录 | 步骤0新建 | ✅ `docker/langbot/plugins/silent-observer/` 已存在 |
| main.py | 步骤4抽主类 | ✅ 8行薄封装，`BasePlugin` 子类 |
| manifest.yaml | 步骤6统一 | ✅ 12 配置项完整（步骤 0.5 + 7 项） |
| 测试基础设施 | 步骤0搭建 | ✅ 14个测试文件，conftest.py 完整 SDK mock 树 |
| FakePlugin 桩 | 步骤0实现 | ✅ conftest.py 已完整实现（含 FakePlain/FakeAt/Face/Image/Quote/Forward） |
| 测试覆盖 | 步骤1-5随重构加 | ✅ P0(纯函数) + P1(消息链) + P2(异步/熔断) + P3(SQLite) + vision + face |
| pyproject.toml | 步骤0配置 | ✅ ruff/mypy/coverage/pytest-cov/pre-commit 全配 |
| 事件监听器 | 步骤5变薄 | ❌ 仍 1352 行（比原计划的 1085 行更多），所有逻辑仍在内 |
| tool 组件 | 步骤3抽取 | ✅ `search_chat_history.py` 118行，独立 Tool 组件 |
| patches 体系 | 未在计划中 | ✅ `patch_image_url.py` + `monitoring_helper.py` + `process.py` |

### manifest.yaml 配置项 🔧 已修复（步骤 0.5）

代码引用 12 项，manifest 现已声明 12 项（7e02e96）。

### 仍待解决

- **P0#1**: 状态零持久化 — `_vision_daily_count`/`_last_trigger` 重启即丢失
- **P0#2**: 硬编码维度 — `_search_history` 中 keyword 通道仍用 `[0.0]*384`
- **P1#6**: 检索双实现 — `_search_history`（RRF）vs tool 的简单搜索，未收敛
- **P1#7**: API 调用无超时保护 — `invoke_embedding`/`vector_search` 等无 `asyncio.wait_for` 包装
- **P2**: 43 个裸 except、24 个 `print()`、17 个 `/tmp` 硬编码路径
- 无 store/service/util 分层
- 无依赖注入

### 步骤 0.5+0 已完成 ✅

- ✅ manifest 12 配置项对齐（7e02e96）
- ✅ conftest.py 路径去硬编码（P0#3 已修复）
- ✅ ruff/mypy/coverage 安装并配置
- ✅ .pre-commit-config.yaml 创建
- ✅ approval 快照基线录制（3 文件 + 11 回归测试）
- ✅ 96 tests passed, < 1s

## 一、为什么重构

**现状问题**:
- 1352 行 default.py 全在一个 `DefaultEventListener` 类中
- 运行时状态零持久化(日限重启失效)
- 硬编码嵌入维度 384

**目标**:
- 分层拆分(store/service/util)
- 修 P0 债务(持久化、维度探测)
- 搭 pytest 测试基础设施(FakePlugin桩)
- 加质量门(ruff/mypy/coverage)

**只做地基,不实现反思层。**

## 二、两条铁律

### 1. 特征刻画测试先行(安全网)

动任何生产代码前,先用真实输入锁定现有行为为 golden master,再抽取,每步后跑它保持绿。

- inject 产出的 prompt、gate 写入 KB 的 metadata 是大文本 → 用 **approval testing**(序列化完整输出+diff)
- 文档现有 quirk 原样,不顺手改 bug

### 2. 结构提交与行为提交分离

一个 commit 要么改结构(纯抽取,特征测试必须保持绿)要么改行为(修 P0,允许改测试),绝不混。

- 提交循环:5–15 分钟一提交
- 超 1 小时没提交 = 改动太大

## 三、术语定义

| 术语 | 定义 |
|------|------|
| **薄封装** | event_listener 只负责事件路由,不包含业务逻辑,调用 service 层方法 |
| **收敛** | 将分散在多处的相似逻辑合并到统一模块,减少重复代码 |
| **结构提交** | 纯代码抽取/重组,不改变外部行为,approval 测试必须保持绿 |
| **行为提交** | 修复 bug 或改进功能,允许改变外部行为,approval 测试可以更新 |
| ** seam **(接缝) | 通过依赖注入制造的测试切入点,让模块可以独立测试 |
| **approval 快照** | 锁定某个输出的 golden master,后续变更需要 diff 对比确认 |
| **影子对照** | 新旧版本同时处理相同输入,对比输出差异,零差异才切换 |

## 四、目标目录布局

> **注意**: 插件实际路径为 `docker/langbot/plugins/silent-observer/`（Docker 构建上下文），
> 以下用 `plugins/silent-observer/` 简写。

**可测性设计**: service/store 通过构造函数接收 `plugin`/`api`(依赖注入,制造 seam),不做全局 import,这样 FakePlugin 桩可注入单测。

```
plugins/silent-observer/
├── main.py                 # BasePlugin 子类：配置/状态/生命周期/持久化（✅ 已薄）
├── manifest.yaml           # ⚠️ 缺 7 个配置项（vision_enabled 等），需补齐
├── AGENTS.md               # 插件级本地开发指引
├── pyproject.toml          # ⚠️ 仅 pytest，缺 ruff/mypy/coverage
├── .pre-commit-config.yaml # ruff+mypy+文件卫生（待创建）
├── store/
│   └── kb_store.py         # KB 读写 + 维度探测 + 多 collection 支持
├── service/
│   ├── vision.py           # 视觉识别（URL-first + 熔断器 + 配额）
│   ├── timeline.py         # 时间线构建 + 去重 + 截断
│   ├── retrieval.py        # RRF 混合检索（收敛 _search_history 与 tool 双实现）
│   └── quote.py            # 引用解析
├── util/
│   ├── image.py            # resize/open/clean
│   └── logs.py             # 统一日志（替裸except+/tmp）
├── components/
│   ├── event_listener/
│   │   ├── default.py      # 薄路由: gate/inject/save_reply → self.plugin.service.*
│   │   └── default.yaml    # ✅ 已存在
│   └── tool/
│       ├── search_chat_history.py  # ✅ 118行，已独立，需改为复用 service/retrieval
│       └── search_chat_history.yaml # ✅
├── requirements.txt        # ✅
└── tests/
    ├── conftest.py         # ✅ 208行 FakePlugin 桩 + Fake* 组件
    ├── approval/           # approval testing 快照（待创建）
    ├── test_p0_pure.py     # ✅ 纯函数测试
    ├── test_p1_chain.py    # ✅ 消息链操作（含 _strip_base64）
    ├── test_p2_async.py    # ✅ 异步队列+熔断器
    ├── test_p2_extract.py  # ✅ _extract_text + _extract_quote
    ├── test_p3_sqlite.py   # ✅ SQLite 操作
    ├── test_vision_p0p1.py # ✅ vision 缩放+限并发
    ├── test_face_unit.py   # ✅ Face 映射表
    ├── test_face_regression.py # ✅ Face 组件回归
    ├── test_smoke.py       # ✅ 全链路烟雾
    ├── test_deploy_smoke.py # ✅ 部署烟雾
    ├── test_bg_stress.py   # ✅ 后台压力
    ├── test_e2e_sync.py    # ✅ 端到端同步
    └── test_quote_e2e.py   # ✅ 引用端到端
```

**可测性设计**: service/store 通过构造函数接收 `plugin`/`api`(依赖注入,制造 seam),不做全局 import,这样 FakePlugin 桩可注入单测。

## 四、步骤间依赖与工作量

### 为什么按这个顺序？

核心原则：**风险从低到高，依赖从底层到上层，每步可独立验证。**

```
步骤0.5 (manifest 补齐) ← 无依赖，最先做
  ↓
步骤0 (脚手架收尾)
  ↓
步骤1 (util) ← 无依赖
  ↓
步骤2 (store)
  ↓
步骤3 (service) ← 依赖 store
  ↓
步骤4 (持久化) ← 依赖 service
  ↓
步骤5 (变薄) ← 依赖 service
  ↓
步骤6 (灰度) ← 依赖所有前序步骤
  ↓
步骤7 (清理) ← 依赖灰度成功
```

**逐层解释**：

| 顺序 | 步骤 | 为什么在这个位置 | 如果跳过/提前会怎样 |
|------|------|-----------------|-------------------|
| 1 | **0.5 manifest** | 最紧急（用户看不到 vision 配置）+ 改动最小（仅 yaml）+ 零风险（新增 key，代码已有默认值降级） | 跳过 → 后续步骤验证时 UI 看不到配置，无法确认生效 |
| 2 | **0 脚手架** | 建立安全网后才能安全重构。approval 快照是所有后续步骤的回归检测器。ruff/mypy 防止新代码引入低级错误 | 提前（先拆代码再补测试）→ 没有 golden master，改出 bug 发现不了 |
| 3 | **1 util** | 纯函数最安全——无副作用、无异步、易于验证等价性。从这里开始建立"抽取→验证"的肌肉记忆。util 的函数被 store 和 service 使用，必须先抽 | 跳过 → store 层会有重复代码；放在后面 → 抽 store 时还要处理工具函数，增加单步复杂度 |
| 4 | **2 store** | 数据层必须先于业务层稳定。维度探测是 P0，必须尽早修。store 使用 util 的函数（`_build_document_id` 等）。API 超时保护加在 store 层最合适 | 提前到 util 前 → util 函数还没抽出来，store 会有冗余代码。推到 service 后 → service 的检索逻辑没地方放 |
| 5 | **3 service** | 依赖 store 的 API（检索服务调 KBStore，vision 服务存结果到 KBStore）。service 是最大块（700+ 行），分 4 个子模块独立抽取，每个子模块单独验证 | 提前到 store 前 → 没有稳定的数据层 API，service 抽取后还要改两次。和持久化一起做 → 单步太大，验证困难 |
| 6 | **4 持久化** | service 抽取完成后，才能准确知道哪些状态需要持久化（`_vision_daily_count`/`_vision_stats` 等在 vision service 中引用）。状态迁移依赖 service 层的稳定 API | 提前 → 可能遗漏字段或持久化了不该持久化的东西。和 service 一起做 → 混淆结构变更和行为变更（违反铁律2） |
| 7 | **5 变薄** | 只有在 store/service/util 全部就位后，event_listener 才有地方路由。这是纯结构变更——每一行代码只是从 default.py 搬到 service，不改变行为 | 提前 → 没有 service 可路由，event_listener 删不掉代码。推迟到灰度后 → 万一有问题需要回滚，回滚到未拆的代码更难诊断 |
| 8 | **6 灰度** | 所有重构完成后才部署。影子对照需要新旧两版都存在。最高风险，放最后做——此时所有前序步骤都已独立验证，灰度只验证"组合在一起是否正常" | 提前 → 每步都部署一次太折腾，且中间状态的代码不适合生产 |
| 9 | **7 清理** | 灰度成功 = 新版本稳定运行后，才能安全清理旧文件。文档写的是最终状态，放在最后 | 提前 → 可能删了还在用的旧文件。推迟 → 无所谓，不阻塞 |

**为什么不能并行？**

- 唯一可并行的 util(步骤1) 和 store(步骤2) 之间有依赖——store 使用 util 的函数
- manifest(步骤0.5) 和脚手架(步骤0) 可并行，但 manifest 改动小（5 分钟），不值得开两个 worktree
- service 的 4 个子模块（vision/timeline/retrieval/quote）可在步骤 3 内并行抽取，但共享同一个 worktree

**为什么不是"合并大步"？**

每条 `→` 都是一次"结构提交 vs 行为提交"的分界线。合并步骤 = 把结构和行为混在一起提交 = 违反铁律 2 = 出问题没法精确回滚到哪个 commit。

**工作量估算**（2026-07-28 重新校准）:
| 步骤 | 预计时间 | 复杂度 | 风险 | 状态 |
|------|---------|--------|------|------|
| 0.5 manifest 补齐 | 0.5小时 | 低 | 低 | ✅ 完成 |
| 0 脚手架收尾 | 1-2小时 | 低 | 低 | ✅ 完成 |
| 1 util | 1-2小时 | 低 | 低 | ⬜ 未开始 |
| 2 store | 3-4小时 | 中 | 中(维度探测) | ⬜ 未开始 |
| 3 service | 5-7小时 | 中 | 低 | ⬜ 未开始 |
| 4 持久化 | 3-4小时 | 中 | 中(状态迁移) | ⬜ 未开始 |
| 5 变薄 | 2-3小时 | 低 | 低 | ⬜ 未开始 |
| 6 灰度 | 3-4小时 | 高 | 高(生产切换) | ⬜ 未开始 |
| 7 清理 | 1-2小时 | 低 | 低 | ⬜ 未开始 |
| **总计** | **19.5-28.5小时** | - | - | 步骤 0.5+0 已完成 |

> 相比原估算减少约 7-10 小时，因为步骤0大部分已完成。

## 四、分步骤执行

### 步骤 0.5 — 补齐 manifest 配置项（新增紧急）

**worktree**: 可合并到下一步骤的 worktree 中，改动量小

**任务**:
在 manifest.yaml 的 `spec.config` 中新增 7 个缺失配置项：

```yaml
- name: timeline_max_chars
  type: integer
  label: { en_US: Timeline Max Chars, zh_Hans: 时间线最大字符数 }
  default: 2000
- name: vision_max_images
  type: integer
  label: { en_US: Vision Max Images, zh_Hans: 视觉识图最大张数 }
  default: 5
- name: vision_enabled
  type: boolean
  label: { en_US: Enable Vision, zh_Hans: 启用视觉识别 }
  default: false
- name: vision_model_uuid
  type: string
  label: { en_US: Vision Model UUID, zh_Hans: 视觉模型 UUID }
  default: ""
- name: vision_all_messages
  type: boolean
  label: { en_US: Vision All Messages, zh_Hans: 所有消息都识图 }
  default: false
- name: vision_daily_limit
  type: integer
  label: { en_US: Vision Daily Limit, zh_Hans: 每日识图上限 }
  default: 0
- name: debug_dump
  type: boolean
  label: { en_US: Debug Dump, zh_Hans: 调试输出 }
  default: false
```

**验证**: 重启后 UI 配置面板出现这 7 个选项，默认值与代码一致。

### 步骤 0 — 脚手架收尾 ✅ 已完成

**worktree**: `silent-base-0.5`（与步骤 0.5 合并）

**已完成**:
- ✅ pyproject.toml 补全 ruff/mypy/coverage/pytest-cov
- ✅ .pre-commit-config.yaml 创建
- ✅ conftest.py 路径去硬编码（`__file__` 相对路径）
- ✅ approval 快照录制（3 基线文件 + 11 回归测试）
- ✅ Docker E2E 脚本分离到 tests/scripts/
- ✅ uv sync 全部依赖安装
- ✅ 96 tests passed, ruff baseline 120 errors

### 步骤 1 — 抽 util/（纯函数，最安全）

**worktree**: `wt create silent-base-1`

**当前代码中的目标函数**:
- `_resize_image()` (L1313-1331): PIL 图片缩放
- `open_image()` (L1308-1310): PIL 图片打开封装
- `_clean_description()` (L1342-1352): vision 描述清理
- `_log_gate()` (L49-54): 写 /tmp 日志（裸 except:pass）
- `_build_document_id()` / `_build_msg_metadata()` (L1271-1290): ID 和元数据构造
- `_format_timeline()` (L1293-1305): 时间线格式化
- `_norm_role()` (L1334-1338): 角色标准化
- `_QQ_FACE_NAME` (L14-33): 137 条 QQ 表情 face_id→中文名映射
- `_is_face_component()` (L469-471): 判断是否 Face/Unknown 降级
- `_face_to_text()` (L483-488): Face 组件 → `[QQ表情:xxx]`
- `_extract_faces()` (L473-481): 从 message_chain 提取所有 Face
- `_normalize_face_components()` (L490-501): 原地替换 Face→Plain（递归 Quote）

**产出**:
- `util/image.py`: `resize_image()`, `open_image()`
- `util/text.py`: `clean_description()`, `build_document_id()`, `build_msg_metadata()`, `format_timeline()`, `norm_role()`
- `util/face.py`: `QQ_FACE_NAME`, `is_face_component()`, `face_to_text()`, `extract_faces()`, `normalize_face_components()`
- `util/logs.py`: `safe_log()` 统一日志（替换裸 except:pass + /tmp 路径 → logging 模块 + RotatingFileHandler）

### 步骤 2 — 抽 store/kb_store.py（收敛所有 vector_* + SQLite）

**worktree**: `wt create silent-base-2`

**当前代码中的目标函数**:
- `_store_message()` (L732-754): vector_upsert + SQLite 双写
- `_get_recent_messages()` (L1037-1051): SQLite 时间线查询
- `_search_history()` (L1053-1159): RRF 混合搜索（vector + keyword）
- `_backfill_sender()` (L991-1035): 回填发送者名称
- `_migrate_buffer_if_needed()` (L1161-1234): 一次性 buffer→KB 迁移
- `_init_chat_index()` (L1253-1268): SQLite 表初始化
- `search_chat_history.py` 中的检索逻辑（L80-95）：简单向量搜索

**关键改进**:
1. 维度探测：启动时 `invoke_embedding(["test"])` → `len(result[0])` 替换硬编码 384
2. 收敛双实现：`_search_history` 的 RRF + tool 的简单搜索 → 统一 `retrieve()` 方法
3. 支持多 collection（chat_history + 未来 reflections）
4. **API 超时保护**：所有 `invoke_embedding`/`vector_search`/`vector_upsert` 调用加 `asyncio.wait_for(..., timeout=30)`（当前仅 vision LLM 有 45s 超时，其余无保护——参考 MCP 超时事故教训）

### 步骤 3 — 抽 service/（逐个，依赖注入，每个配测试）

**worktree**: `wt create silent-base-3`

**当前代码中的目标函数**（注意新增的健壮特性，抽取时必须保留）:

`service/vision.py`:
- `_describe_images()` (L806-831): Semaphore 限并发 + gather
- `_describe_one()` (L833-942): **URL-first 策略**（先尝试 URL 直传 → fallback base64）
- `_check_vision_quota()` (L977-989): 每日配额 + 熔断器
- `_record_vision_result()` (L965-974): 连续失败计数 + 自动熔断
- `_extract_llm_text()` (L944-963): LLM 响应文本提取
- `_collect_images()` (L792-804): 递归收集 Image 组件
- `_has_image()` (L780-790): 递归检测是否含图片

`service/retrieval.py`:
- `_search_history()` (L1053-1159): RRF 混合搜索（保留 jieba 分词 + 停用词过滤）
- `_get_recent_messages()` (L1037-1051): SQLite 时间线
- tool 的简单搜索逻辑合并进来

`service/quote.py`:
- `_extract_quote()` (L597-629): 递归提取引用文本
- `_quote_has_image()` (L584-595): 引用图片检测

`service/timeline.py`:
- `_extract_text()` (L503-561): 消息链→文本（含 Face/Forward/Quote 递归）
- `inject()` 中的 timeline 格式化 + 去重 + 截断逻辑 (L297-309)
- `inject()` 中的图片识别标记强化逻辑 (L312-338)

**抽取注意事项**:
- `_VISION_SEMAPHORE` (L807) 是模块级 global，抽取到 `VisionService` 时应改为实例属性 `self._semaphore`
- `_API_SEM` (L46) 同理，抽取到 `KBStore` 时应改为实例属性
- 所有 service 方法签名改为 `(self, plugin, ...)` 依赖注入模式

### 步骤 4 — 主类 + 持久化（修 P0#1）

**worktree**: `wt create silent-base-4`

**当前状态字段**（比原计划多）:
- `_vision_daily_count` / `_vision_daily_date`: 每日识图计数
- `_vision_fail_streak`: 连续失败计数
- `_vision_circuit_open_until`: 熔断器恢复时间
- `_vision_stats`: 累计统计 {'total', 'success', 'fail', 'total_tokens'}
- `_last_trigger`: session → (trigger, doc_id, message_chain)
- `_lock_set_ts` / `_reply_ts` / `_last_msg_ts`: 时间戳
- `_gate_hits` / `_gate_misses` / `_lock_skips` / `_inject_random` / `_inject_at`: 触发统计
- `_stats_start`: 统计起始时间

**持久化方案**: 单键 JSON + `asyncio.Lock` + 每 5 分钟 `_periodic_save()`，启动时 `initialize()` 恢复。

**注意**: `_face_cache` / `_image_cache` / `_reply_pending` / `_reply_tasks` 不需要持久化（运行时临时状态）。

### 步骤 5 — event_listener 变薄

**worktree**: `wt create silent-base-5`

**当前 default.py 结构**（1352 行 → 目标 ~200 行）:

| 区域 | 行号 | 行数 | 操作 |
|------|------|------|------|
| 模块级 (import/常量/工具函数) | 1-56 | 56 | → util/ + store/ |
| `initialize()` | 58-145 | 88 | 配置读取保留，状态初始化→main.py |
| `gate` handler | 148-218 | 71 | → 薄路由调用 service |
| `save_reply` handler | 221-237 | 17 | → 薄路由调用 service |
| `inject` handler | 240-401 | 162 | → **最大块**，timeline 逻辑→service |
| `cache_cleanup_loop` | 404-414 | 11 | → main.py 生命周期 |
| `stats_report_loop` | 416-434 | 19 | → main.py 生命周期 |
| helper 方法 (face/at/extract/vision/store/search) | 436-1159 | 724 | → service/ + store/ |
| 迁移+队列+SQLite | 1161-1268 | 108 | → store/ + main.py |
| 模块级工具函数 | 1271-1352 | 82 | → util/ |

**核心原则**: event_listener 只保留事件路由 + 薄调用，所有业务逻辑在 service/ 中。

### 步骤 6 — 影子对照 + 灰度部署（风险最高）

**worktree**: `wt create silent-base-6`

> manifest 补齐已在步骤 0.5 完成，本步聚焦于生产切换。

**任务**:
1. **数据兼容验证**: doc_id 格式 (`chat:sha256[:16]`) 和 metadata schema 不变，确保旧 KB 数据可检索
2. **影子对照**: 录制真实 gate/inject 输入 → 新旧两版并行跑 → diff prompt/KB 输出
3. **灰度**: 先测试群 `group_1104330614` → 再切生产群 `group_116381172`
4. **备份 + 回滚**: 切换前备份现行 default.py

### 步骤 7 — 清理 + 文档

**worktree**: `wt create silent-base-7`

**任务**:
1. 删除根目录旧 `default.py`（如仍存在）
2. 写 `plugins/silent-observer/AGENTS.md` 本地开发指引
3. **更新 deploy.sh**：拆分后需部署整个目录（store/ + service/ + util/ + components/），而非仅 default.py + main.py
4. 地基决策（目录/分层/持久化/依赖注入）补充 ADR
5. **jieba import 优化**：当前 `import jieba` 在 `_search_history` 异步函数内，首次调用可能阻塞事件循环；移到模块顶部 import

**影子对照录制流程**:
```bash
# 1. 从 KB 导出最近 100 条真实消息
ssh root@nas "docker exec langbot-plugin python3 -c '
import chromadb
client = chromadb.PersistentClient(path=\"/app/data/chroma\")
collection = client.get_collection(\"da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc\")
results = collection.get(limit=100, include=[\"documents\", \"metadatas\"])
import json
print(json.dumps(results, ensure_ascii=False))
'" > /tmp/real_messages.json

# 2. 用这些消息分别喂新旧版本,生成输出
python3 scripts/shadow_run.py --input /tmp/real_messages.json --old default.py --new plugins/silent-observer/

# 3. 对比输出差异
diff /tmp/old_output.json /tmp/new_output.json
```

**回滚脚本** (`scripts/rollback.sh`):
```bash
#!/bin/bash
# 一键回滚到老版本
set -e

echo "开始回滚..."

# 1. 备份当前版本
ssh root@nas "docker cp langbot-plugin:/app/data/plugins/dou__langbot-silent-observer/components/event_listener/default.py /tmp/default.py.backup.$(date +%s)"

# 2. 恢复老版本
ssh root@nas "docker cp /backup/default.py langbot-plugin:/app/data/plugins/dou__langbot-silent-observer/components/event_listener/default.py"

# 3. 重启容器
ssh root@nas "timeout 30 docker restart langbot-plugin"

# 4. 验证回滚成功
sleep 5
ssh root@nas "docker exec langbot-plugin cat /tmp/silent_init.log | grep 'vision_enabled=True'"

echo "回滚完成"
```

## 五、测试基础设施

### 已完成 ✅

- **pytest + pytest-asyncio + pytest-cov + ruff + mypy + coverage**: 全部安装并配置
- **FakePlugin 桩** (conftest.py 208行): 完整 SDK mock 树 + FakePlain/FakeAt/FakeFace/FakeUnknown/FakeImage/FakeQuote/FakeForward/FakeForwardNode
- **approval 快照**: 3 基线文件 + test_approval.py 11 回归测试
- **.pre-commit-config.yaml**: ruff + yaml/toml 文件卫生
- **测试分层**: P0/P1/P2/P3/vision/face/approval
- **E2E 脚本**: 7 个 Docker 内自动化测试（tests/scripts/）

### 待完成

- **覆盖阈值**: `--cov-fail-under` 设 70–80%（当前未强制执行）
- `_resize_image` RGBA→JPEG 预存 bug 修复（步骤 1）

## 六、关键约束 / 风险

- **单 event_listener 组件**: 逻辑抽普通模块,组件仅路由
- **生产在跑**: strangler 渐进 + 每步保持可运行完整插件(非到末步才能跑)+ 每步真机验证
- **步骤 6 最高风险**: shadow 对照 + 灰度 + 备份回滚三重保险;KB/配置数据向后兼容
- **运维教训(incident-20260713)**: SSH 管道 `docker logs | tail` 会产僵尸进程(15 个崩掉 Docker 守护进程)。所有 docker 命令**非管道化**(用 `docker exec ... sh -c '...'` 替代 `docker logs | head`),运维文档已更新。
- **AGPL**: livingmemory 仅阅读禁复制;longterm-memory/lancedb-pro 参考机制不搬代码
- 每步 `wt create` 隔离,结构/行为提交分离,5–15 分钟一提交

### 重构中必须保留的新特性（2026-07 迭代新增）

以下代码模式是经过线上验证的，抽取时必须完整保留：

| 特性 | 位置 | 要点 |
|------|------|------|
| **Vision URL-first** | `_describe_one` L833-942 | URL 直传优先，失败 fallback base64；45s 超时 |
| **Vision 熔断器** | `_record_vision_result` + `_check_vision_quota` | 连续 5 次失败 → 5 分钟熔断 + 每日配额 |
| **Face 全链路** | `_is_face_component` → `_face_to_text` → `_normalize_face_components` | Unknown 降级兼容 + 137 条 QQ 表情映射 + inject 阶段 `[QQ表情:xxx]` 注入 |
| **Forward 递归** | `_extract_text` / `_extract_quote` / `_has_at` / `_strip_base64` | 合并转发多层递归 + Source-only 检测 + 节点数限制(5) |
| **后台 Worker Pool** | `_bg_queue` + `_bg_worker` ×3 | 有界队列(maxsize=10) + QueueFull 丢弃 |
| **双时区注入** | `inject` L249-256 | UTC + 北京时间同时注入 system prompt |
| **Timeline 去重** | `inject` L298-303 | 连续相同 bot 消息只保留第一条 |
| **Prompt Dump** | `inject` L343-355 + L392-401 | 调试输出到 `/tmp/silent_prompt_dump.log` |
| **Image URL pass-through** | `patch_image_url.py` | NapCat Image 构造时保留 `url` 字段 |

## 七、事故响应预案

### 监控告警配置

```python
# monitoring.py
class MetricsCollector:
    def __init__(self):
        self.error_rate_threshold = 0.01  # 1%
        self.latency_threshold = 1.0      # 1秒
        self.alert_cooldown = 300         # 5分钟

    def check_alerts(self):
        """检查是否需要告警"""
        if self.error_rate > self.error_rate_threshold:
            self._send_alert(f"错误率过高: {self.error_rate:.2%}")
        
        if self.avg_latency > self.latency_threshold:
            self._send_alert(f"延迟过高: {self.avg_latency:.2f}s")

    def _send_alert(self, message):
        """发送告警(可扩展为邮件/钉钉/微信)"""
        print(f"[ALERT] {message}", file=sys.stderr)
```

### 事故响应流程

| 阶段 | 时间 | 行动 |
|------|------|------|
| **发现** | < 5分钟 | 监控告警 or 用户反馈 |
| **诊断** | < 15分钟 | 查看日志、检查错误率、定位问题模块 |
| **决策** | < 30分钟 | 判断是否需要回滚 |
| **回滚** | < 5分钟 | 执行 `scripts/rollback.sh` |
| **验证** | < 10分钟 | 确认回滚成功、错误率恢复正常 |
| **复盘** | < 1小时 | 记录事故原因、改进措施 |

**回滚时间窗口**:
- 步骤 0-5: 无需回滚(worktree隔离)
- 步骤 6: 5分钟内可回滚
- 步骤 7: 无需回滚(清理阶段)

### 降级方案

| 场景 | 降级策略 |
|------|---------|
| vision 识图失败率 > 10% | 自动禁用 vision,退回纯文本模式 |
| KB 检索延迟 > 2s | 降低 history_count 到 20 |
| 并发冲突 | 降低 reply_probability 到 0.05 |
| 完全不可用 | 执行回滚脚本,恢复老版本 |

## 八、验证体系

> 原则：每一步都有**可执行的**验证流程，不做完就完。

### 验证分层

```
          真机全链路 (步骤 6)
         /              \
    影子对照 (步骤 6)   集成验证 (每步)
         \              /
          approval 快照 (步骤 0 建立，所有后续步骤跑)
              ↑
          单元测试 (每步，pytest + FakePlugin)
```

### 步骤 0.5 验证 — manifest 补齐

| 检查项 | 方法 | 通过标准 |
|--------|------|---------|
| 配置项出现在 UI | 重启 → 打开插件配置面板 | 7 个新配置项可见，默认值与代码一致 |
| 旧配置不丢失 | 查看 DB `plugin_settings` | 已有 `bot_qq`/`kb_id` 等值不变 |
| 默认值降级 | 不填新配置项，看日志 | vision_enabled=false，无报错 |

### 步骤 0 验证 — 脚手架收尾

| 检查项 | 方法 | 通过标准 |
|--------|------|---------|
| ruff 检查 | `ruff check .` | 0 errors（可先设宽松规则，逐步收紧） |
| mypy 类型检查 | `mypy components/` | 无 new errors（允许渐进 annotation） |
| conftest 路径 | 在新 worktree 中跑 `pytest tests/` | 所有已有测试绿，无 ImportError |
| approval 录制 | 用真机最近 50 条消息作为输入，跑 inject/gate | 生成 `tests/approval/gate_baseline.txt` + `inject_baseline.txt` |
| approval 可重复 | 连续跑 3 次 approval 测试 | 每次 diff 为零（输出可重复） |

### 步骤 1 验证 — util/ 抽取

| 检查项 | 方法 | 通过标准 |
|--------|------|---------|
| 纯函数等价 | 随机 100 组输入，新旧 `_resize_image`/`_clean_description`/`_build_document_id` 输出对比 | 100% 一致 |
| 日志行为不变 | 触发 gate 事件，检查 `/tmp/silent_gate.log` 格式 | 日志格式与旧版一致 |
| 现有测试绿 | `pytest tests/` | 全绿，无新增失败 |
| approval 绿 | approval diff | 零差异 |
| 机械指标 | `grep -c 'except:' default.py` 等 | 裸 except 数下降，print 数下降 |

### 步骤 2 验证 — store/ 抽取

| 检查项 | 方法 | 通过标准 |
|--------|------|---------|
| 维度探测 | 启动时日志 `dimension detected: N` | N ≠ 384（真实维度），且 `[0.0]*N` 可用于 keyword search |
| KB 读写等价 | 写入 20 条测试消息，分别用新旧 `_store_message` → `_get_recent_messages` 对比 | 返回结果 100% 一致 |
| RRF 检索等价 | 相同 query 新旧 `_search_history` 结果对比 | top-5 结果 ID 和排序一致 |
| 双实现收敛 | tool `search_chat_history` 改为调用 store 层 | 返回格式不变，调用方无感知 |
| API 超时保护 | 模拟网络延迟 >30s | 抛出 `asyncio.TimeoutError`，不永久挂起 |
| approval 绿 | approval diff | 零差异 |

### 步骤 3 验证 — service/ 抽取

| 检查项 | 方法 | 通过标准 |
|--------|------|---------|
| vision 等价 | 同一条带图消息，新旧 `_describe_images` 输出对比 | image_descs 内容一致（允许 LLM 非确定性，但格式/索引一致） |
| vision URL-first 保留 | 带 URL 的 Image 组件 → `_describe_one` | 走 URL 路径（日志含 `url_ok`），不 fallback base64 |
| vision 熔断保留 | 连续模拟 5 次失败 | `_vision_circuit_open_until` 被设置，之后返回 `[图片]` |
| quote 等价 | 同一条 Quote 消息新旧 `_extract_quote` 对比 | 提取文本 100% 一致 |
| timeline 等价 | 同组 KB 数据新旧 inject 的 timeline 对比 | lines 列表内容/顺序一致 |
| service 可独立测 | `pytest tests/test_service_*.py`（新写） | 每个 service 至少 5 个独立用例 |
| approval 绿 | approval diff | 零差异 |

### 步骤 4 验证 — 持久化

| 检查项 | 方法 | 通过标准 |
|--------|------|---------|
| 状态保存 | 运行 5 分钟 → 检查 `plugin_storage` | `silent_observer_state` 键存在，含完整 JSON |
| 状态恢复 | 手动 `set_plugin_storage` 写入测试数据 → 重启 | `_vision_daily_count` 等恢复为写入值 |
| 跨日重置 | 改系统时间到次日 → 触发 vision | `_vision_daily_count` 从 0 开始 |
| 并发安全 | 2 个协程同时写状态 | 不丢数据、不损坏 JSON |

### 步骤 5 验证 — event_listener 变薄

| 检查项 | 方法 | 通过标准 |
|--------|------|---------|
| 行数缩减 | `wc -l default.py` | < 250 行（从 1352 行） |
| 函数长度 | `grep` 最长的 async def | < 50 行 |
| 路由正确 | gate → service.gate() / inject → service.inject() | 行为不变（approval 绿） |
| 事件注册完整 | 检查 handler 注册 | GroupMessageReceived + NormalMessageResponded + PromptPreProcessing 三个事件都在 |
| approval 绿 | approval diff | **零差异**（纯结构变更，不改行为） |

### 步骤 6 验证 — 灰度部署

| 检查项 | 方法 | 通过标准 |
|--------|------|---------|
| 影子对照: KB 写入 | 历史 50 条消息新旧版本分别写入 | doc_id/metadata/content 完全一致 |
| 影子对照: inject | 相同 timeline 输入新旧版本 inject 输出 | prompt 内容完全一致 |
| 测试群验证 | 部署到 `group_1104330614` 运行 24h | 错误率 < 1%，@触发正常回复 |
| 生产群切换 | 部署到 `group_116381172` | 烟雾测试通过（@bot 回复 + 随机插话） |
| 回滚演练 | 执行回滚脚本 | 3 分钟内恢复旧版本并验证正常 |
| KB 向后兼容 | 切换后搜索旧 KB 记录 | 旧数据可检索，返回格式正确 |

### 步骤 7 验证 — 清理

| 检查项 | 方法 | 通过标准 |
|--------|------|---------|
| 旧文件清理 | 确认根目录无残留 `default.py` | 文件不存在或已标记废弃 |
| deploy.sh 覆盖 | 执行 deploy.sh | 所有新文件（store/service/util/）都被上传 |
| AGENTS.md 可执行 | 按 AGENTS.md 指引从零搭建开发环境 | 能跑 `pytest` 且全绿 |

### 真机 E2E 验证（关键步骤后执行）

`tests/scripts/` 中有 7 个 Docker 内自动化脚本，通过 napcat HTTP API 在测试群发消息并验证回复：

| 脚本 | 场景 | 用法 | 适用步骤 |
|------|------|------|---------|
| `test_smoke.py` | napcat+LangBot 存活 | 任何部署后 | 全部 |
| `test_deploy_smoke.py` | 8 场景全链路 | 重大变更后 | 步骤 3, 4, 5, 6 |
| `test_face_regression.py` | 6 场景表情回归 | Face 相关变更 | 步骤 3(timeline), 5 |
| `test_quote_e2e.py` | 引用消息 KB 入库 | Quote 相关变更 | 步骤 3(quote), 5 |
| `test_bg_stress.py` | 20 并发压力 | 异步/队列变更 | 步骤 4, 5 |
| `test_e2e_sync.py` | /sync 防 KB flood | KB 写入变更 | 步骤 2, 3, 4 |
| `test_face_unit.py` | Face 容器内单元（不发消息） | Face 映射表变更 | 步骤 1, 3 |

**执行方式**（以 test_deploy_smoke.py 为例）：
```bash
# 1. 部署新代码到 NAS
cd plugins/silent-observer && ./deploy.sh
# 2. 上传 E2E 脚本到 napcat 容器
scp tests/scripts/test_deploy_smoke.py root@nas:/tmp/
ssh root@nas "docker cp /tmp/test_deploy_smoke.py napcat:/tmp/"
# 3. 运行（发送消息到测试群 group_1104330614，验证回复）
ssh root@nas "docker exec napcat python3 /tmp/test_deploy_smoke.py"
# 4. 检查退出码：0=全通过
```

**E2E 验证触发规则**：
- 步骤 2-5：每步完成后至少跑 `test_smoke.py` + 对应的专项脚本
- 步骤 6：跑全部 7 个脚本，全部通过才切生产群
- 步骤 0-1：纯本地函数抽取，不强制真机验证

### 全程监控（横切所有步骤）

每个步骤完成后记录以下指标到 `/tmp/silent_stats.log`，与上一步对比：

| 指标 | 采集方法 | 警戒线 |
|------|---------|--------|
| gate 触发率 | `_gate_hits / (_gate_hits + _gate_misses)` | 波动 < 5% |
| vision 成功率 | `_vision_stats['success'] / _vision_stats['total']` | 波动 < 10% |
| KB 写入延迟 | `_store_message` 耗时 | < 500ms |
| inject 延迟 | `inject` handler 总耗时 | < 2s |
| 错误日志量 | `grep ERROR /tmp/silent_gate.log | wc -l` | 不显著增加 |

### 验证执行规则

1. **每步必验**：验证是步骤的一部分，未通过验证 = 步骤未完成，禁止进入下一步
2. **三层验证体系**：
   - 第1层 🤖 本地：pytest + ruff + mypy + approval diff（秒级，每次 commit 跑）
   - 第2层 🤖 真机：E2E 脚本发送消息到测试群验证回复（分钟级，每步完成后跑）
   - 第3层 👤 人工：UI 配置检查、生产全链路、影子对照确认（关键时刻跑）
3. **人机分工**：
   - 🤖 自动：pytest、ruff、mypy、approval diff、机械指标 grep、E2E 脚本
   - 👤 人工：UI 配置面板检查、生产群切换、影子对照结果确认
4. **验证记录**：每步完成后在 `tests/approval/step_N_verification.log` 记录验证结果：
   ```
   [2026-07-28 14:30] 步骤 2 验证
   ✅ pytest: 96 passed, 0 failed
   ✅ ruff: 0 errors (down from 120)
   ✅ approval: diff empty
   ✅ 维度探测: 1536 (seekdb-local)
   ✅ E2E test_smoke.py: exit 0
   ✅ E2E test_quote_e2e.py: 4/4 场景通过
   ```
5. **失败即停**：任一必须验证项失败 → 停止、诊断、修复 → 重新验证 → 通过后才继续

### approval 快照内容定义

录制以下具体输出作为 golden master：

**gate 快照** (`tests/approval/gate_baseline.txt`):
```
输入: 最近 50 条真实群消息 (从 KB 导出)
录制内容:
- 每条消息的 gate 决策 (hit/miss)
- doc_id 生成结果
- _extract_text 输出
- face_text 提取结果
- quote_text 提取结果
```

**inject 快照** (`tests/approval/inject_baseline.txt`):
```
输入: 10 组不同触发场景 (随机插话 / @ / 空@ / 空@+引用 / 带图@)
录制内容:
- 注入的 system prompt 完整文本
- timeline 行数和内容
- 时区注入文本
- 图片识别标记状态 (⏳/🤖/❌)
```

**approval 测试脚本** (`tests/test_approval.py`):
```python
def test_gate_approval():
    """gate 输出必须与 baseline 完全一致"""
    output = run_gate_with_fixtures(GATE_FIXTURES)
    baseline = Path('tests/approval/gate_baseline.txt').read_text()
    assert output == baseline, f"Gate output diverged! Diff:\n{diff(output, baseline)}"

def test_inject_approval():
    """inject 输出必须与 baseline 完全一致"""
    output = run_inject_with_fixtures(INJECT_FIXTURES)
    baseline = Path('tests/approval/inject_baseline.txt').read_text()
    assert output == baseline, f"Inject output diverged! Diff:\n{diff(output, baseline)}"
```

## 九、不做

- 不实现反思层/评估层(地基后独立任务,见 evolution-roadmap.md)
- 不追 100% 覆盖(核心层优先)
- 不动现有 bats 测试;不顺手改现有 quirk(单独开票)

## 十、测试数据管理

### 数据隔离策略

```python
# tests/conftest.py
import pytest
import tempfile
import shutil

@pytest.fixture
def test_data_dir(tmp_path):
    """临时测试数据目录"""
    test_dir = tmp_path / "test_data"
    test_dir.mkdir()
    yield test_dir
    # 测试结束后自动清理
    shutil.rmtree(test_dir, ignore_errors=True)

@pytest.fixture
def mock_kb(test_data_dir):
    """模拟 KB,避免污染生产环境"""
    # 使用临时 ChromaDB 实例
    import chromadb
    client = chromadb.PersistentClient(path=str(test_data_dir / "chroma"))
    collection = client.create_collection("test_kb")
    yield collection
    # 测试结束后自动清理
```

### 测试数据污染防护

| 场景 | 防护措施 |
|------|---------|
| 单元测试 | 使用 pytest 的 `tmp_path` fixture,自动隔离 |
| 集成测试 | 使用独立的测试群 `group_test_123` |
| E2E 测试 | 在测试群执行,不污染生产群 |
| approval 测试 | 快照文件在 `tests/approval/`,不影响运行时 |

### 测试数据清理

```bash
# 清理测试数据
rm -rf tests/tmp/
rm -rf /tmp/test_silent_observer/

# 清理测试群数据(可选)
ssh root@nas "docker exec langbot-plugin python3 -c '
import chromadb
client = chromadb.PersistentClient(path=\"/app/data/chroma\")
# 删除测试群的消息
collection = client.get_collection(\"da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc\")
collection.delete(where={\"session_id\": \"group_test_123\"})
'"
```

## 十一、FAQ

### Q: worktree 冲突如何处理?

**A**: 
1. 每个步骤创建独立的 worktree(`wt create silent-base-N`)
2. 步骤间通过 merge 传递变更
3. 如果 merge 冲突,优先保留当前步骤的改动(因为前序步骤已验证)

```bash
# 示例:合并步骤1到main
git checkout main
git merge silent-base-1 --no-ff
# 如果有冲突
git mergetool  # 使用可视化工具解决冲突
```

### Q: approval 测试失败如何检查?

**A**:
1. 查看 diff 输出,确认变更是否预期
2. 如果是预期变更(如修复 bug),更新 approval 快照
3. 如果是非预期变更,回滚代码

```bash
# 查看 diff
pytest tests/approval/ --approval-show-diff

# 更新快照(确认变更后)
pytest tests/approval/ --approval-update
```

### Q: 灰度部署发现问题如何回滚?

**A**:
1. 立即执行 `scripts/rollback.sh`
2. 验证回滚成功(检查日志)
3. 分析问题原因
4. 修复后重新灰度

### Q: 步骤间可以并行吗?

**A**: 
- 步骤 1-3 可以部分并行(util/store 可以并行)
- 步骤 4-5 必须串行(依赖前序步骤)
- 步骤 6 必须最后(依赖所有前序步骤)

### Q: 如果某步骤失败,如何继续?

**A**:
1. 分析失败原因
2. 修复问题
3. 重新执行该步骤(不需要从头开始)
4. 通过后继续下一步骤

## 十二、Troubleshooting

### 场景 1: pytest 不通过

**症状**: approval 测试 diff 不为零

**排查步骤**:
```bash
# 1. 查看 diff
pytest tests/approval/ --approval-show-diff

# 2. 确认变更是否预期
# - 预期变更:更新快照
# - 非预期变更:回滚代码

# 3. 检查覆盖率
pytest --cov=plugins/silent_observer --cov-report=term-missing
```

### 场景 2: 影子对照出现 diff

**症状**: 新旧版本输出不一致

**排查步骤**:
```bash
# 1. 查看具体差异
diff /tmp/old_output.json /tmp/new_output.json | head -50

# 2. 分析差异类型
# - prompt 格式差异:检查 prompt 组装逻辑
# - KB metadata 差异:检查 metadata 构建逻辑
# - 时间戳差异:检查时间处理逻辑(可能需要 mock)

# 3. 如果是预期差异(如修复 bug),记录原因后继续
# 4. 如果是非预期差异,回滚并修复
```

### 场景 3: 灰度部署后错误率上升

**症状**: 切换到新版本后,错误率从 < 1% 上升到 > 5%

**排查步骤**:
```bash
# 1. 查看错误日志
ssh root@nas "docker exec langbot-plugin cat /tmp/silent_error.log | tail -50"

# 2. 检查错误类型
# - ImportError: 检查模块导入路径
# - KeyError: 检查配置项是否缺失
# - TimeoutError: 检查外部服务调用

# 3. 如果无法快速修复,立即回滚
./scripts/rollback.sh

# 4. 回滚后验证
ssh root@nas "docker exec langbot-plugin cat /tmp/silent_init.log | grep 'vision_enabled=True'"
```

### 场景 4: 性能退化

**症状**: vision 延迟从 45s 上升到 > 60s

**排查步骤**:
```bash
# 1. 运行性能测试
pytest tests/performance/ -v

# 2. 查看性能瓶颈
pytest tests/performance/ --profile

# 3. 常见原因
# - 网络延迟:检查外部 API 调用
# - 内存泄漏:检查是否有未释放的资源
# - 并发问题:检查 Semaphore 配置

# 4. 如果性能持续退化,考虑降级
# - 降低 history_count
# - 降低 vision_max_images
```

## 十三、相关文档

- [项目总纲](project-overview.md)
- [重构方法论](refactoring-methodology.md)
- [参考资产地图](reference-assets-map.md)
- [代码评审基线](code-review-against-official.md)
- [ADR-001: 插件目录结构](../decisions/001-plugin-directory-structure.md)
- [ADR-002: 测试策略](../decisions/002-testing-strategy.md)
- [ADR-003: 依赖注入](../decisions/003-dependency-injection.md)
- [ADR-004: 不用 QQ 酒馆](../decisions/004-reject-qq-sillytavern.md)
