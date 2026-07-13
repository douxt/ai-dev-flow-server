# 容器重启与连接最佳实践

> 2026-07-10 初稿 | 2026-07-13 更新：init:true + healthcheck + timeout 规范

---

## 〇、容器配置（compose 关键字段）

```yaml
services:
  langbot:
    init: true           # tini 回收僵尸子进程（必加！）
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "grep -q '00000000:08E8' /proc/net/tcp || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

  langbot-plugin:
    init: true           # tini 回收僵尸子进程（必加！）
    restart: unless-stopped
```

- `init: true` 是治愈僵尸进程的根本方案——Docker 注入 `tini` 作为 PID 1，自动回收 `docker exec`/`docker logs` 断开后残留的子进程
- `restart: unless-stopped` 确保宿主重启后容器自动启动，但尊重手动 `docker stop`
- healthcheck 检测 langbot 的 2280 端口是否在监听，配合 cron 巡检自动重启 unhealthy 容器

---

## 一、容器重启顺序

```
1. langbot-plugin 先重启
2. langbot 主进程后重启
3. napcat 最后重启
```

**原因：**
- napcat 连 langbot 的 WebSocket（ws://langbot:2280/ws）
- 如果 langbot 先重启，napcat 已建立的连接会断，且 napcat 需要重新连
- langbot 后重启时 napcat 连接瞬间断开，重连可能超时（ECONNREFUSED）
- **正确顺序**：先 langbot+plugin，等 langbot 完全启动后，再重启 napcat

**完整命令（所有 docker 命令必须加 timeout）：**
```bash
DOCKER=/volume1/@appstore/ContainerManager/usr/bin/docker
# 先重启 langbot+plugin
ssh root@nas "timeout 20 $DOCKER restart langbot-plugin langbot"
sleep 8
# 确认 langbot 端口就绪
ssh root@nas "timeout 5 $DOCKER exec langbot sh -c 'grep 08E8 /proc/net/tcp | head -1'"
# 等 healthcheck 通过
sleep 30
# 再重启 napcat
ssh root@nas "timeout 10 $DOCKER restart napcat"
# 验证无 ECONNREFUSED
sleep 5
ssh root@nas "timeout 5 $DOCKER logs napcat 2>&1 | grep -i refused || echo 'no errors'"
```

---

## 二、SSH 连接最佳实践

### 问题：SSH 僵尸会话堆积

连续 `docker exec`/`docker logs` 调用会在 NAS 上堆积僵死子进程，后续 docker exec 全部 hang。管道跨 SSH 边界是最大元凶。

### 硬性规则（所有远程命令必须遵守）

| 规则 | 做法 |
|------|------|
| **必须加 timeout** | 每条 `docker exec/logs/restart` 前加 `timeout N` |
| **管道不跨 SSH** | 管道放 `sh -c "..."` 内，不放在 SSH 和 docker 之间 |
| **docker logs 同样危险** | `docker logs` 和 `docker exec` 一样产生子进程，SSH 断开后变僵尸 |

**正确模式：**
```bash
# ✅ 管道在 sh -c 内部
ssh root@nas 'timeout 5 docker exec langbot sh -c "cmd1 | cmd2"'

# ✅ docker logs 加 timeout
ssh root@nas 'timeout 5 docker logs --tail 10 langbot'

# ❌ 禁止：管道跨 SSH 边界（SSH 断开 → docker logs 僵尸）
ssh root@nas 'docker logs langbot | tail -5'

# ❌ 禁止：无 timeout
ssh root@nas 'docker exec langbot ...'
```

**1. 使用连接保持参数：**
```bash
ssh -nT -o ConnectTimeout=6 -o BatchMode=yes root@nas 'command'
```
- `-nT`：不分配 TTY，非交互模式
- `ConnectTimeout=6`：6 秒连接超时（快速失败）
- `BatchMode=yes`：禁用密码认证，避免卡在密码提示

**2. 远程写脚本文件再执行（避免引号转义问题）：**
```bash
cat << 'PYEOF' > /tmp/script.py
...python code...
PYEOF
scp /tmp/script.py root@nas:/tmp/
ssh root@nas 'timeout 10 docker cp /tmp/script.py langbot:/tmp/ && timeout 10 docker exec langbot /app/.venv/bin/python3 /tmp/script.py'
```

**3. Docker 守护进程卡死时的恢复：**
```bash
# 普通 docker exec/restart/kill 全部超时 → 重启 Container Manager 服务
/usr/syno/bin/synopkg restart ContainerManager
```

