# AFK 管线容器依赖清单

> 提交给 Docker 镜像构建者。目标：让容器能跑 Archon serve（GitHub Issues + Webhook 主流模式）。

---

## 背景

AFK 管线已从自研 dispatcher 切换到 Archon 主流模式：

```
GitHub Issue 评论 @archon → webhook → archon serve → workflow 执行 → PR + 评论
```

不再需要 dispatch.sh / reconciler.sh / cron。核心依赖只有一个：**archon serve 常驻进程**。

**当前容器已有**：git 2.47.3、python3 3.13.5、bash 5.2.37、gh CLI、claude CLI、15Gi 内存。

---

## 必须安装

### 1. Archon CLI + serve 模式（核心）

```bash
# 方式 A：官方安装脚本
curl -fsSL https://archon.diy/install | bash

# 方式 B：Homebrew（Linuxbrew）
brew install coleam00/archon/archon

# 方式 C：从 GitHub Release 下载二进制
# https://github.com/coleam00/Archon/releases
```

**验证**：
```bash
archon --version
archon workflow list
archon serve --help
```

### 2. C/C++ 编译工具链 + SQLite（cuotiben 错题本需要）

```bash
apt-get install -y build-essential libsqlite3-dev sqlite3
```

| 包 | 用途 |
|---|---|
| `build-essential` | gcc + g++ + make，编译 better-sqlite3 原生模块 |
| `libsqlite3-dev` | SQLite 开发头文件 |
| `sqlite3` | SQLite CLI 调试工具 |

### 3. Python 包

```bash
pip3 install pyyaml requests
```

### 4. 环境变量

```bash
# Claude Code 调用 LLM
ANTHROPIC_API_KEY=sk-xxx
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_AUTH_TOKEN=sk-xxx

# Archon GitHub Webhook（必填）
WEBHOOK_SECRET=<openssl rand -hex 32 生成>
GITHUB_TOKEN=<GitHub PAT 或 GitHub App 令牌>

# Archon 数据目录
ARCHON_HOME=/home/coder/.archon
```

### 5. Archon serve 自启动

容器启动时自动运行 `archon serve`：

```bash
# 方式 A：supervisor
cat > /etc/supervisor/conf.d/archon.conf << 'EOF'
[program:archon]
command=archon serve --port 8420
directory=/home/coder/project
user=coder
autostart=true
autorestart=true
environment=HOME="/home/coder",ARCHON_HOME="/home/coder/.archon"
EOF

# 方式 B：简单 tmux 后台（开发环境用）
# tmux new-session -d -s archon 'archon serve --port 8420'
```

### 6. 端口暴露

```dockerfile
EXPOSE 8420
```

Archon Web UI 在 8420，webhook 端点在 `/webhooks/github`。

---

## GitHub 侧配置（容器外操作）

容器跑起来后，配置 GitHub webhook：

```bash
# 1. 生成 webhook secret
openssl rand -hex 32

# 2. 注册 webhook（替换 OWNER/REPO 和域名）
gh api repos/OWNER/REPO/hooks --input - << EOF
{
  "config": {
    "url": "https://<your-domain>/webhooks/github",
    "content_type": "json",
    "secret": "<上一步生成的 secret>"
  },
  "events": ["issues", "issue_comment", "pull_request"],
  "active": true
}
EOF
```

Webhook Payload URL 需要公网可达（Tailscale Funnel 或 Cloudflare Tunnel 或直接暴露）。

---

## 不再需要的组件

以下自研组件已标注 DEPRECATED，无需在容器中配置：

| 组件 | 状态 | 替代 |
|------|------|------|
| dispatch.sh | DEPRECATED | Archon webhook 自动触发 |
| reconciler.sh | DEPRECATED | GitHub labels + comments 管理状态 |
| scheduler.sh | DEPRECATED | webhook 即时触发，无需轮询 |
| cron / systemd timer | DEPRECATED | 同上 |
| dispatch.timer | DEPRECATED | 同上 |
| reconciler.timer | DEPRECATED | 同上 |

---

## 建议安装（非必须）

```bash
apt-get install -y less jq tmux
```

---

## 验证脚本

```bash
#!/bin/bash
set -euo pipefail

echo "=== 基础工具 ==="
git --version
python3 --version
gh --version | head -1
claude --version 2>/dev/null || echo "claude: OK"

echo "=== Archon ==="
archon --version
archon workflow list 2>/dev/null && echo "workflows: OK"

echo "=== Python 包 ==="
python3 -c "import yaml; print('pyyaml: OK')"
python3 -c "import requests; print('requests: OK')"

echo "=== 环境变量 ==="
[ -n "${ANTHROPIC_API_KEY:-}" ] && echo "ANTHROPIC_API_KEY: ✅" || echo "ANTHROPIC_API_KEY: ❌"
[ -n "${WEBHOOK_SECRET:-}" ] && echo "WEBHOOK_SECRET: ✅" || echo "WEBHOOK_SECRET: ❌"
[ -n "${GITHUB_TOKEN:-}" ] && echo "GITHUB_TOKEN: ✅" || echo "GITHUB_TOKEN: ❌"

echo "=== archon serve 端口 ==="
curl -s http://localhost:8420/health 2>/dev/null && echo "archon serve: ✅" || echo "archon serve: ⚠️ 未运行"

echo "=== 全部检查完成 ==="
```
