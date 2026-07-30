# ADR-007: G0 反向突变测试——测试有效性门禁

## 状态：已采纳
## 日期：2026-07-30

## 背景

UMES3 项目三次出现"47/47 GREEN → 手工'参数缺失'"（见 [ADR-006](./006-gate-architecture-principles.md)）。现有 C0-C7 门禁全部检查"测试长得像测试吗"，无一条检查"测试能拦住 Bug 吗"。

学术上称为 **Rotten Green Tests**（ICSE 2019）：测试通过但不执行任何有效断言，在成熟代码库中可"休眠"5 年以上。对 26 个 Java 开源项目检测发现 ~420 个 rotten tests。

业界标准方案是 **Mutation Testing**（StrykerJS 等），但对 Playwright E2E 测试无自动化工具支持。EuroSTAR 2026 提出 **Reverse Mutation Testing (RMT)**——手动破坏被测代码，验证测试必须失败。零工具依赖，5 分钟/次。

## 决策

在 `/implement` 完成后、`done` 标记前，增加 **G0 故障注入验证**。

### 流程定位

```
/implement GREEN → C0-C7 → G0 → 人工确认 → done
```

### 操作步骤

| # | 步骤 | 操作 |
|:--|------|------|
| G0.1 | 选目标 | 选一条核心用户路径的测试（E2E 或集成测试） |
| G0.2 | 注入故障 | 在被测代码中改一个关键值（参数名/字段名/条件值），使功能必错 |
| G0.3 | 验证 RED | 跑该测试，**必须失败**。若仍通过 → 断言不够强 → 修复断言后重试 G0.2 |
| G0.4 | 恢复 | 撤销故障注入，测试重新 GREEN |

### 注入规则

| 层级 | 注入方式 | 示例 |
|------|---------|------|
| E2E | 改前端 handler 中的参数名 | `sale_id` → `saleId_typo` |
| API 集成 | 改后端 action 返回值字段名 | `code` → `status_code` |
| 单元 | 改函数返回值 | `return items` → `return []` |

**注入的故障产生的影响必须是用户可感知的错误**（页面报错/数据不显示/操作失败）。如果注入不影响用户可感知结果，该测试不适用 G0（记录即可）。

### 范围与级别

- **范围**：每个 feature 选 1 条核心路径测试（不要求全覆盖）
- **级别**：⚠️ 警告（advisory）——与 C7 同级，需人工审查，不自动阻断
- **豁免**：`[hotfix]` ticket 跳过 G0；纯数据迁移/配置变更 `[no-test]` 不适用

## 后果

- 门禁体系从单轴线（形式正确性）扩展为双轴线（形式 + 有效性），覆盖 C0-C7 的全部盲区
- G0 作为通用防线，减少特化门禁（C8/C9/C10…）的追加需求（见 ADR-006 原则 3）
- 每次 `/implement` 增加约 5 分钟人工/自动时间
- G0 用例（每次注入什么、测试是否失败）可积累为项目知识，供后续 ticket 参考

## 未来演进

- 当分层测试（Phase 3）落地后，API 集成测试可引入自动化 Mutation Testing（StrykerJS + Vitest）
- E2E 层 G0 保持人工——自动化 E2E 突变工具不存在，且短期无望

## 拒绝的方案

- **自动化突变测试全覆盖**：StrykerJS 不支持 Playwright E2E（[GitHub issue #5286](https://github.com/stryker-mutator/stryker-js/issues/5286)），Stryker + Vitest Browser Mode 在 Vitest v2 后已损坏。对纯 E2E 项目无自动化方案
- **新增 C8/C9/C10 特化检查**：违背 ADR-006 原则 3，会陷入"伤疤"增长循环
- **不做任何事**：三次"全部 GREEN → 手工失败"已证明盲区真实存在
