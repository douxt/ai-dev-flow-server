# NAS 访问与运维最佳实践

> 2026-07-10 初稿 | 2026-07-11 新增 Tailscale 性能诊断

---

## 一、环境概览

### SSH 入口
```bash
ssh root@nas
```

### Docker 容器（三个）
| 容器 | 作用 | 关键路径 |
|------|------|---------|
| `langbot` | LangBot 主进程 | DB: `/app/data/langbot.db`, ChromaDB: `/app/data/chroma/` |
| `langbot-plugin` | 插件运行时 | 插件代码: `/app/data/plugins/dou__langbot-silent-observer/` |
| `napcat` | QQ 协议 | 配置: `/app/napcat/config/onebot11_3228649756.json` |

### 核心代码地图（本地 ↔ NAS）

| 用途 | 本地路径（项目仓库） | NAS/容器路径 |
|------|---------------------|-------------|
| **插件主文件** | `docker/langbot/plugins/silent-observer/components/event_listener/default.py` | 容器 `langbot-plugin:/app/data/plugins/dou__langbot-silent-observer/components/event_listener/default.py` |
| | | NAS 卷: `/volume1/docker/langbot/data/plugins/dou__langbot-silent-observer/components/event_listener/default.py` |
| **单元测试** | `docker/langbot/plugins/silent-observer/tests/test_face_unit.py` | 部署到 `langbot-plugin:/tmp/` 执行 |
| **冒烟测试** | `docker/langbot/plugins/silent-observer/tests/test_smoke.py` | 部署到 `napcat:/tmp/` 执行 |
| **E2E 测试** | `docker/langbot/plugins/silent-observer/tests/test_e2e_sync.py` | 部署到 `langbot-plugin:/tmp/` 执行 |
| **健康巡检** | `nas/health-check.sh` | NAS: `/volume1/docker/langbot/health-check.sh` |
| **relay v2** | (临时，待入库) | 容器 `napcat:/tmp/relay_v2.py`，监听 `:8888` |
| **LangBot 源码** | (第三方，只读) | 容器内 `/app/.venv/lib/python3.12/site-packages/langbot_plugin/api/entities/builtin/platform/message.py` |
| **聊天记录 DB** | (NAS 数据) | 容器 `langbot-plugin:/app/data/plugins/dou__langbot-silent-observer/chat_index.db` |
| **LangBot 配置 DB** | (NAS 数据) | 容器 `langbot:/app/data/langbot.db` |
| **插件配置** | LangBot WebUI 管理 | DB 表 `plugin_settings`，key=`dou__langbot-silent-observer` |
| **测试文档** | `docs/bot/automated-testing-guide.md` | — |
| **开发日志** | `docs/bot/silent-observer-dev-journal.md` | — |

### 部署命令速查

```bash
# 部署插件（推荐：直接写 NAS 卷，docker cp 有时静默失败）
scp docker/langbot/plugins/silent-observer/components/event_listener/default.py \
  root@nas:/volume1/docker/langbot/data/plugins/dou__langbot-silent-observer/components/event_listener/default.py

# 清缓存 + 重启
ssh root@nas "D=/volume1/@appstore/ContainerManager/usr/bin/docker; \
  \$D exec langbot-plugin sh -c 'find /app/data/plugins/dou__langbot-silent-observer -name __pycache__ -exec rm -rf {} +'; \
  \$D restart langbot-plugin"

# 运行冒烟
scp tests/test_smoke.py root@nas:/tmp/ && \
  ssh root@nas "D=/volume1/@appstore/ContainerManager/usr/bin/docker; \
  \$D cp /tmp/test_smoke.py napcat:/tmp/; timeout 30 \$D exec napcat python3 /tmp/test_smoke.py"

# 运行 E2E
scp tests/test_e2e_sync.py root@nas:/tmp/ && \
  ssh root@nas "D=/volume1/@appstore/ContainerManager/usr/bin/docker; \
  \$D cp /tmp/test_e2e_sync.py langbot-plugin:/tmp/; timeout 90 \$D exec langbot-plugin /app/.venv/bin/python3 /tmp/test_e2e_sync.py"
```

---

## 二、SSH + Docker 日常命令

### SSH 前提：WSL 必须关掉 Tailscale

**Tailscale 同时在 Windows 和 WSL 运行会导致 SSH 极不稳定。** 连接 NAS 前先在 WSL 里关掉 Tailscale：

