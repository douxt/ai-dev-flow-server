# ADR-005: 记忆体系作为 ai-dev-flow-server 的 Feature Toggle（层次 1）

## 状态：计划中（后续实施）
## 日期：2026-07-16
## 背景

基于 [ADR-001 跨会话记忆体系](/home/dou/.claude/plans/decisions/ADR-001-claude-memory-system.md) 已建成 8-script 全局记忆体系（mem-stop/mem-backup/mem-scan/mem-session-start/mem-precompact/mem-report/mem-setup/mem-common），hook 注册在用户级 `~/.claude/settings.json`，符链指向 claude-config 仓库。

ai-dev-flow-server 已有成熟的自动化配置体系（`install.sh` → `config-templates/default/settings.json` + `.devflow/config.yaml`），但目前两套体系完全独立：install.sh 只管它的 5 个基础 hook，与记忆体系的 4 个 hook 无互调。社区实践表明，成熟的自动化配置应把记忆沉淀作为可选的 feature toggle。

## 决策（层次 1：模板化）

**不合并两套代码库**（记忆体系仍住 claude-config），仅让 ai-dev-flow-server 的 installer 通过一个开关来**认领**记忆 hook 注册。

具体手段：

1. 新建 `config-templates/default/memory-hooks.json`：存放 4 个记忆 hook 的 settings.json 注册片段（可独立 merge 到项目目标 settings.json）
2. `install.sh` 新增 `--memory on|off` 开关（默认 `on`）
   - `--memory on`：在安装 settings.json 步骤后，用 jq 合并 memory-hooks.json 进目标 settings.json
   - `--memory off`：跳过
3. `uninstall.sh` 反向移除（检测到目标 settings.json 含记忆 hook 时移除对应段）
4. 单测：install.sh --dry-run --memory on/off 对比输出

## 后果

- 新项目安装时可一键选择是否带记忆沉淀能力
- 个人 global 级部署方式不变（`~/.claude/settings.json` 手工版不冲突）
- 为层次 2（config.yaml 管控）和层次 3（install.sh 认领 mem-setup 全套流程）留下接口

## 实施要点

- `config-templates/default/memory-hooks.json` 格式：单个 JSON 对象，包含 `SessionStart`（追加 mem-session-start）、`Stop`（新增）、`PreCompact`（新增）、`PostToolUse`（Edit\|Write 追加 mem-backup）四个 hook 注册
- install.sh 合并时机：在"安装 CC settings/hooks/CLAUDE.md"步骤之后（`install_mode_settings_and_hooks` 阶段）
- 合并方式：`jq -s '.[0] * .[1]' 目标文件 模板文件`，与现有 install.sh 的 jq 用法一致
- 卸载检测：grep `mem-session-start|mem-stop|mem-precompact|mem-backup` 后 jq 反选删除
- 不影响 `--no-config` 现有行为：`--no-config` 时一切 settings 变更跳过，记忆段自然也不写入
- 若目标项目已装了记忆体系（已注册过 4 个 hook），`--update` 模式应幂等（jq merge 本身就幂等）

## 拒绝的方案

- **把记忆脚本 move 到 ai-dev-flow-server**：记忆体系是跨项目基础设施，搬进单个项目仓库违背其定位；且记忆脚本的符链和 claude-config 维护模式已成熟
- **默认 off**：记忆沉淀是非侵入能力（最差结果就是不沉淀，不影响正常干活），和 AI 工具链的定位一致，默认 on 更合理
- **只给开关不做模板**：那 install.sh 就要知道记忆 hook 的具体命令路径，把 claude-config 的内部细节泄露进 ai-dev-flow-server 的维护范围
- **一步做到层次 2/3**：过早。层次 2（config.yaml 管控）等需求驱动（AFK 管线需要自适应开关）；层次 3（认领全流程）等这套体系被其他项目采用时再投入
