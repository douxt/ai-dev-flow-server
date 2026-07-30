---
name: characterize
description: 遗留代码特征测试——改旧代码前先锁当前行为，建安全网后安全改动。触发：/characterize、[legacy] ticket、零测试覆盖文件改动前。
---

# 遗留代码特征测试

## 原则

> **Cover and Modify，非 Edit and Pray。** — Michael Feathers

特征测试捕获代码"当前实际行为"——不关心对不对，只关心"改了之后不变"。与 TDD 的本质区别：

| | TDD | 特征测试 |
|--|-----|---------|
| 测什么 | 期望行为（应该怎样） | 当前行为（现在怎样） |
| RED/GREEN | RED 先（代码不存在） | **立即 GREEN**（证明理解正确） |
| 断言 | 业务正确性 | 行为快照 |

## 四阶段流程

```
/characterize（特征测试）→ 预重构（打破依赖）→ /tdd → /implement（实际改动）→ 后重构
```

P1 只做第一阶段。预重构和后重构在后续版本中实现。

## 执行步骤

### STEP 1: ANALYZE — 理解代码

读目标代码，输出：
- 公共接口（函数签名/API 端点/组件 props）
- 接缝点（不改源码就能改变行为的点）
- 外部依赖（DB/文件/网络调用）
- 副作用（写操作/状态变更）

用接缝决策表选择测试方式：

| 代码类型 | 推荐接缝 | 特征测试方式 |
|---------|---------|------------|
| HTTP API 端点 | URL 路径 | HTTP 探针 + JSON 快照 |
| 纯函数/工具函数 | 函数签名 | 参数-返回值录制 |
| DB 写入操作 | 函数前后 DB 状态 | SELECT 对比 |
| 多层调用链 | 最外层公共接口 | 全输出录制（胖测试） |

### STEP 2: CAPTURE — 捕获行为

1. 在 `tests/characterization/` 下创建测试文件，命名：`<ticket-id>-<feature>_test.*`
2. 写特征测试——运行被测代码，记录实际输出
3. 断言当前行为（快照对比 / 返回值断言 / DB 状态对比）
4. **铁律：特征测试必须立即 GREEN**

如果 RED：
- 先判断是否基础设施故障（connect refused / timeout）→ 标记 `[infra]`，修复环境
- 否则是你理解错了代码行为 → 修测试，不修代码

### STEP 3: VERIFY — 验证安全网

**元验证**：确认特征测试真的在起作用。

1. 临时修改被测代码一行（如改返回值）
2. 跑特征测试 → **必须变 RED**
3. 恢复修改 → **必须恢复 GREEN**

不通过 → 特征测试有问题，修复后重新验证。

### 技术栈速查

| 栈 | 快照方案 | 工具 |
|----|---------|------|
| PHP | HTTP 探针 → JSON 快照 | `file_get_contents` + `assertJsonStringEqualsJsonFile` |
| Node/React | 组件渲染快照 | Vitest `toMatchSnapshot()` |
| Python | API 响应快照 | pytest-syrupy |
| Go | 输出 golden file | `testdata/` + `go test` |
| DB 密集 | SELECT 结果集对比 | 专用测试库 + fixture |

> 详细步骤见各栈模块：`knowledge/stacks/<stack>/legacy-characterization.md`
> 完整规则见：`knowledge/11-遗留代码特征测试.md`
> 门禁清单见：`gate-checklists/characterization-checklist.md`

## 生命周期

```
创建（/characterize）
  → 验证（改代码确认变红→恢复）
    → 执行（锁行为，安全改代码）
      → 调和（有意变更行为时，更新快照 + 记录原因）
        → 退役（新 TDD 测试覆盖同一路径后，删除特征测试）
```

## 产物

- `tests/characterization/<ticket-id>-<feature>_test.*` — 特征测试文件
- `tests/characterization/snapshots/` — 快照文件（如有）
