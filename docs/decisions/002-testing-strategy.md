# ADR-002：测试策略选核心层单测优先

**状态**：已采纳  
**日期**：2026-07-13  
**决策者**：项目维护者

## 背景

Silent Observer 插件当前没有正式的测试体系。虽然有 `e2e_test.py`，但只是简单的端到端冒烟测试，无法覆盖核心逻辑（如 KB 读写、视觉识别、反思机制）。

直接编写单元测试面临挑战：
- 插件依赖 LangBot 运行时（Plugin API、事件系统）
- 需要 Mock 大量外部服务（ChromaDB、Qwen API、文件存储）
- 现有代码（1085 行 default.py）耦合度高，难以隔离测试

## 决策

采用 **核心层单测优先** 策略，配合 **依赖注入** 实现可测试性：

1. **测试分层**：
   - L1 核心层（store/service）：单元测试，覆盖率 >80%
   - L2 集成层（components）：集成测试，验证组件协作
   - L3 端到端：E2E 测试，验证完整流程

2. **技术选型**：
   - 测试框架：`pytest` + `pytest-asyncio`
   - Mock 工具：`unittest.mock.AsyncMock`
   - 覆盖率：`pytest-cov`，核心层阈值 80%

3. **FakePlugin 桩**：
   - 在 `tests/conftest.py` 中定义
   - 模拟 LangBot Plugin API（向量存储、LLM 调用、事件系统）
   - 所有核心层测试通过依赖注入使用此桩

4. **Approval Testing**：
   - 对 prompt 组装逻辑使用 Approval Testing
   - 确保 prompt 变更不会意外破坏行为

## 理由

1. **风险最低**：核心层（store/service）是纯逻辑，不依赖 LangBot 运行时，最容易测试
2. **价值最高**：核心层包含关键业务逻辑（反思机制、视觉识别），测试收益最大
3. **渐进式**：先测核心层，再逐步扩展到集成层和 E2E，避免一次性投入过大
4. **符合官方实践**：langbot-plugin-sdk 和 langbot-longterm-memory 都采用类似策略

## 后果

### 正面
- 核心逻辑有测试保护，重构时不易引入回归
- FakePlugin 桩可复用，后续插件开发也可使用
- 测试驱动开发（TDD）成为可能

### 负面
- 需要重构现有代码（提取 store/service，注入依赖）
- 初期测试编写成本较高
- 集成层和 E2E 测试仍依赖真实 LangBot 环境

## 实施计划

1. 步骤 0：创建 tests/ 目录和 conftest.py（FakePlugin 桩）
2. 步骤 1：为 store/ 编写单元测试
3. 步骤 2：为 service/ 编写单元测试
4. 步骤 3：为 components/ 编写集成测试
5. 步骤 4：保留并增强 e2e_test.py

## 相关 ADR

- ADR-001：插件目录结构选 plugins/
- ADR-003：可测性设计用依赖注入

## 参考资料

- [langbot-plugin-sdk 测试示例](https://github.com/langbot-app/langbot-plugin-sdk/tree/main/tests)
- [pytest-asyncio 文档](https://pytest-asyncio.readthedocs.io/)
- [Approval Testing 介绍](https://approvaltests.com/)
