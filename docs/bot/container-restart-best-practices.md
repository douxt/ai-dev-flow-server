# 容器重启与连接最佳实践

> 2026-07-10 | 从多次 restart / SSH 故障中总结

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

**完整命令：**
```bash
# 先重启 langbot
ssh root@nas '/usr/local/bin/docker restart langbot-plugin langbot'
sleep 5
# 确认 langbot 端口就绪
ssh root@nas '/usr/local/bin/docker exec langbot sh -c "cat /proc/net/tcp | grep 08E8"'
# 再重启 napcat
ssh root@nas '/usr/local/bin/docker restart napcat'
sleep 10
# 确认连接成功
ssh root@nas '/usr/local/bin/docker logs napcat 2>&1 | tail -10'
```

---

## 二、SSH 连接最佳实践

### 问题：SSH 僵尸会话堆积

连续 `docker exec` 调用会在 NAS 上堆积僵死的 exec 会话，后续 docker exec 全部 hang。

### 解决方案

**1. 使用连接保持参数：**
```bash
ssh -nT -o ConnectTimeout=10 -o ServerAliveInterval=30 -o ServerAliveCountMax=3 root@nas 'command'
```
- `-nT`：不分配 TTY，非交互模式
- `ConnectTimeout=10`：10 秒连接超时
- `ServerAliveInterval=30`：每 30 秒发 keepalive
- `ServerAliveCountMax=3`：3 次无响应即断开

**2. 清理临时 SSH 连接（使用后清理）：**
```bash
ssh -O exit root@nas 2>/dev/null
```

**3. 避免嵌套 SSH 命令：**
```bash
# ❌ 错误：SSH 里套 SSH
ssh root@nas 'docker exec ... && ssh ...'

# ✅ 正确：单次 SSH，单次 exec 跑完多条命令
ssh root@nas '/usr/local/bin/docker exec langbot-plugin sh -c "cmd1; cmd2; cmd3"'
```

**4. 远程写脚本文件再执行（避免引号转义问题）：**
```bash
cat << 'PYEOF' > /tmp/script.py
...python code...
PYEOF
scp /tmp/script.py root@nas:/tmp/
ssh root@nas '/usr/local/bin/docker cp /tmp/script.py langbot:/tmp/ && /usr/local/bin/docker exec langbot /app/.venv/bin/python3 /tmp/script.py'
```

---

## 三、部署后验证清单

```bash
# 1. 插件初始化
ssh root@nas '/usr/local/bin/docker exec langbot-plugin cat /tmp/silent_init.log'
# 预期：kb_enabled=True vision_enabled=True

# 2. napcat WebSocket 连接
ssh root@nas '/usr/local/bin/docker logs napcat 2>&1 | tail -5'
# 预期：无 ECONNREFUSED，看到"已启动"

# 3. gate 日志（插件收到消息）
ssh root@nas '/usr/local/bin/docker exec langbot-plugin sh -c "tail -5 /tmp/silent_gate.log"'
# 预期：看到 [silent] inject START

# 4. langbot 主进程无异常
ssh root@nas '/usr/local/bin/docker logs langbot 2>&1 | grep -i "error" | tail -5'
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
| 查看 napcat 连接状态 | `sudo $DOCKER logs napcat 2>&1 \| grep -i websocket \| tail -5` |
| 查看 langbot 端口 | `sudo $DOCKER exec langbot sh -c "grep 08E8 /proc/net/tcp"` |
| 查看插件是否收到消息 | `sudo $DOCKER exec langbot-plugin sh -c "tail -10 /tmp/silent_gate.log"` |
| 查看监控消息 | `sudo $DOCKER exec langbot /app/.venv/bin/python3 -c "import sqlite3;..."` |
| 启用插件检查 | `sudo $DOCKER exec langbot /app/.venv/bin/python3 -c "import sqlite3; db=sqlite3.connect('/app/data/langbot.db'); cur=db.execute('SELECT plugin_author,plugin_name,enabled FROM plugin_settings WHERE enabled=1'); [print(f'{r[0]}/{r[1]}={r[2]}') for r in cur.fetchall()]"` |
| 清日志重试 | `sudo $DOCKER exec langbot-plugin sh -c "echo '' > /tmp/silent_gate.log"` |

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
```" 僵死防护（重要）

### 问题：docker exec 卡住堆积僵尸，最终 sshd 连接池耗尽

每次 `docker exec` 在 NAS 上开一个新会话，如果容器卡死，会话永久挂起。堆积到 sshd `MaxSessions` 上限后，NAS **拒绝所有新 SSH 连接**，只能物理重启。

### 预防规则

| 规则 | 做法 |
|------|------|
| **不加超时不 exec** | `timeout 10 docker exec ...` — 超时自动杀，不留僵尸 |
| **合并不连击** | 多条命令用 `sh -c "cmd1; cmd2"` 一次跑完 |
| **卡住立刻停手** | 发现卡住 → 去 DSM 网页操作，不 SSH 重复打 |
| **优先碰 napcat** | WS 断连先试 `docker restart napcat`，轻量不卡 |

### DSM 紧急清理脚本

放到 DSM → 控制面板 → 任务计划 → 新建 → 用户自定义脚本：

```bash
#!/bin/sh
# 清理僵死 docker exec 会话（后台执行，不阻塞）
for cid in $(/usr/local/bin/docker ps -q); do
  timeout 3 /usr/local/bin/docker exec -d "$cid" true 2>/dev/null
done
# 重启 sshd
killall -9 sshd 2>/dev/null
sleep 1
/usr/syno/etc.defaults/rc.d/S95sshd.sh start
echo "SSH restored"
```

以后 SSH 卡死 → DSM 跑这个脚本 → 恢复，不用重启 NAS。

---

## 六、已知陷阱

| 陷阱 | 现象 | 解决 |
|------|------|------|
| napcat WS 超时 | `ECONNREFUSED 192.168.176.4:2280` | 等 langbot 完全启动后再重启 napcat |
| 僵尸 exec 会话 | docker exec 全部 hang | 合并成单次 exec，避免连击 |
| `__pycache__` 缓存 | 旧代码继续跑 | 部署前 `find -name __pycache__ -exec rm -rf {}` |
| SSH 中间层截断 | 输出被替换/摘要 | 远端命令 base64 编码输出，本地解码 |
| 引号转义地狱 | shell 语法错误 | 写 Python 脚本 scp 过去执行 |
| LongTermMemory 突然消失 | 随机 `Plugin not found` | transient error，重启 langbot 可恢复 |