---

## 三、部署后验证清单

```bash
# 1. 插件初始化
ssh root@nas "timeout 5 $DOCKER exec langbot-plugin cat /tmp/silent_init.log"
# 预期：kb_enabled=True vision_enabled=True

# 2. langbot healthcheck
ssh root@nas "timeout 5 $DOCKER inspect langbot --format '{{.State.Health.Status}}'"
# 预期：healthy

# 3. napcat WebSocket 连接
ssh root@nas "timeout 5 $DOCKER logs napcat 2>&1 | grep -i refused || echo 'no errors'"
# 预期：no errors

# 4. gate 日志（插件收到消息）
ssh root@nas "timeout 5 $DOCKER exec langbot-plugin sh -c 'tail -5 /tmp/silent_gate.log'"
# 预期：看到 [silent] inject START
```

---

## 四、Docker 位置

Synology Docker 二进制不在标准 PATH 中。实际路径：

```bash
DOCKER=/volume1/@appstore/ContainerManager/usr/bin/docker
# 或设置别名
alias docker=/volume1/@appstore/ContainerManager/usr/bin/docker
```

DSM 终端以 `douxt` 用户登录时需加 `sudo`。重启后 Container Manager 可能变成灰色图标 → 点「修复」即可恢复，**不会丢失容器数据**（数据在 `/volume1/@docker/`）。

---

## 五、诊断命令速查

所有命令用 `$DOCKER` 代替 `docker`：

```bash
DOCKER=/volume1/@appstore/ContainerManager/usr/bin/docker
```

| 目的 | 命令 |
|------|------|
| 查看容器状态 | `ssh root@nas "timeout 5 $DOCKER ps --format '{{.Names}} {{.Status}}'"` |
| 查看 langbot 健康 | `ssh root@nas "timeout 5 $DOCKER inspect langbot --format '{{.State.Health.Status}}'"` |
| 查看 napcat 连接状态 | `ssh root@nas "timeout 5 $DOCKER logs napcat 2>&1 \| grep -i refused"` |
| 查看 langbot 端口 | `ssh root@nas "timeout 5 $DOCKER exec langbot sh -c 'grep 08E8 /proc/net/tcp \| head -1'"` |
| 查看插件是否收到消息 | `ssh root@nas "timeout 5 $DOCKER exec langbot-plugin sh -c 'tail -10 /tmp/silent_gate.log'"` |
| 查看监控消息 | `ssh root@nas "timeout 5 $DOCKER exec langbot /app/.venv/bin/python3 -c \"...\""` |
| 查看僵尸进程 | `ssh root@nas "ps aux \| grep -c 'docker (logs\|exec)'"` |

---

## 六、Tailscale + WSL2 双端冲突（重要）

### 问题

Tailscale **同时在 Windows 和 WSL2 中运行时**，SSH 到 NAS 极不稳定（时通时不通，KEX 握手超时）。

**官文明确说明：**
> *"If you run Tailscale on both the Windows host and inside WSL 2 at the same time, Tailscale encrypted traffic that flows from WSL 2 over Tailscale on the Windows host will not work due to Tailscale packets not being able to fit in Tailscale packets."*

**根因：** WSL 和 Windows 各跑一个 Tailscale，流量包被双重隧道加密，MTU 叠加后 SSH KEX 包被丢弃。

### 解决方案

**方案 1：WSL 关掉 Tailscale（推荐）**

```bash
# WSL 里
sudo tailscale down
# SSH 到 NAS 立刻变快变稳
ssh root@nas echo ok
```

WSL 流量会通过 Windows 宿主网卡自然走 Windows 的 Tailscale 隧道。

**方案 2：保留双端，SSH 加参数缓解**

```bash
ssh -o IPQoS=throughput root@nas
```

仅缓解，不根治。

**方案 3：Windows 关掉 Tailscale，只用 WSL 的**

如果 WSL 是主要工作环境。

### 诊断方法

```bash
# 查看两端 Tailscale 状态
tailscale status          # WSL
tailscale.exe status      # Windows
```## 六、僵死防护（重要）

### 问题：docker exec/logs 卡住堆积僵尸，最终 Docker 守护进程耗尽

每次 `docker exec`/`docker logs` 在 NAS 上创建一个子进程。如果 SSH 断开或超时，子进程永久挂起。2026-07-13 事故中 **15 个 `docker logs langbot` 僵尸**从 7/12 挂到 7/13，最终 Docker 守护进程拒绝所有 `exec`/`restart`/`kill` 操作。

