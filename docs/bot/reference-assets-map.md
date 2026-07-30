# 参考资产地图

> 7 个参考项目的位置、用途、许可证注意事项

## 一、项目位置总览

所有参考项目位于：`~/dev/references/bot-evolve-refs/`

| 项目 | 路径 | 许可证 | 核心价值 |
|------|------|--------|----------|
| **langbot-longterm-memory** | `langbot-longterm-memory/` | Apache-2.0 | LangBot 官方长期记忆插件，**最该照抄的架构** |
| **memory-lancedb-pro** | `memory-lancedb-pro/` | 无 LICENSE | 反思纠错标杆，⭐4450 |
| **astrbot-livingmemory** | `astrbot-livingmemory/` | **AGPL-3.0** | 薄 handler 架构范例，⭐277 |
| **astrbot-persistent-memory** | `astrbot-persistent-memory/` | MIT | LanceDB + 多重打分 + 作用域隔离 |
| **langbot-plugin-sdk** | `langbot-plugin-sdk/` | Apache-2.0 | 官方插件 SDK 源码 |
| **langbot-plugin-demo** | `langbot-plugin-demo/` | Apache-2.0 | 官方插件示例集 |
| **langbot-rag** | `langbot-rag/` | 无 LICENSE | 官方 RAG 实现 |

---

## 二、各项目详细说明

### 1. langbot-longterm-memory（最该照抄）

**路径**：`~/dev/references/bot-evolve-refs/langbot-longterm-memory/`

**核心价值**：
- 双层记忆架构（L1 profile + L2 episode）
- 候选审核机制（防噪声固化）
- 作用域隔离（scope_key/user_key）
- 测试范式（FakePlugin 桩 + pytest-asyncio）

**关键文件**：
```
langbot-longterm-memory/
├── store/memory_store.py          # 存储层（可测性设计）
├── service/
│   ├── profile_service.py         # L1 profile 管理
│   └── episode_service.py         # L2 episode 管理
├── components/
│   └── event_listener/default.py  # 薄路由（~50行）
└── tests/
    ├── conftest.py                # FakePlugin 桩
    └── test_memory_store.py       # 存储层测试
```

**Codegraph 查询示例**：
```bash
# 查存储层实现
codegraph explore "MemoryStore upsert delete" -p ~/dev/references

# 查候选审核机制
codegraph explore "CandidateReview approve reject" -p ~/dev/references

# 查测试桩实现
codegraph explore "FakePlugin vector_upsert" -p ~/dev/references
```

---

### 2. memory-lancedb-pro（反思纠错标杆）

**路径**：`~/dev/references/bot-evolve-refs/memory-lancedb-pro/`

**核心价值**：
- 反思分片存储（4 类 importance 权重）
- 衰减打分（recency/importance/decay）
- 混合检索（向量 + 关键词）
- 自动捕获正则

**关键文件**：
```
memory-lancedb-pro/
├── src/
│   ├── reflection-store.ts        # 反思分片存储
│   ├── decay-engine.ts            # 衰减打分
│   ├── retriever.ts               # 混合检索
│   └── embedder.ts                # 嵌入 + 维度探测
└── test/
    └── reflection-store.test.ts   # 反思存储测试
```

**Codegraph 查询示例**：
```bash
# 查反思分片存储
codegraph explore "ReflectionStore storeReflection" -p ~/dev/references

# 查衰减打分
codegraph explore "DecayEngine calculateDecay" -p ~/dev/references

# 查维度探测
codegraph explore "Embedder detectDimension" -p ~/dev/references
```

---

### 3. astrbot-livingmemory（薄 handler 架构）

**路径**：`~/dev/references/bot-evolve-refs/astrbot-livingmemory/`

**核心价值**：
- 薄 handler 架构（event handler 只路由）
- 注入式子模块（可测性 seam）
- 图记忆组件

**许可证**：**AGPL-3.0** — 仅读架构思路，**禁止复制代码**

**关键文件**：
```
astrbot-livingmemory/
├── core/
│   ├── event_handler.py           # 薄路由（~100行）
│   └── event_handler_modules/     # 注入式子模块
│       ├── message_handler.py
│       ├── memory_recall.py
│       └── memory_reflection.py
└── components/
    └── memory_engine.py           # 图记忆
```

**Codegraph 查询示例**：
```bash
# 查薄 handler 架构
codegraph explore "EventHandler on_message" -p ~/dev/references

# 查注入式子模块
codegraph explore "MessageHandler process" -p ~/dev/references
```

---

### 4. astrbot-persistent-memory（多重打分）

**路径**：`~/dev/references/bot-evolve-refs/astrbot-persistent-memory/`

**核心价值**：
- LanceDB 持久化
- 混合检索（向量 + BM25）
- 多重打分（recency/importance/time_decay）
- 作用域隔离（session/global/session+global）

