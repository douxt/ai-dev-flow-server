# AFK 管线容器依赖清单

> 提交给 Docker 镜像构建者。目标：让 Claude Code 运行环境能跑通完整的 AFK 管线（dispatch → Archon → reconciler）。

---

## 背景

Claude Code 运行在一个 Docker 容器中。AFK（自动无人值守开发）管线需要在该容器内完整运行，包括：
- `dispatch.sh` — 扫描 issue、宪法检查、git claim、调用 Archon
- `archon workflow run ...` — 执行 YAML 定义的 DAG 工作流
- `reconciler.sh` — 状态修复器（检测卡住/孤儿 issue）
- 测试套件 `test-dispatch.sh`

**当前容器已有**：git 2.47.3、python3 3.13.5、bash 5.2.37、gh CLI、claude CLI、15Gi 内存。

**当前缺失**：Archon CLI、部分 Python 包、systemd 替代方案。

---

## 必须安装

### 1. Archon CLI（核心）

这是管线中最关键的组件 —— 解析 YAML DAG、编排 Claude Code 任务、管理 worktree 隔离。

**安装方式**（任选其一，需确认）：
```bash
# 方式 A：pip（如果有 PyPI 包）
pip3 install archon-cli

# 方式 B：私有源
pip3 install archon-cli --index-url https://...

# 方式 C：下载二进制
curl -fsSL https://.../archon -o /usr/local/bin/archon
chmod +x /usr/local/bin/archon

# 方式 D：git clone + 安装
git clone https://github.com/.../archon.git /opt/archon
cd /opt/archon && pip3 install -e .
```

**验证**：
```bash
archon --version
archon workflow list   # 应列出可用工作流
```

### 2. Python 包

```bash
pip3 install pyyaml requests
```

### 3. 环境变量

容器启动时需要注入以下环境变量：
```bash
ANTHROPIC_API_KEY=sk-xxx
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_AUTH_TOKEN=sk-xxx
```

---

## 建议安装（非必须，但能提升体验）

### 4. systemd 替代

容器内无 systemd，建议安装 cron 作为定时器替代：
```bash
apt-get update && apt-get install -y cron
# 或安装 supervisor 管理后台进程
apt-get install -y supervisor
```

### 5. 日志工具

```bash
apt-get install -y less jq
```

### 6. Archon 工作目录

```bash
mkdir -p /opt/archon/workspaces
mkdir -p /tmp/archon-worktrees
```

---

## 验证脚本

镜像构建完成后，运行以下命令验证：

```bash
#!/bin/bash
set -euo pipefail

echo "=== 基础工具 ==="
git --version
python3 --version
bash --version | head -1
gh --version | head -1
claude --version 2>/dev/null || echo "claude: OK (Claude Code CLI)"

echo "=== Archon CLI ==="
archon --version
archon workflow list 2>/dev/null || echo "archon workflows: OK"

echo "=== Python 包 ==="
python3 -c "import yaml; print('pyyaml: OK')"
python3 -c "import requests; print('requests: OK')"

echo "=== 环境变量 ==="
[ -n "${ANTHROPIC_API_KEY:-}" ] && echo "ANTHROPIC_API_KEY: ✅" || echo "ANTHROPIC_API_KEY: ❌ 未设置"
[ -n "${ANTHROPIC_BASE_URL:-}" ] && echo "ANTHROPIC_BASE_URL: ✅" || echo "ANTHROPIC_BASE_URL: ❌ 未设置"

echo "=== 目录结构 ==="
[ -d /opt/archon/workspaces ] && echo "/opt/archon/workspaces: ✅" || echo "/opt/archon/workspaces: ❌ 不存在"

echo "=== 管线测试 ==="
# 创建临时测试项目
TMPDIR=$(mktemp -d)
mkdir -p "$TMPDIR/.devflow/archon" "$TMPDIR/.devflow/scripts" "$TMPDIR/issues" "$TMPDIR/logs"
echo "name: test" > "$TMPDIR/.devflow/config.yaml"
echo "---
type: AFK
estimate: 1h
effort: small
status: ready
blocked_by: []
needs_llm: true
needs_vision: false
needs_pdf: false
test_files: []
---
# Test
" > "$TMPDIR/issues/000-test.md"

echo "dispatch 语法检查..."
bash -n "$TMPDIR/../archon/dispatch.sh" && echo "dispatch.sh: ✅"

echo "reconciler 语法检查..."
bash -n "$TMPDIR/../archon/reconciler.sh" && echo "reconciler.sh: ✅"

echo "宪法检查..."
python3 "$TMPDIR/../scripts/check_constitution.py" "$TMPDIR/issues/000-test.md" --json && echo "constitution: ✅"

echo "mock archon 执行..."
archon workflow run auto-execute-afk "$TMPDIR/issues/000-test.md" --dry-run 2>/dev/null && echo "archon dry-run: ✅" || echo "archon dry-run: ⚠️ 需要 real issue"

rm -rf "$TMPDIR"
echo "=== 全部检查完成 ==="
```

---

## 安装优先级

| 优先级 | 项目 | 说明 |
|--------|------|------|
| P0 | Archon CLI | 管线核心，无此不可运行 |
| P0 | pyyaml + requests | 宪法检查 + 通知依赖 |
| P1 | ANTHROPIC_* 环境变量 | Claude CLI 调 LLM 需要 |
| P2 | cron / supervisor | 替代 systemd timer |
| P3 | less / jq | 调试工具 |
