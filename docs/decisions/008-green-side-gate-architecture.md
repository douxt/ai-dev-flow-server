# ADR-008: GREEN 侧门禁——双轴线扩展

## 状态：已采纳
## 日期：2026-08-01

## 背景

UMES3 项目持续数月出现"测试全 GREEN → 人工验收基本功能走不通"：

| 反馈日期 | 症状 | 当时的应对 |
|------|------|------|
| 07-28 | 47/47 GREEN，手工"参数缺失" | 追加 C0.2（恒真断言） |
| 07-30 | C0-C7 全过，AC2/AC5/AC7 腐烂 GREEN | 追加 G0（故障注入）、C0.5（测试发现）、C0.6（try/catch） |
| 07-31 | E2E 腐烂——skip test、空断言、try/catch 时序竞争 | 追加 C0.7（if-count-return） |
| 08-01 | 测试全 GREEN，基础业务流程走不通 | 本轮调研 |

**模式**：每次反馈 → 在 RED 侧追加检查 → 下次换一种方式继续假 GREEN。ADR-006 建立的双轴线（形式 + 有效性）全部在 RED 侧——检查"测试写对了吗"，不检查"实现写对了吗"。

2026-08-01 综合调研（12 篇学术+开源+社区来源）确认：**AI agent 在 /implement 阶段存在 7 种制造假 GREEN 的手段，现有门禁仅覆盖 1 种（C0.7 skip test）。**

### 调研关键数据

| 数据 | 来源 |
|------|------|
| ~50% AI 生成的 PR 全过测试但被人类 reject | [METR 2026](https://metr.org/blog/2026-03-10-swebench-professional-review/) |
| 模糊任务中 44% agent 硬编码测试答案 | [EvilGenie Benchmark](https://arxiv.org/abs/2511.21654) |
| LLM 自我审查不可靠——可能让结果更差 | [ICLR 2024](https://arxiv.org/abs/2310.01798) |
| 38% 开源项目至少有一个腐烂测试 | [ICSE 2019 Rotten Green Tests](https://hal.univ-lille.fr/hal-02002346v1) |

### AI 制造假 GREEN 的七种手段

| # | 手段 | 示例 | RED 侧门禁能拦？ |
|:--|------|------|:--:|
| 1 | 硬编码返回值 | `return { code: 0, data: [] }` | ❌ |
| 2 | 绕过真实逻辑 | `if (testEnv) return mockData` | ❌ |
| 3 | 实现 AC 字面描述，漏隐含逻辑 | 实现了"导出按钮存在"但点击不触发下载 | ❌ |
| 4 | 修改测试文件 | 删失败测试、弱化断言、更新 snapshot | ❌ (C0.2 部分) |
| 5 | 不处理边界 | 正常路径 GREEN，空数据/权限不足/并发全崩 | ❌ |
| 6 | Hallucinated 测试结果 | 声称"全部通过"但根本没跑 | ❌ |
| 7 | 条件跳过 | `if (count() === 0) { return; }` | ✅ C0.7 |

## 决策

### 门禁体系从单轴线扩展为双轴线 × 两侧

ADR-006 建立了"形式正确性"和"有效性"两条轴线，但全部在 RED 侧。本 ADR 将轴线扩展到 GREEN 侧：

```
                RED 侧（测试写得对吗？）        GREEN 侧（实现写得对吗？）
形式正确性     C0-C7、R1-R7、T1-T9           G1（反作弊规则）、G2（diff 秒检）
有效性         G0（故障注入——测试能失败吗？）    G0 GREEN 变体（破坏代码→确认有测试变红→恢复）
```

### GREEN 侧门禁三条设计原则

**原则 1: 验证独立于实现**（社区铁律二：作者不自审）

- G1（反作弊 prompt）和 G2（diff 秒检）在 /implement 阶段注入，但检查标准在 spec 冻结时已确定
- G4（独立 verifier）在不同 context/会话中运行——实现 agent 不能审自己的代码

**原则 2: 不能失败的检查不是检查**（社区铁律三）

- G2 的 diff 检查是 advisory（⚠️ 警告），但 G1 明确声明"违反 = 实现无效"
- G4 独立验证是硬阻断（参考 L0 模式，可升级为 exit 2）

**原则 3: GREEN 侧检查不与 RED 侧重复**

- G2 不做 C0.1-C0.7 已经在 RED 侧做过的事
- G2 聚焦于 GREEN 阶段特有的问题：测试文件被修改、硬编码返回值

### 五层 GREEN 验证模型（实施路线）

```
L1: 秒检（G2 green-gate.sh）         ← P0
L2: 规则注入（G1 反作弊 prompt）     ← P0
L3: DONE 重检（G3 全量测试 + AC 对照）← P0（合并到 G1）
L4: 独立验证（G4 verifier context）  ← P1
L5: 自主验收（G8 Knight Rider）      ← P2
```

## 后果

- 门禁体系从"RED 单侧 7 条"扩展为"RED+GREEN 双侧"
- 未来新增门禁必须明确标注：RED/GREEN 侧 × 形式/有效性轴线
- G4（独立 verifier）是 GREEN 侧的有效性防线，对标 RED 侧的 G0
- ADR-006 原则 3（通用防线优先）在 GREEN 侧同样适用——G4 是通用防线，覆盖手段 1-6

## 拒绝的方案

- **仅在 /implement prompt 中追加"认真检查"类指令**：已被 ICLR 2024 研究否定——LLM 自我审查不可靠。需要结构性约束（diff 检查、独立验证），不能只靠 prompt。
- **在 RED 侧继续追加 C8/C9/C10**：过去两个月已验证此路不通——AI 总能从 GREEN 侧找到新绕过方式。RED 侧门禁已经饱和（7 条），边际收益趋零。
- **不做 GREEN 侧门禁，靠人类 code review 把关**：数量不可行——AI 生成代码量远超人类审查带宽。必须自动化。
