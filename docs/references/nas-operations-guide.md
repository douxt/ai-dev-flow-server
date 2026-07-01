# NAS 运维手册

> @author: Claude
> @created: 2026-07-01
> @workflow: 文档整理

## 硬件与访问

| 项目 | 值 |
|------|-----|
| 型号 | Synology SA6400 (epyc7002) |
| OS | DSM (Linux 5.10.55+) |
| Hostname | `nas` |
| SSH | `ssh root@nas`（密钥免密） |
| Docker 路径 | `/var/packages/ContainerManager/target/usr/bin/docker` |

## 容器清单（2026-07-01）

```
NAMES                     STATUS                         PORTS
code-server               Up                            0.0.0.0:25252→8080, 127.0.0.1:8686→8080
maf-agent-app             Restarting (broken)           -
n8n                       Up 2 weeks                    5679→5678
langbot                   Up 5 weeks                    2280-2285, 5300
langbot-plugin            Up 6 weeks                    -
napcat                    Up 6 weeks                    6099
immich_server             Up 8 weeks (healthy)          2283
immich_postgres           Up 8 weeks (healthy)          5432
immich_machine_learning   Up 8 weeks (healthy)          -
immich_redis              Up 8 weeks (healthy)          6379
emby                      Up 8 weeks                    7568→8096
moviepilot-v2             Up 8 weeks                    -
iyuuplus                  Up 8 weeks                    -
sun-panel                 Up 8 weeks                    3002
xiaoya                    Up 8 weeks                    5678→80
```

### 容器分类

| 类别 | 容器 | 重要性 |
|------|------|--------|
| 开发环境 | code-server | 核心 |
| MAF 运行时 | maf-agent-app | 待修复 |
| 自动化 | n8n, langbot, langbot-plugin, napcat | 高 |
| 媒体 | emby, immich*, moviepilot-v2, iyuuplus, xiaoya | 中 |
| 面板 | sun-panel | 低 |

---

## 1. code-server（核心开发容器）

### 概览

在 NAS 上运行的 VSCode Server + Claude Code 环境，用于 MAF-Hub 的 AFK 开发。

### 文件位置

```
/volume7/docker/codeserver/
├── Dockerfile              # 构建文件
├── Dockerfile.bak.20260630 # 上次修改前备份
├── docker-compose.yml      # 编排文件
├── docker-compose.yml.bak  # 编排文件备份
├── certs/                  # TLS 证书
├── config/                 → 挂载到 /home/coder/.config
└── projects/               → 挂载到 /home/coder/project
```

### Dockerfile 关键内容

```dockerfile
FROM codercom/code-server:latest
USER root
# 安装依赖：nodejs, npm, tmux, git, gh, jq, curl, python3-pip, python3-venv
# 安装 Claude Code：npm install -g @anthropic-ai/claude-code
# 安装 uv：pip3 install uv
# .claude → symlink 到 .config/claude（持久化）
USER coder
```

### docker-compose.yml

```yaml
services:
  code-server:
    build: .
    container_name: code-server
    environment:
      - TZ=Asia/Shanghai
      - PASSWORD=cc9d5d9b82a7fc
    volumes:
      - /volume7/docker/codeserver/config:/home/coder/.config
      - /volume7/docker/codeserver/projects:/home/coder/project
    ports:
      - '127.0.0.1:8686:8080'   # Tailscale 隧道用
      - '0.0.0.0:25252:8080'    # 局域网直连
    restart: unless-stopped
```

### 访问方式

| 方式 | 地址 | 密码 |
|------|------|------|
| 局域网直连 | `http://nas:25252` | `cc9d5d9b82a7fc` |
| Tailscale 隧道 | `http://<tailscale-ip>:8686` | 同上 |

### 容器内操作

```bash
# 进入容器（root）
ssh root@nas
docker exec -it code-server bash

# 以 coder 用户执行命令
docker exec -u coder code-server <command>

# 示例：检查 Claude Code 版本
docker exec code-server claude --version

# 示例：检查 devflow 角色
docker exec code-server /home/coder/.local/bin/devflow role
```

