# ai-dev-flow-server

DevFlow 元框架——通过 `install.sh` 一键为目标项目装上 Gate 流程 + AFK 自动化管线 + 质量宪法体系的约束模板仓库。

## 双重身份

| 身份 | 说明 |
|------|------|
| **DevFlow 约束模板** | install.sh → config-templates/ + skills-cache/ + templates/ 安装到目标项目 |
| **LangBot 插件仓库** | `docker/langbot/plugins/silent-observer/` — QQ 群聊反思 Bot（与本框架独立） |

## 目录结构

```
install.sh              # 通用安装器（三种模式 × 四种调度器）
config-templates/       # settings.json / hooks / CLAUDE.md 模板（安装到目标项目）
templates/              # .gate-state / CLAUDE.md.append / 角色模板 / issue 模板
skills-cache/           # 15 个 CC skill 离线缓存 + sync-skills.sh
scripts/devflow         # 角色管理 CLI（owner/developer/agent-b）
tests/                  # bats-core 测试套件（17 文件 60 用例）

docs/
├── design/             # Gate 设计 + AFK 迭代史
├── plans/              # 历史设计计划（部分已落地）
├── decisions/          # ADR 001-005（架构决策记录）
├── references/         # Archon / CLAUDE.md / 基础设施参考
├── business/           # PRD + 业务文档
└── bot/                # Silent Observer 插件文档（独立子系统）

docker/langbot/plugins/silent-observer/  # Bot 插件代码
```

## 文档入口

[docs/README.md](docs/README.md) → 子目录各有 README 索引。

## 开发要点

### 模板改动影响面大

`config-templates/` 和 `templates/` 的改动会通过 `--update` 传播到所有已安装项目。改前确认：
- 不破坏已有项目的 `config.yaml` 兼容性
- 不覆盖 `.gate-state`（install.sh 已保证，但需验证）
- 新增字段给默认值，旧配置能降级运行

### 测试

```bash
bash tests/run_tests.sh              # Alpine + Ubuntu 双发行版
bash tests/run_tests.sh -f "update"  # 过滤单个测试
```

### 版本发布

1. 更新 CHANGELOG.md
2. 打 tag：`git tag v2.x`
3. 推送：`git push --tags`
4. 已安装项目用 `bash install.sh <项目> --update` 增量升级

## 部署架构（服务器版）

```
dispatch.timer（每 5 分钟）
  → dispatch.sh 扫描 issues/ 找 ready
  → check_constitution.py 7 项机器检查
  → 原子抢占（ready → in_progress）
  → archon run auto-execute-afk
    → implement → validate → auto-review → cross-review → merge-reviews → create-pr
  → Telegram 通知
```

目标项目管线详情见 [docs/design/gate-design.md](docs/design/gate-design.md)。

## Bot 子项目

Silent Observer 有独立开发流程（地基重建 7 步 + 四级进化路线），文档在 [docs/bot/](docs/bot/)，入口 [docs/bot/project-overview.md](docs/bot/project-overview.md)。