**许可证**：MIT — 可安全参考代码

**关键文件**：
```
astrbot-persistent-memory/
├── src/
│   ├── memory_store.py            # LanceDB 存储
│   ├── retriever.py               # 混合检索 + 多重打分
│   └── decay.py                   # 时间衰减
└── tests/
    └── test_retriever.py          # 检索测试
```

**Codegraph 查询示例**：
```bash
# 查多重打分
codegraph explore "Retriever calculate_score" -p ~/dev/references

# 查作用域隔离
codegraph explore "MemoryStore get_scope" -p ~/dev/references
```

---

### 5. langbot-plugin-sdk（官方 SDK）

**路径**：`~/dev/references/bot-evolve-refs/langbot-plugin-sdk/`

**核心价值**：
- 官方 API 定义
- 插件开发规范
- 组件类型定义

**许可证**：Apache-2.0（runtime/ 目录为 AGPL，但不传染插件）

**关键文件**：
```
langbot-plugin-sdk/
├── src/langbot_plugin/
│   ├── api/
│   │   ├── plugin.py              # BasePlugin
│   │   ├── components/            # 组件类型定义
│   │   └── entities/              # 事件/上下文定义
│   └── runtime/                   # AGPL（不传染插件）
├── docs/
│   ├── plugin-api.md              # 插件 API 文档
│   └── component-types.md         # 组件类型文档
└── tests/
    ├── conftest.py                # 测试桩
    └── test_plugin.py             # 插件测试示例
```

**Codegraph 查询示例**：
```bash
# 查 BasePlugin API
codegraph explore "BasePlugin on_event" -p ~/dev/references

# 查组件类型
codegraph explore "EventListener Component" -p ~/dev/references
```

---

### 6. langbot-plugin-demo（官方示例）

**路径**：`~/dev/references/bot-evolve-refs/langbot-plugin-demo/`

**核心价值**：
- 官方插件示例集
- 各种组件类型的实现参考

**关键插件**：
- `daily-limit-plugin/` — 日限计数（可参考持久化）
- `faq-manager/` — FAQ 管理（可参考知识库）
- `keyword-alert/` — 关键词告警（可参考事件监听）

---

### 7. langbot-rag（官方 RAG）

**路径**：`~/dev/references/bot-evolve-refs/langbot-rag/`

**核心价值**：
- 官方 RAG 实现
- 向量存储/检索
- 嵌入模型调用

---

## 三、Codegraph 使用指南

### 基本命令

```bash
# 探索符号及其调用关系
codegraph explore "<symbol>" -p ~/dev/references

# 查询符号定义和引用
codegraph query "<symbol>" -p ~/dev/references

# 查看单个符号详情
codegraph node "<symbol>" -p ~/dev/references

# 查找调用者
codegraph callers "<symbol>" -p ~/dev/references

# 查找被调用者
codegraph callees "<symbol>" -p ~/dev/references
```

### 常用查询模式

```bash
# 查某类实现
codegraph explore "MemoryStore upsert" -p ~/dev/references

# 查测试桩实现
codegraph explore "FakePlugin vector_upsert" -p ~/dev/references

# 查架构模式
codegraph explore "EventHandler on_message" -p ~/dev/references

# 查特定功能
codegraph explore "DecayEngine calculate" -p ~/dev/references
```

---

## 四、许可证注意

| 许可证 | 项目 | 可否借鉴代码 |
|--------|------|-------------|
| **Apache-2.0** | langbot-longterm-memory, langbot-plugin-sdk, langbot-plugin-demo | ✅ 可安全使用 |
| **MIT** | astrbot-persistent-memory | ✅ 可安全使用 |
| **AGPL-3.0** | astrbot-livingmemory | ❌ 仅读思路，禁复制 |
| **无 LICENSE** | memory-lancedb-pro, langbot-rag | ⚠️ 参考机制，不直接搬代码 |

### AGPL 传染性说明

AGPL-3.0 要求：
- 如果你的代码使用了 AGPL 代码，必须开源
- 即使只是链接（静态/动态），也算使用

**应对**：
- astrbot-livingmemory：只读架构思路（薄 handler + 注入式子模块），不复制代码
- 自己实现类似架构，确保代码独立

### runtime/ 目录特殊性

langbot-plugin-sdk 的 `runtime/` 目录为 AGPL，但：
- 插件只 import `api/`、`components/`、`entities/` 等目录
- 这些目录为 Apache-2.0，不传染插件
- **安全**：正常使用 SDK API 不会触发 AGPL

---

## 五、更新日志

- 2026-07-11：初始创建，记录 7 个参考项目
- 2026-07-13：补充 Codegraph 查询示例
- 2026-07-14：完善许可证说明
