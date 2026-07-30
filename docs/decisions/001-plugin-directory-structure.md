# ADR-001：插件目录结构选 plugins/

**状态**：已采纳  
**日期**：2026-07-13  
**决策者**：项目维护者

## 背景

Silent Observer 插件当前存在两份代码：
- 根目录 `default.py`（1085 行，含 vision）
- `docker/langbot/plugins/silent-observer/components/event_listener/default.py`（613 行，无 vision）

两份代码不一致，导致修改容易遗漏，部署时也容易混淆。

## 决策

采用 **plugins/ 目录结构**，作为唯一源：

```
plugins/silent-observer/
├── main.py                    # 插件入口
├── manifest.yaml              # 插件元数据
├── requirements.txt           # 依赖声明
├── components/
│   └── event_listener/
│       ├── default.py         # 事件监听器（薄）
│       └── manifest.yaml
├── store/                     # 数据存储层
│   ├── kb.py                  # 知识库读写
│   └── reflection.py          # 反思记录存储
├── service/                   # 业务逻辑层
│   ├── vision.py              # 视觉识别
│   └── retrieval.py           # 检索逻辑
└── tests/                     # 测试
    ├── conftest.py            # FakePlugin 桩
    └── test_*.py
```

## 理由

1. **单一源原则**：plugins/ 是唯一源，docker/ 和根目录的 default.py 将被废弃
2. **官方规范**：符合 LangBot 官方插件目录结构（参考 langbot-plugin-demo）
3. **可维护性**：职责分离（components/store/service/tests），便于重构和测试
4. **可测试性**：tests/ 目录内置，配合 FakePlugin 桩实现单元测试

## 后果

### 正面
- 消除两份代码不一致的问题
- 便于渐进式重构（从 default.py 逐步提取到 store/service）
- 符合社区标准，新人易理解

### 负面
- 需要一次性迁移工作（根目录 default.py → plugins/）
- 部署流程需要调整（从根目录改为 plugins/）

## 实施计划

详见 [ground-reconstruction-plan.md](../bot/ground-reconstruction-plan.md) 步骤 0-7。

## 相关 ADR

- ADR-002：测试策略选核心层单测优先
- ADR-003：可测性设计用依赖注入
