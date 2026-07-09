# 基础设施一览

> @updated: 2026-07-01

## NAS（本地）

| 项目 | 值 |
|------|-----|
| 型号 | Synology SA6400 |
| CPU | Intel N100，4 核 |
| 内存 | 15GB |
| 系统 | DSM（Linux 5.10.55+） |
| 运行时长 | 368 天 |
| SSH | `ssh root@nas`（密钥免密） |
| 局域网 IP | 192.168.31.7 |
| Docker 路径 | `/var/packages/ContainerManager/target/usr/bin/docker` |

### 磁盘

| 卷 | 容量 | 使用率 |
|----|------|--------|
| volume1（Docker 层） | 209G | 24% |
| volume2 | 3.6T | 60% |
| volume3 | 1.8T | 46% |
| volume4 | 447G | 48% |
| volume5 | 282G | 8% |
| volume6 | 13T | 68% |
| volume7（code-server） | 928G | 1% |

### 关键容器

| 容器 | 端口 | 说明 |
|------|------|------|
| code-server | 25252 (LAN), 8686 (Tailscale) | VSCode + Claude Code，密码 `cc9d5d9b82a7fc` |
| n8n | 5679 | 自动化工作流 |
| immich 全家桶 | 2283 | 照片管理 |
| emby | 7568 | 媒体服务器 |
| maf-agent-app | - | 已挂，2026-05-04 起 crash loop |

### code-server 关键路径

| 路径 | 内容 |
|------|------|
| `/home/coder/project/MAF-Hub/` | 主项目仓库（gitee） |
| `/home/coder/.config/claude/` | Claude Code 持久化配置 |

---

## 轻量云服务器（阿里云）

| 项目 | 值 |
|------|-----|
| 配置 | 2C 3.4GB（Intel Xeon Platinum），49G 磁盘 |
| 系统 | Ubuntu 5.15，运行 47 天 |
| SSH | `ssh root@115.29.110.107`（密钥免密） |
| Tailscale IP | 100.112.178.76 |

### 服务状态（2026-07-01）

| 服务 | 端口 | 状态 | 说明 |
|------|------|------|------|
| OpenLobby | :3001 | ✅ running | 多会话 CC 聊天（systemd） |
| 审批看板 | :8421 | ✅ running | Python/FastAPI，源码 `/opt/maf-hub/docs/business/devflow/approval_board.py` |
| Telegram Bot | - | ✅ running | 审批回调轮询（systemd） |
| Archon | :8420 | ❌ inactive | 未启动（disabled） |
| mini-router（cc-stack） | :3457 | ❌ inactive | 未启动（disabled） |

### 管线 timer

| timer | 周期 | 状态 |
|-------|------|------|
| dispatch-openlobby | 每 1 分钟 | ✅ 活跃 |
| dispatch-cuotiben | 每 5 分钟 | ✅ 活跃 |
| dispatch（maf-hub） | 每 5 分钟 | ✅ 活跃 |
| reconcile-openlobby | 每 1 分钟 | ✅ 活跃 |
| reconcile-cuotiben | 每 5 分钟 | ✅ 活跃 |
| reconciler（maf-hub） | 每 5 分钟 | ✅ 活跃 |

### Docker 容器

| 容器 | 状态 | 端口 |
|------|------|------|
| mes-agent | Up 9 days | :8000 |
| win-vl-agent | Up 5 weeks | :8001 |
| derp-ip | Up 36 hours | - |
| competent_bassi | 6 周前已退出 | - |

### 关键路径

| 路径 | 内容 |
|------|------|
| `/opt/maf-hub/` | 主项目仓库 |
| `/opt/ai-dev-flow-server/` | 本管线框架 |
| `/opt/maf-hub/issues/phase2-compiler/` | 试点项目（8 个 issue） |

> Archon 和 mini-router 当前 inactive 为预期状态（试运行阶段，按需启动）。