### 项目目录

| 路径 | 内容 |
|------|------|
| `/home/coder/project/MAF-Hub/` | 主项目仓库（gitee） |
| `/tmp/ai-dev-flow-server/` | AI Dev Flow 服务器版脚本 |
| `/home/coder/.claude/` | Claude Code 配置（→ symlink .config） |

### MAF-Hub 配置

```yaml
# /home/coder/project/MAF-Hub/.devflow/config.yaml
project:
  name: MAF-Hub
  repo_url: git@gitee.com:cybxcoder/maf-hub.git
  workspace: /home/coder/project/MAF-Hub
mode: frontend
role: developer
tech_stack:
  language: python
  package_manager: uv
```

- **role: developer** = 只写业务代码，不碰管线/部署文件
- Gate 全部 `pending`，未启动 AFK 循环

### 重启/重建

```bash
# 重启容器
ssh root@nas 'docker restart code-server'

# 重建镜像（Dockerfile 有改动时）
ssh root@nas 'cd /volume7/docker/codeserver && docker compose up -d --build'

# 查看日志
ssh root@nas 'docker logs --tail 50 code-server'
```

### 修改 Dockerfile 流程

1. 备份：`cp Dockerfile Dockerfile.bak.$(date +%Y%m%d)`
2. 编辑 Dockerfile
3. 重建：`docker compose up -d --build`
4. 验证：`docker exec code-server <检查命令>`
5. 如失败：从 `.bak` 恢复，重复 3-4

---

## 2. maf-agent-app（MAF 运行时，已挂）

### 状态：**Restarting（2026-05-04 起）**

### 文件位置

```
/volume1/docker/maf-app/
├── agent.py              # 测试 agent（写俳句）
├── Dockerfile
├── requirements.txt
├── .env                  # 密钥配置
└── docker-compose.yml
```

### docker-compose.yml

```yaml
services:
  agent:
    build: .
    image: my-maf-agent:latest
    container_name: maf-agent-app
    restart: unless-stopped
    env_file:
      - .env
```

### 崩溃原因（推测）

`.env` 中的 API key 可能已过期，或 `agent_framework` 依赖有兼容问题。需要进入容器排查：

```bash
ssh root@nas 'docker logs --tail 50 maf-agent-app'
```

### 修复方向

1. 检查 `.env` 中的 `OPENAI_API_KEY` 是否有效
2. 升级 `agent_framework` 到最新版
3. 如不再使用，直接停掉：`docker stop maf-agent-app`

---

## 3. 日常运维命令速查

### 容器管理

```bash
# 查看所有容器状态
ssh root@nas 'docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'

# 启动/停止/重启
ssh root@nas 'docker start <name>'
ssh root@nas 'docker stop <name>'
ssh root@nas 'docker restart <name>'

# 查看日志
ssh root@nas 'docker logs --tail 100 <name>'

# 进容器 shell
ssh root@nas 'docker exec -it <name> bash'
```

### DSM 层面

```bash
# NAS 重启后容器自动启动（unless-stopped 策略）
# 注意：maf-agent-app 即使自动启动也会继续 crash loop

# 检查 NAS 磁盘
ssh root@nas 'df -h'

# 检查 Docker 占用
ssh root@nas 'docker system df'
```

### code-server 内 Claude Code 操作

```bash
# 查看 gate 状态
docker exec code-server cat /home/coder/project/MAF-Hub/.gate-state

# 手动触发 gate 流程（在容器内交互式运行）
docker exec -it code-server bash
cd ~/project/MAF-Hub
claude

# 更新 ai-dev-flow-server
docker exec code-server bash -c '
  cd /tmp/ai-dev-flow-server && git pull --rebase origin master &&
  cd ~/project/MAF-Hub &&
  bash /tmp/ai-dev-flow-server/install.sh . --update --role developer'
```

