# 重构方法论：Silent Observer 插件

> 适用场景：大规模重构遗留代码，特别是不可测试的闭包式插件代码

## 一、两条铁律

### 1. Characterization 测试先行（安全网）

**原则**：动任何生产代码前，先用真实输入锁定现有行为为 golden master，再抽取。

**工具**：pytest + approval testing（序列化完整输出 + diff）

**示例**：
```python
# tests/approval/test_gate_output.py
import pytest
from pathlib import Path

@pytest.mark.asyncio
async def test_gate_inject_output_approval():
    """录制 gate/inject 输出的 prompt、KB metadata 作为安全网"""
    # 1. 准备真实输入（从生产环境录制的 message_chain）
    input_data = load_approval_input("gate_inject_20260711")
    
    # 2. 执行当前代码
    result = await run_gate_inject(input_data)
    
    # 3. 序列化完整输出
    output_json = json.dumps(result, indent=2, ensure_ascii=False)
    
    # 4. 与 golden master 对比（首次运行自动生成 .approved.json）
    approval_file = Path(__file__).parent / "gate_inject_20260711.approved.json"
    if approval_file.exists():
        approved = approval_file.read_text()
        assert output_json == approved, "输出变化，请检查是否为预期改动"
    else:
        # 首次运行，保存为 golden master
        approval_file.write_text(output_json)
        pytest.skip("生成 approval 文件，请检查后提交")
```

**关键**：
- 首次运行生成 `.approved.json`，人工检查后提交
- 后续重构时，若输出变化，测试失败 → 检查是否为预期改动
- 若是预期改动，更新 `.approved.json` 并重新提交
- 若非预期改动，回滚代码

### 2. 结构提交与行为提交分离

**原则**：一个 commit 要么改结构（纯抽取，特征测试必须保持绿），要么改行为（修 P0，允许改测试），绝不混。

**提交循环**：5–15 分钟一提交，超 1 小时没提交 = 改动太大

**示例**：
```bash
# ✅ 正确：结构提交（纯抽取，不改逻辑）
git commit -m "refactor: extract vision service from default.py"

# ✅ 正确：行为提交（修 P0，允许改测试）
git commit -m "fix: persist vision_daily_count to plugin_storage"

# ❌ 错误：混合提交
git commit -m "refactor: extract vision service and fix persistence"
```

---

## 二、Strangler 模式

**原则**：逐步替换，不一次大爆炸。每步保持可运行完整插件，非到末步才能跑。

**步骤**：
1. **识别接缝**：找到可以独立抽取的模块边界（如 store、service、util）
2. **创建新模块**：在 `plugins/silent-observer/` 下新建 `store/`、`service/`、`util/`
3. **逐步迁移**：每迁移一个模块，立即补测试，确保 pytest 绿
4. **灰度切换**：先在测试群验证，再切生产群
5. **删除旧代码**：迁移完成且稳定后，删除 `default.py` 中的旧代码

**关键约束**：
- 单 event_listener 组件限制（LangBot 约束）
- 生产在跑，每步真机验证
- AGPL 许可证红线（livingmemory 仅读思路，禁复制）

---

## 三、测试金字塔

```
        ┌──────┐
        │ E2E  │  ← 完整链路（消息→gate→inject→LLM→回复→QQ群）
       ┌┴──────┴┐
       │ 集成测试 │  ← napcat HTTP API 直接发消息
      ┌┴────────┴┐
      │ 单元测试  │  ← FakePlugin 桩，脱离 LangBot 运行时
      └──────────┘
```

### 单元测试（核心）

**工具**：pytest + pytest-asyncio + pytest-cov

**FakePlugin 桩**（`tests/conftest.py`）：
```python
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def fake_plugin():
    """模拟 LangBot Plugin API，让 service/store 脱离运行时单测"""
    plugin = AsyncMock()
    
    # 向量操作
    plugin.invoke_embedding = AsyncMock(return_value=[[0.1] * 384])
    plugin.vector_upsert = AsyncMock()
    plugin.vector_search = AsyncMock(return_value=[
        {"id": "chat:abc123", "distance": 0.5, "metadata": {"text": "测试消息"}}
    ])
    plugin.vector_list = AsyncMock(return_value={"items": []})
    plugin.vector_delete = AsyncMock()
    
    # LLM 调用
    plugin.invoke_llm = AsyncMock(return_value=Mock(content="AI 回复"))
    
    # 持久化
    plugin.set_plugin_storage = AsyncMock()
    plugin.get_plugin_storage = AsyncMock(return_value=b'{}')
    
    # 配置
    plugin.get_config = AsyncMock(return_value={
        "kb_id": "test-kb",
        "embedding_model_uuid": "test-model",
        "vision_enabled": False
    })
    
    return plugin
```

**测试示例**：
```python
# tests/test_kb_store.py
import pytest

@pytest.mark.asyncio
async def test_kb_store_upsert(fake_plugin):
    """测试 KB 写入"""
    from plugins.silent_observer.store.kb_store import KBStore
    
    store = KBStore(plugin=fake_plugin)
    await store.upsert("chat:abc123", "测试消息", {"sender": "user1"})
    
    # 验证调用
    fake_plugin.vector_upsert.assert_called_once()
    call_args = fake_plugin.vector_upsert.call_args
    assert call_args.kwargs["collection_id"] == "test-kb"
    assert call_args.kwargs["ids"] == ["chat:abc123"]
```

### 集成测试

**工具**：napcat HTTP API（端口 3000）

**示例**：
```bash
# 直接发消息到 QQ 群（以 bot 身份）
curl -X POST http://localhost:3000/send_group_msg \
  -H "Content-Type: application/json" \
  -d '{"group_id": 1104330614, "message": "测试消息"}'
```

### E2E 测试

**工具**：完整链路（消息→gate→inject→LLM→回复→QQ群）

**示例**：参考 `e2e_test.py`（已有）

---

## 四、质量门配置

### pyproject.toml

```toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]
ignore = ["E501"]  # 行长度由 formatter 控制

[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.coverage.run]
source = ["plugins/silent_observer"]
omit = ["tests/*"]

[tool.coverage.report]
fail_under = 70  # 覆盖率阈值
```

### .pre-commit-config.yaml

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.5.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests, types-PyYAML]
  
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
```

---

## 五、关键约束

### 1. 单 event_listener 组件限制

LangBot 约束：每个插件只能有一个 event_listener 组件。

**应对**：逻辑抽到普通模块（store/service/util），event_listener 只做路由。

### 2. 生产在跑

每步必须保持可运行完整插件，非到末步才能跑。

**应对**：
- 灰度切换：先在测试群验证，再切生产群
- 备份回滚：切换前备份容器现行 default.py

### 3. AGPL 许可证红线

livingmemory 是 AGPL-3.0，仅读思路，禁复制代码。

**应对**：参考架构设计（薄 handler + 注入式子模块），但不直接搬代码。

---

## 六、参考资源

- [Michael Feathers - Working Effectively with Legacy Code](https://www.amazon.com/Working-Effectively-Legacy-Michael-Feathers/dp/0131177052)
- [Martin Fowler - Strangler Fig Pattern](https://martinfowler.com/bliki/StranglerFigApplication.html)
- [pytest-asyncio 文档](https://pytest-asyncio.readthedocs.io/)
- [ruff 配置指南](https://docs.astral.sh/ruff/configuration/)