```bash
sudo tailscale down
```

详见 [容器重启最佳实践 - Tailscale + WSL2 双端冲突](container-restart-best-practices.md#六tailscale--wsl2-双端冲突重要)

### Docker 路径

Synology 上 Docker 二进制不在标准 PATH，需指定完整路径或设别名：

```bash
# SSH 命令中
DOCKER=/volume1/@appstore/ContainerManager/usr/bin/docker
sudo $DOCKER ps
```

### 日常命令

```bash
# 环境变量
DOCKER=/volume1/@appstore/ContainerManager/usr/bin/docker

# 查看容器状态（所有命令加 timeout）
ssh root@nas "timeout 5 $DOCKER ps"

# 容器内执行 Python
ssh root@nas "timeout 10 $DOCKER exec langbot /app/.venv/bin/python3 ..."
ssh root@nas "timeout 10 $DOCKER exec langbot-plugin /app/.venv/bin/python3 ..."

# 重启（顺序重要！先 plugin 后 langbot）
ssh root@nas "timeout 20 $DOCKER restart langbot-plugin langbot"

# 传文件进容器
scp file.py root@nas:/tmp/ && ssh root@nas "timeout 10 $DOCKER cp /tmp/file.py langbot-plugin:/path/"

# 读插件日志
ssh root@nas "timeout 5 $DOCKER exec langbot-plugin cat /tmp/silent_init.log"
ssh root@nas "timeout 5 $DOCKER exec langbot-plugin cat /tmp/silent_gate.log"

# 查看 healthcheck 状态
ssh root@nas "timeout 5 $DOCKER inspect langbot --format '{{.State.Health.Status}}'"
```

---

## 三、部署标准流程

```bash
DOCKER=/volume1/@appstore/ContainerManager/usr/bin/docker
# 1. 上传代码
scp default.py root@nas:/tmp/silent_default.py

# 2. 清 pycache（必须！否则旧代码继续跑）
ssh root@nas "timeout 10 $DOCKER exec langbot-plugin sh -c '
  find /app/data/plugins/dou__langbot-silent-observer -name __pycache__ -exec rm -rf {} +
  find /app/data/plugins/dou__langbot-silent-observer -name \"*.pyc\" -delete
'"

# 3. 部署文件（优先用卷路径，docker cp 偶有静默失败）
# 卷映射：/volume1/docker/langbot/data/plugins → /app/data/plugins
scp default.py root@nas:/volume1/docker/langbot/data/plugins/dou__langbot-silent-observer/components/event_listener/default.py
# 备用方式：
# ssh root@nas "timeout 10 $DOCKER cp /tmp/silent_default.py langbot-plugin:<容器内路径>"

# 4. 重启（先 plugin，后主进程）
ssh root@nas "timeout 20 $DOCKER restart langbot-plugin langbot"
sleep 5

# 5. 验证启动
ssh root@nas "timeout 5 $DOCKER exec langbot-plugin cat /tmp/silent_init.log"
# 应看到：kb_enabled=True vision_enabled=True

# 6. 验证 healthcheck
ssh root@nas "timeout 5 $DOCKER inspect langbot --format '{{.State.Health.Status}}'"
# 应看到：healthy
```

**关键纪律**：
- 部署**必须**清 `__pycache__`，否则已删的函数仍被调用
- 重启**必须先 plugin 后主进程**，否则 napcat WebSocket 可能不重连（踩坑 #5）
- 重启后等 3 秒再验证，否则日志可能还没写完

---

## 四、数据库操作

### ChromaDB（群聊 KB 存储）
```python
import chromadb
c = chromadb.PersistentClient(path="/app/data/chroma")
col = c.get_collection("da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc")  # Dou KB
col = c.get_collection("992ae019-e8ff-47b1-81f7-94519ef2fb6d")  # LTM Long KB
```

### LangBot DB（SQLite）
```python
import sqlite3, json
db = sqlite3.connect("/app/data/langbot.db")
# 关键表：plugin_settings, legacy_pipelines, binary_storages,
#        monitoring_messages, monitoring_sessions, knowledge_bases, embedding_models
```

### 清除测试对话
```sql
DELETE FROM monitoring_messages WHERE session_id='group_1104330614';
DELETE FROM monitoring_sessions WHERE session_id='group_1104330614';
```

---

## 五、关键 UUID 速查

| 资源 | UUID |
|------|------|
| Dou KB | `da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc` |
| Long KB (LTM) | `992ae019-e8ff-47b1-81f7-94519ef2fb6d` |
| seekdb-local | `62e075f9-733f-458c-8ce8-d983c411cad9` |
| text-embedding-3-small | `c3037d01-1f6e-497a-8fb8-9bc5a69a874d` |
| qwen3.6-flash (vision) | `61a105e9-6180-45ee-a6f6-a7ec9d713265` |
| qwen3.7-plus (vision, 主 LLM 备选) | `5f82a8e5-1a47-47a1-92f3-4dff2f2600e0` |
| deepseek-v4-flash (当前主 LLM) | `b36247de-cea2-4cb4-9557-183f53f4d62b` |
| Pipeline | `dc0ff402-edc3-4dab-8054-d2a855241dea` |
| 测试群 | `group_1104330614` |
| 太空工程师群 | `group_116381172` |

---

## 六、日志解读

### 插件日志位置
- `/tmp/silent_init.log` — 初始化日志（在 langbot-plugin 容器内）
- `/tmp/silent_gate.log` — gate/inject/search 全链路日志（在 langbot-plugin 容器内）

### 日志含义
```
[silent] gate: allowed (at) doc_id=chat:xxx    ← @触发
[silent] inject START                            ← inject handler 被调用
[silent] at_text="xxx" sender=小通豆            ← 提取到的查询文本
[silent] search: 2 queries                       ← 搜索 query 数量
[silent] vector: 10 results                      ← 向量搜索返回数
[silent] keyword: 3 docs from 2 words            ← 关键词搜索
[silent] search: 5 results (after dedup)         ← 去重后结果数
[silent] INJECTED 5 search lines, prompt_msgs=65 ← 注入成功
```

---

## 七、SSH 安全绕过（重要）

### 问题：SSH 中间层污染

SSH 明文输出会被中间层截断/摘要/串扰，导致：
- 真实源码被替换成假注释（`# ... omitted by reader`）
- 输出变成 0 字节
- `wc -l` 结果重复打印

### 标准绕过方式
```bash
# 远端命令只输出纯 base64，不混任何明文
ssh -nT -o BatchMode=yes -o ConnectTimeout=6 root@nas \
  'timeout 10 docker exec langbot base64 -w0 /app/data/langbot.db' > /tmp/x.b64
tr -d '\n\r ' < /tmp/x.b64 | base64 -d > /tmp/x.db
```

**纪律**：远端命令只吐 base64，不混明文（混了明文会污染 base64 解码）

---

## 八、Docker Exec 安全规则

`ssh ... docker exec ... | 管道` 连续调用会在 NAS 上堆积僵死的 exec 会话，后续命令全部 hang。**2026-07-13 事故：15 个 `docker logs` 僵尸从 7/12 挂到 7/13，耗尽 Docker 守护进程。**

### 硬性规则

| 规则 | 做法 |
|------|------|
| 必须加 timeout | 每条 `docker exec/logs/restart` 前加 `timeout N` |
| 管道不跨 SSH | `\| tail` 放 `sh -c "..."` 内部 |
| docker logs 同样危险 | 和 exec 一样产生容器子进程 |

**正确模式：**
```bash
# ✅ 单次 exec 跑完所有，加 timeout
ssh root@nas "timeout 10 $DOCKER exec langbot-plugin sh -c '
  echo ===A===
  grep -c pattern /tmp/silent_gate.log
  echo ===B===
  tail -10 /tmp/silent_gate.log
'"

# ✅ docker logs 加 timeout + --tail（不输出全部再管道）
ssh root@nas "timeout 5 $DOCKER logs --tail 10 langbot 2>&1"

# ❌ 禁止：管道跨 SSH 边界
ssh root@nas 'docker logs langbot 2>&1 | tail -5'
```

---

## 九、Tailscale Serve 性能与诊断

### 诊断方法论

网络慢 ≠ 网络问题。依次排除：MTU → DNS/SNI → TLS → TCP 栈。

```bash
# 1. 路径 MTU 探测（从小往大试，直到丢包）
ping -M do -s 1100 <tailscale-ip>    # WSL/Linux
ping -f -l 1100 <tailscale-ip>       # Windows

# 2. TLS 时序分解（看瓶颈在 TCP 还是 TLS）
curl -w "TCP:%{time_connect}s TLS:%{time_appconnect}s 总:%{time_total}s" -o /dev/null -s <url>

# 3. 对比 HTTP 裸连基线（排除 TLS 因素）
curl -w "TCP:%{time_connect}s 总:%{time_total}s" -o /dev/null -s http://<ip>:<port>/
```

### Tailscale Serve HTTPS 慢（Windows 客户端）

**现象**：Windows 浏览器访问 `tailscale serve` 的 HTTPS 端口极慢（TLS 握手 >2s），同一网络 Android/WSL 正常。

**根因**：NAS Tailscale Serve gVisor TCP 栈的 Nagle 算法与 Windows Schannel 的延迟 ACK（200ms）冲突。每轮 TLS 1.3 握手 stall 200-400ms，叠加多次握手放大到 2-3 秒。

**验证**：WSL/Linux curl（OpenSSL）TLS ~100ms，Windows curl（Schannel）TLS ~2.7s。

**解决**：升级 Tailscale 到最新版。`tailscale update` 升级后 TLS 降至 ~80ms。

**Synology NAS 升级注意**：`synopkg` 在 `/usr/syno/bin/`，不在默认 PATH：
```bash
ssh root@nas 'PATH="/usr/syno/bin:/usr/local/bin:$PATH" tailscale update'
```
升级过程中 Tailscale 服务重启，SSH 会断连，重连后 `tailscale version` 确认。

### MTU 黑洞

Tailscale 隧道 MTU 默认 1280，减去 WireGuard 开销后实际可用 ~1240。如果中间链路 MTU 更小，TCP 段被静默丢弃（ICMP "需分片" 被 NAT/防火墙吞）→ 反复超时重传。

```bash
# 确认 MTU 黑洞
ping -M do -s 1200 <tailscale-ip>    # 丢包 = 黑洞

# 修复（Windows PowerShell 管理员）
netsh interface ipv4 set subinterface "Tailscale" mtu=1140 store=persistent
```

WSL 的 Tailscale 通常会自动探测正确 MTU（1140），Windows 可能不下调。

---

## 十、已踩坑汇总

| # | 坑 | 后果 | 解决/预防 |
|---|----|------|----------|
| 1 | `docker logs` 在 Synology NAS 上永久超时 | 命令卡死 | 用 `docker exec` + DB 查询代替 |
| 2 | `__pycache__` 不清 | 旧代码继续跑 | 部署前必须清 |
| 3 | 重启顺序反了（先主后 plugin） | napcat WS 不重连，消息丢失 | 先 plugin 后主进程 |
| 4 | 合并转发只有 Source 组件 | 提取文本为空 | 用 Quote 引用代替 Forward |
| 5 | docker exec 堆积僵尸会话 | 后续命令全部 hang | 单次 exec 跑完所有 |
| 6 | SSH 中间层污染明文 | 读到假数据 | 远端输出 base64 编码 |
| 7 | NAS + Docker + SSH 三重组合超过 5s 不可靠 | 连接积压/超时 | 长耗时操作在 NAS 本地终端跑 |
| 8 | Tailscale Serve gVisor Nagle + Windows Schannel | TLS 握手 >2s，页面极慢 | 升级 Tailscale 到最新版 |
| 9 | Tailscale MTU > 路径 MTU | TCP 段静默丢弃，重传风暴 | `ping -f -l` 探测，调低接口 MTU |
| 10 | `docker logs` 管道跨 SSH | Docker 守护进程耗尽，exec/restart/kill 全卡死 | `init: true` + timeout + 管道放 sh -c 内 |

---

## 十一、插件开发黄金法则

1. **开发时用 debug 模式**：`lbp run` 通过 WebSocket 热加载，无需重启
2. **加文件日志**：`print()` 到 stderr 可能被吞，写 `/tmp/` 文件
3. **验证顺序**：manifest 语法 → 插件进程启动 → 组件实例化 → 事件触发
4. **存储读写必须保守**：读失败绝不能写空数据覆盖旧数据
5. **消息组件树是嵌套结构**：Quote/Forward 含子 MessageChain，必须递归处理
6. **事件时机决定数据状态**：同一条消息在不同事件中内容可能已被前面的 stage 修改
