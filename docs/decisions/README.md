# 架构决策记录（ADR）

## DevFlow 框架

| 编号 | 文件 | 决策 | 状态 |
|------|------|------|------|
| ADR-008 | [008-green-side-gate-architecture.md](008-green-side-gate-architecture.md) | GREEN 侧门禁——双轴线扩展到实现侧，五层验证模型，防 AI reward hacking | ✅ 已采纳 |
| ADR-006 | [006-gate-architecture-principles.md](006-gate-architecture-principles.md) | 测试门禁体系设计原则——双轴线（形式+有效性）+ 通用防线优先 + 防御类别非实例 | ✅ 已采纳 |
| ADR-007 | [007-g0-reverse-mutation-testing.md](007-g0-reverse-mutation-testing.md) | G0 反向突变测试——测试有效性门禁（流程：C0-C7 → G0 → done） | ✅ 已采纳 |
| ADR-005 | [005-memory-system-feature-toggle.md](005-memory-system-feature-toggle.md) | 记忆体系作为 install.sh 的 `--memory` Feature Toggle | 📋 计划中 |

## Silent Observer 插件

以下 ADR 属于本仓库内的 LangBot 插件子项目（`docker/langbot/plugins/silent-observer/`）：

| 编号 | 文件 | 决策 | 状态 |
|------|------|------|------|
| ADR-001 | [001-plugin-directory-structure.md](001-plugin-directory-structure.md) | 插件目录结构选 `plugins/`，消除代码不一致 | ✅ 已采纳 |
| ADR-002 | [002-testing-strategy.md](002-testing-strategy.md) | 测试策略选核心层单测优先（三层金字塔） | ✅ 已采纳 |
| ADR-003 | [003-dependency-injection.md](003-dependency-injection.md) | 通过构造函数 DI 使核心逻辑可脱离 LangBot 独立测试 | ✅ 已采纳 |
| ADR-004 | [004-reject-qq-sillytavern.md](004-reject-qq-sillytavern.md) | 拒绝采用 QQ 酒馆插件（设计目标不匹配 + AGPL + 架构耦合） | ✅ 已采纳 |
