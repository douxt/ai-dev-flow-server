# ADR-003：可测性设计用依赖注入

**状态**：已采纳  
**日期**：2026-07-13  
**决策者**：项目维护者

## 背景

当前 default.py 的类（DefaultEventListener、ChatIndexStore、PromptBuilder 等）直接依赖 LangBot 运行时：
- 构造函数中通过 `self.plugin.get_vector_storage()` 获取存储实例
- 事件监听器方法接收 LangBot 事件对象
- 视觉识别直接调用 Qwen API

这导致：
1. 无法在不启动 LangBot 的情况下测试这些类
2. Mock 成本高（需要 Mock 整个 Plugin API）
3. 测试执行慢（需要初始化 LangBot 环境）

## 决策

采用 **依赖注入（Dependency Injection）** 模式，将 LangBot 运行时依赖从构造函数参数传入：

```python
# 重构前：紧耦合
class ChatIndexStore:
    def __init__(self):
        self.plugin = get_current_plugin()
        self.storage = self.plugin.get_vector_storage()

# 重构后：依赖注入
class ChatIndexStore:
    def __init__(self, storage):
        self.storage = storage
```

## 理由

1. **可测试性**：测试时传入 FakeStorage，无需 Mock LangBot API
2. **解耦**：核心逻辑与 LangBot 运行时分离，便于独立演进
3. **符合官方实践**：langbot-longterm-memory 的 store/ 层采用相同模式
4. **渐进式重构**：可以先重构 store/ 层，再逐步扩展到 service/ 和 components/

## 后果

### 正面
- 单元测试可以在毫秒级完成（无需初始化 LangBot）
- 测试覆盖率容易达到 80%+
- 代码更清晰，职责更明确

### 负面
- 需要修改现有类的构造函数签名
- 需要在 components/ 层传递依赖（增加一些样板代码）
- 重构工作量中等（约 2-3 天）

## 实施计划

1. 步骤 1：重构 store/ 层（ChatIndexStore、ReflectionStore）
2. 步骤 2：重构 service/ 层（VisionService、RetrievalService）
3. 步骤 3：在 components/ 层初始化并注入依赖
4. 步骤 4：编写单元测试（使用 FakePlugin 桩）

## 示例代码

```python
# store/kb.py
class KBStore:
    def __init__(self, vector_storage):
        self.vector_storage = vector_storage
    
    def save_message(self, session_id: str, message: dict):
        embedding = self._compute_embedding(message["text"])
        self.vector_storage.upsert(
            collection="chat_history",
            id=message["id"],
            vector=embedding,
            metadata={"session_id": session_id, **message}
        )

# service/vision.py
class VisionService:
    def __init__(self, llm_client, image_storage):
        self.llm_client = llm_client
        self.image_storage = image_storage
    
    def recognize_image(self, image_url: str) -> str:
        image_data = self.image_storage.download(image_url)
        prompt = self._build_prompt(image_data)
        return self.llm_client.call(prompt)

# components/event_listener/default.py
class DefaultEventListener:
    def __init__(self):
        plugin = get_current_plugin()
        
        # 初始化依赖
        vector_storage = plugin.get_vector_storage()
        llm_client = plugin.get_llm_client()
        image_storage = plugin.get_image_storage()
        
        # 注入依赖
        self.kb_store = KBStore(vector_storage)
        self.vision_service = VisionService(llm_client, image_storage)
```

## 相关 ADR

- ADR-001：插件目录结构选 plugins/
- ADR-002：测试策略选核心层单测优先

## 参考资料

- [Dependency Injection in Python](https://realpython.com/dependency-injection-python/)
- [langbot-longterm-memory store 层实现](https://github.com/langbot-app/langbot-longterm-memory/tree/main/store)