---

## 4. 状态切换场景

### 场景 A：启动 AFK 自动消化

当前所有 Gate 都是 `pending`，要启动 AFK 循环需要：

1. 人用 VSCode 打开 `http://nas:25252`
2. 依次执行 Gate 1-6：
   - `/gate-1-grill` → 需求对齐
   - `/gate-2-prd` → 产出 PRD
   - `/gate-3-issues` → 拆 Issue
   - `/gate-4-review` → Issue 评审
   - `/gate-5-prep` → 环境检查
   - `/gate-6-afk` → 管线就绪
3. 将 issue 拖到 `ready` 状态
4. dispatch.timer 自动抢 issue → Archon 工作流 → 提 PR
5. PR 创建后 Telegram 通知审批

### 场景 B：停止 AFK 循环

```bash
# 方法1：停掉 dispatch timer（在容器内）
docker exec code-server bash -c 'crontab -l | grep -v dispatch | crontab -'

# 方法2：把所有 issue 改回 backlog
```

### 场景 C：更新 code-server 环境

当需要升级 Claude Code、uv 或添加系统依赖时：

```bash
# 1. 备份
ssh root@nas 'cp /volume7/docker/codeserver/Dockerfile /volume7/docker/codeserver/Dockerfile.bak.$(date +%Y%m%d)'

# 2. 编辑 Dockerfile（修改 RUN 指令）

# 3. 重建
ssh root@nas 'cd /volume7/docker/codeserver && docker compose up -d --build'

# 4. 验证
ssh root@nas 'docker exec code-server claude --version'
ssh root@nas 'docker exec code-server uv --version'
```

### 场景 D：更新 MAF-Hub 项目

```bash
# 在容器内 pull 最新代码
ssh root@nas 'docker exec code-server bash -c "cd ~/project/MAF-Hub && git pull --rebase origin master"'

# 同步依赖
ssh root@nas 'docker exec code-server bash -c "cd ~/project/MAF-Hub && uv sync"'
```

### 场景 E：完全重建 code-server

```bash
# 1. 停容器
ssh root@nas 'cd /volume7/docker/codeserver && docker compose down'

# 2. 重建（保留 volumes 数据）
ssh root@nas 'cd /volume7/docker/codeserver && docker compose up -d --build'

# 3. 检查持久化数据是否完整
ssh root@nas 'docker exec code-server ls /home/coder/.config/claude/'
ssh root@nas 'docker exec code-server ls /home/coder/project/'
```

---

## 5. 备份策略

### 当前备份

| 文件 | 备份位置 |
|------|---------|
| Dockerfile | `Dockerfile.bak.20260630` |
| docker-compose.yml | `docker-compose.yml.bak` |

### 建议定期备份

```bash
# Dockerfile 每次修改前备份
cp Dockerfile Dockerfile.bak.$(date +%Y%m%d)

# Claude Code 配置（自动持久化到 volume）
# /volume7/docker/codeserver/config/ 是 Docker volume，已持久化

# Git 仓库
# /volume7/docker/codeserver/projects/ 中的未提交改动需手动 push
```

---

## 6. 已知问题

| 问题 | 状态 | 影响 |
|------|------|------|
| maf-agent-app 重启循环 | 待修复（2026-05-04 起） | MAF 运行时不可用 |
| code-server 无 gh 登录 | 已确认 | 无法操作 GitHub PR |
| Gate 全部 pending | 设计如此 | AFK 循环未启动 |

---

## 7. 操作红线

- **禁止**在生产容器内直接改文件（走 Dockerfile 重建）
- **禁止**`docker rm` 删除容器（permission deny 已配置）
- **禁止**在 code-server 内直推 master（走 PR）
- **注意**：code-server 的 `.claude/` 是 symlink 到 `.config/claude/`，备份时注意别跟丢
- **注意**：容器内 git 未配置 user.name/email（需要在容器内设置或通过环境变量注入）
