# ai-dev-flow-server — 服务器端 AI 开发流程约束模板

AI Dev Flow 的服务器版。将 10-Gate Step-Gate 开发框架适配到服务器项目，提供 **gate 流程 + AFK 自动消化管线**。

```
ai-dev-flow（本地版）→ 人在本地 Claude Code 终端操作
ai-dev-flow-server（服务器版）→ 人在 OpenLobby / Web CC 操作，AFK 由 dispatch+Archon 自动消化
```

## 与本地版的差异

| | 本地版 | 服务器版 |
|------|------|------|
| **运行环境** | 本地 CC 终端 | OpenLobby（手机浏览器） |
| **gate 触发** | 人敲 `/gate-X` | 同左（路径适配后） |
| **AFK 执行** | `ralph-once.sh` 本地循环 | dispatch.sh + Archon workflow |
| **审批** | 无 | notify.py 直连 Telegram |
| **部署** | `install.sh` 装到本地项目 | `install.sh` 装到服务器项目 |

## 快速开始

```bash
# 1. 克隆本仓库
git clone <this-repo> ai-dev-flow-server && cd ai-dev-flow-server

# 2. 安装到目标项目
bash install.sh /path/to/your-project --tech-stack node

# 3. 按提示执行 root 段（激活 timer）
# systemctl enable --now dispatch-<project>.timer reconcile-<project>.timer

# 4. 开始走 Gate 流程
# /grill-with-docs → /to-spec → /to-tickets → /implement → AFK 自动消化
```

## 支持的 tech-stack

| 值 | 包管理 | 测试命令 | Lint 命令 |
|:---:|------|------|------|
| `node` | npm | npm test | npm run lint |
| `python` | uv | uv run pytest | uv run ruff check |
| `go` | go | go test ./... | go vet ./... |

可通过 `--pkg-mgr`、`--test-cmd`、`--lint-cmd` 覆盖默认值。

## 角色系统（`--role`）

3 级角色控制 Agent 行为边界：

| 角色 | 权限 | 产出 | 适用 |
|------|------|------|------|
| `owner` | 全权，无额外约束 | 代码+PR+部署 | 个人项目 |
| `developer` | 业务代码+PR合并，禁改管线 | 代码+PR | 团队项目 |
| `agent-b`（默认） | 仅产出issue，handoff协作 | issue | 受限环境 |

```bash
# 初始安装
bash install.sh . --role developer

# 秒切角色
devflow role switch owner
devflow role              # 查看当前角色
devflow role list         # 列出可用角色
```

切换角色时自动处理 CLAUDE.md 约束段 + _handoff/ + AGENTS.md 的创建/删除。

## 项目结构

```
ai-dev-flow-server/
├── README.md
├── install.sh / uninstall.sh
├── config.example.yaml
├── templates/        # .gate-state / CLAUDE.md.append / issue 模板 / .timer
├── workflows/        # 6 个 gate 脚本（适配服务器路径）
├── archon/           # dispatch.sh + reconciler.sh + auto-execute-afk.yaml
├── scripts/          # check_constitution.py + cost_tracker.py + notify.py
└── knowledge/        # 7 份方法论文档（宪法 + 流程 + 防护）
```

## 依赖

- Claude Code（目标项目需可用）
- git + gh CLI（AFK 管线需要）
- systemd（timer 调度）
- Python 3.12+（check_constitution / cost_tracker / notify）
- Archon（工作流引擎，AFK 执行）

## 许可

MIT — 同 ai-dev-flow 上游。
