# ADR-002: --hetero 异构双层评审——单实例内 lead 指挥 pack

## 状态：已采纳
## 日期：2026-08-28

## 背景

`--parallel` 已在（外层主会话编排 N 个同模型独立 `claude -p`）。新需求：单实例内一个主模型（lead）并行派发子代理（pack，可为不同模型）分维评审 + 主模型亲自综合评审，一次上报。典型场景：qwen 开发会话中，deepseek-v4-pro 指挥官带 deepseek-v4-flash 兵做异构评审。

实测前置：headless `claude -p` 具备 Agent 工具可派子代理；`CLAUDE_CODE_SUBAGENT_MODEL` 控制子代理模型；`modelUsage` 按模型分键独立记账；子代理与指挥官**同进程**（fan-out 不放大 /proc 暴露面）。

## 决策

1. **与 `--parallel` 并存互补，不替代**：大 diff / 需独立 verifier 硬隔离 → parallel；异构组合 / 外层上下文省心 / 中小范围 → hetero。二者定位差异写进 README 选择指引
2. **零参数默认链**：lead = `--lead`（=`--model`）> profile.model > opus 别名解析值；pack = `--pack` > profile.pack_model > haiku 别名解析值；**provider 激活时缺 model/pack_model 一律禁止回退继承别名**（跨网关模型名必错），前者硬失败、后者 pack:=lead + 同质警告
3. **防模型泄漏 = 五路 env 全覆盖**（ANTHROPIC_MODEL + 三别名 + SUBAGENT）：实例内 Agent 工具的 alias 参数会经继承 env 解析回原网关模型，必须封死；**防泄漏判定 = `modelUsage` 键集合恰好 == {lead, pack}**，混入第三键整单失败不采信——账本不可伪造，比口头承诺可靠
4. **防敷衍 = 结构断言**：聚合 JSON 五来源键恒在（4 维 + lead_review）+ 各键 inputTokens>0 + merged 抽查对质
5. **权限防线承认是 prompt 软约束**（关键诚实决策）：双探针实测子代理不继承 file-guard/bash-firewall 钩子、无约束时可写任意文件——故只读句硬性植入**每个子代理 prompt**（非仅指挥官），文档禁止写成"已拦截"，声明可被高强度注入绕过
6. 默认一次评审；`--hetero --loop`/`--parallel` 互斥报错（多轮需求回串行 loop）
7. 超时特例 900s + run_in_background（单实例承载 ~5 head）

## 后果

- fixture 实测：pro 帅带 flash 兵对 10 bug 答案卷 **9/9 零漏报零诱饵污染**，超 qwen-parallel 的 8/9 基线
- 认知修正记录在案：hetero 省外层上下文与融合质量，**不省 token**（子代理同样背 ~60K input 底重）——立项时的"省 5×boilerplate"预期被实测推翻
- `--rubric` 在 hetero 下语义收窄为"兵维度子集 + 非维度 rubric 归指挥官"，五键 schema 不变
- 自审环节（用 --hetero 评审本规范 diff，即吃狗粮）发现 18 处规格缺陷，确立"文档即产品"类改动合并前跑 spec 级自审的惯例

## 拒绝的方案

- **替代 --parallel**：失去独立 verifier 与部分失败降级面，异构场景不该以砍重型模式为代价
- **命名 `--team`**：与 parallel 的多实例阵列语义撞车，"异构"才是区分点（候选 hetero/lead/tiers/pack，取 hetero，子参数借 lead/pack 意象）
- **按维度差异化配兵**（每维不同模型）：组合爆炸进兼容矩阵，单 pack 全局统一已覆盖主诉求
- **子代理写权限靠 settings 传导**：实测不成立（决策 5），曾考虑给 settings-review.json 加 Task 白名单——管不住子代理层，无效改动
- **N 层嵌套指挥链**：账本断言与权限防线都按单层设计，嵌套使 modelUsage 判定失效