### 三层防御

| 层 | 措施 | 效果 |
|----|------|------|
| **治本** | compose 加 `init: true` | tini 自动回收僵尸子进程 |
| **防复发** | 所有命令加 `timeout` + 管道不跨 SSH | 单条命令不会永久挂起 |
| **兜底** | cron 巡检 + healthcheck 自愈 | 残留僵尸自动清理，unhealthy 自动重启 |

### 预防规则

| 规则 | 做法 |
|------|------|
| **不加超时不 exec** | `timeout 10 docker exec ...` — 超时自动杀 |
| **管道不跨 SSH** | 管道放 `sh -c "..."` 内，不放在 SSH 和 docker 之间 |
| **docker logs 同样危险** | `docker logs` 和 `docker exec` 一样产生子进程 |
| **合并不连击** | 多条命令用 `sh -c "cmd1; cmd2"` 一次跑完 |
| **卡住立刻停手** | 不再 SSH 重复打 — 只会堆积更多僵尸 |

### NAS 定时巡检（已部署）

`/etc/crontab` 每 30 分钟运行 `/volume1/docker/langbot/health-check.sh`：

- 重启 unhealthy 容器
- 杀超过 10 分钟的 `docker exec/logs` 残留进程
- 僵尸数 > 10 写告警日志到 `/tmp/docker-health.log`

### Docker 守护进程卡死时的紧急恢复

```bash
# docker exec/restart/kill 全部超时 → 重启 Container Manager
/usr/syno/bin/synopkg restart ContainerManager
```

---

## 七、已知陷阱

| 陷阱 | 现象 | 解决 |
|------|------|------|
| napcat WS 超时 | `ECONNREFUSED 192.168.176.4:2280` | 等 langbot healthcheck healthy 后再重启 napcat |
| `docker logs` 僵尸 | docker exec/logs/restart 全部 hang | `init: true` + timeout + 管道不跨 SSH |
| 僵尸 exec 会话 | docker exec 全部 hang | 合并成单次 exec，避免连击 |
| `__pycache__` 缓存 | 旧代码继续跑 | 部署前 `find -name __pycache__ -exec rm -rf {}` |
| SSH 中间层截断 | 输出被替换/摘要 | 远端命令 base64 编码输出，本地解码 |
| 引号转义地狱 | shell 语法错误 | 写 Python 脚本 scp 过去执行 |
| LongTermMemory 突然消失 | 随机 `Plugin not found` | transient error，重启 langbot 可恢复 |
| Docker 守护进程卡死 | `docker restart/kill` 超时 | `synopkg restart ContainerManager` |

---

## 八、LongTermMemory 插件 "not found" 错误

### 根因

LangBot 插件运行时通过独立 WebSocket 连接注册插件。WS 断连 → `disconnect_callback` 触发 → `remove_plugin_container` 从 `self.plugins` 删除插件 → LangBot 调用 `retrieve_knowledge` → `find_plugin` 返回 None → `ValueError: Plugin not found`。

累计 28 次（截至 2026-07-13）。插件重新注册后自动恢复，属于瞬态错误，不影响 bot 基本回复（仅丢失长期记忆上下文）。

### 三个解决层次

#### A. 框架层修复（当前不可行）

改 LangBot `mgr.py`：
- `disconnect_callback` 加身份校验：旧 WS 的 close 事件不应删除新 WS 注册的插件（[参考](https://github.com/purplefish-ai/factory-factory/commit/641d4a2d5416d4786384e55d835c7b26bcb9b64a)）
- `find_plugin` 加重试/等待重新注册逻辑，而非直接返回 None

> 后续如 fork/改写 LangBot 插件运行时，优先改此处。

#### B. 运维层自动恢复（已实施）

NAS cron 每 30 分钟检测：最近 5 分钟出现 LTM 错误 → 自动重启 `langbot-plugin` + `langbot` + `napcat`。

脚本：`/volume1/docker/langbot/health-check.sh`

#### C. 架构层降级（长远方向）

- Pipeline 侧：`retrieve_knowledge` 失败 → 跳过 LTM，仅用近期消息生成回复（当前已这样降级）
- 插件侧自愈：silent-observer 可加 LTM 健康探针，检测到不可用时主动通知 langbot 重新加载
- 替换方案：自研记忆系统替代 LTM 插件，消除跨插件 WS 依赖

> 评估优先级：短期 B 已足够；长期可考虑 fork LangBot plugin runtime 修 A，或自研记忆系统走 C。
