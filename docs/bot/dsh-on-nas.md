# DSH on NAS —— 运维手册

> 2026-09-11 起生效 | 决策依据：[ADR-012](../decisions/012-dsh-inside-code-server-container.md) | 计划与验收：[plans/2026-09-11-dsh-in-code-server.md](../plans/2026-09-11-dsh-in-code-server.md)

DeepSeek Harness 的 Web 实例跑在 NAS 的 **code-server 容器内**（supervisord 程序 `dsh` + `dsh-relay`），
经 Tailscale 访问。**不是独立容器**——理由见 ADR-012 的 D1。

## 一、怎么访问

| 方式 | 地址 | 说明 |
|---|---|---|
| **正常入口** | `https://nas.tail152b92.ts.net:3080` | tailnet only，公信 CA 证书，与 code-server 的 8686 并列 |
| 直连 tailnet IP | ✗ 不通（实测超时） | serve 只认 SNI 名，与既有 8686 行为一致 |
| LAN | ✗ **无入口**（有意为之） | 端口只发布到 NAS 回环；DSH 自身无认证，LAN 暴露等于开放 RCE |
| 容器内回环 | `http://127.0.0.1:3080`（NAS 上） | 运维自测用；经 docker-proxy → 容器 socat → DSH |

## 二、链路与端口

```
浏览器 https://nas.tail152b92.ts.net:3080
  → NAS tailscaled serve（tailnet only，证书由 Tailscale 签发）
  → NAS 127.0.0.1:3080（compose 端口发布，仅回环）
  → 容器 0.0.0.0:3080  socat（裸 TCP 转发 → WebSocket/SSE 天然可用）
  → 容器 127.0.0.1:3081  dsh web（保持 loopback：这是 DSH 唯一允许的绑定姿态之一）
```

| 端口 | 用途 |
|---|---|
| 3080 | 对外入口（NAS 回环 + 容器 relay） |
| 3081 | DSH 本体（仅容器内回环） |
| 8080 / 25252 / 8686 | code-server 自身（8080 容器内、25252 LAN、8686 serve） |
| 8420 | archon（同容器另一 supervisord 程序） |

## 三、持久化模型（"重建不丢"的机制）

| 层 | 内容 | 落点 | 重建后 |
|---|---|---|---|
| 程序 | Node 22.22.2、`@deepseek-ai/dsh@0.1.0-rc.7`、pnpm、socat | 镜像（Dockerfile） | 随镜像重建，版本可控 |
| **状态** | `.credentials.yaml`（API key）、`settings.yaml`、`AGENTS.md`、`.agent-presets/`、`profiles/**`（**插件**）、`sessions/`、`storages/` | `DSH_HOME=/home/coder/.config/dsh` → 卷 `/volume7/docker/codeserver/config/dsh` | **不丢** |
| 包缓存 | pnpm content-addressable store | `/home/coder/.config/.pnpm-store/v11`（同卷） | 不丢 |
| 既有凭据 | code-server `PASSWORD`（`.env`）、`gh`/`ssh`/`gitconfig` | 现有 config 卷 | 不丢 |

> ⚠️ **`DSH_HOME` 会被 DSH 递归 watch**：目录内出现 coder 读不到的文件（如 root 所有、600 的备份）会让进程 `EACCES` 崩溃。**备份一律放到 `DSH_HOME` 之外。**
>
> ⚠️ 手工 `npm i -g` 装的东西只进容器层，重建即丢；装插件请用 `dsh plugin --profile web add <pkg>`（落在 `$DSH_HOME/profiles`）。

## 四、常用运维命令

```bash
D=/volume1/@appstore/ContainerManager/usr/bin/docker     # NAS 上的 docker

# 服务状态（五个程序：archon / bgutil-pot / dsh / dsh-relay / youtube-kb）
$D exec code-server sudo supervisorctl status

# 健康检查：容器内回环 → 容器 relay
$D exec code-server bash -lc 'curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3081/'

# 日志（supervisorctl tail 比翻 /var/log 更省事）
$D exec code-server sudo supervisorctl tail -f dsh stderr
$D exec code-server sudo supervisorctl tail -f dsh-relay stderr

# 重启单个程序（不动 code-server）
$D exec code-server sudo supervisorctl restart dsh

# Tailscale 暴露状态
/var/packages/Tailscale/target/bin/tailscale serve status

# 必须在另一台 tailnet 设备上做（NAS 连不上自己的 tailnet 名，既有现象）
curl -s -o /dev/null -w '%{http_code}\n' https://nas.tail152b92.ts.net:3080/
```

## 五、重建 / 升级流程

**重建（改 Dockerfile 或 compose 后）**：

```bash
# 1. 开发机：改仓库文件后部署（Dockerfile 与 compose 都在 manifest 对账内）
cd <repo>/docker/code-server && scp Dockerfile docker-compose.yml root@nas:/volume7/docker/codeserver/
# 2. NAS：重建 + 重建容器（约 1 分钟，code-server 会短暂中断）
ssh root@nas 'D=/volume1/@appstore/ContainerManager/usr/bin/docker; cd /volume7/docker/codeserver && $D compose build && $D compose up -d'
# 3. 验证（对照 AC5 清单）
bash nas/check-drift.sh                       # 13/13 OK
#    容器内：supervisorctl status 五个 RUNNING；node -v=22.22.2；dsh --version=0.1.0-rc.7
#    tailnet 设备：首页 200；跑一轮对话（含一次 bash 工具调用）
```

**升级 DSH 版本**：改 Dockerfile 里 `npm install -g @deepseek-ai/dsh@<version>` 一行 → 走上面的重建流程。
状态在卷里，升级不动数据；**先确认新版本仍支持当前 Node 主版本**。

**回滚**：镜像有 `code-server:rollback-dsh-20260911`；
或 `docker compose down && docker tag code-server:rollback-dsh-20260911 codeserver-code-server:latest && docker compose up -d`。
备份文件：NAS `/volume7/docker/codeserver/{Dockerfile,docker-compose.yml}.bak.20260911-dsh`。

## 六、配置种子（首次或需要重放时）

```bash
CD=/volume7/docker/codeserver/config/dsh        # NAS 上
# 凭据（**不要在终端回显**）
cat ~/.dsh/.credentials.yaml | ssh root@nas "cat > $CD/.credentials.yaml"
ssh root@nas "chown 1000:1000 $CD/.credentials.yaml && chmod 600 $CD/.credentials.yaml"
# 设置与 preset（standard-lite 无开发机路径，可整体移植）
scp ~/.dsh/settings.yaml root@nas:$CD/settings.yaml
scp -r ~/.dsh/.agent-presets root@nas:$CD/.agent-presets
# 全局规则（把记忆路径改成容器内持久路径）
sed 's|/home/dou/claude-memories|/home/coder/.config/claude-memories|g; s|/home/dou/projects|/home/coder/project|g' \
  ~/.dsh/AGENTS.md | ssh root@nas "cat > $CD/AGENTS.md"
ssh root@nas "chown -R 1000:1000 $CD && chmod 700 $CD"
```

**种子后自检**（避免上面那个 EACCES 坑）：

```bash
ssh root@nas "find $CD ! -user 1000 -o ! -group 1000; find $CD ! -perm -u+r"
```

未移植：开发机的 `hooks.json` 与 MCP 桥接（依赖 `/home/dou/...` 绝对路径）。

## 七、故障排查

| 症状 | 原因 | 处置 |
|---|---|---|
| 页面能打开，但发消息无反应 / `/api` 403 | Host 不在 `trustedHosts`（tailnet 名变了，或漏了 `--trusted-host`） | 改 Dockerfile 里 `--trusted-host <名>` → 重建 |
| bash 工具报 `no sandbox backend is usable on this host` | `DSH_PERMISSION_MODE` 未生效 | 检查 compose `environment` 与 `dsh.conf` 的 `environment=` |
| `dsh` 反复重启，日志有 `EACCES … watch` | `DSH_HOME` 内有非 coder 可读文件 | 用上面的自检找到并移出 `DSH_HOME` |
| NAS 上 curl 该 URL 超时 | 既有现象（NAS 连不上自己的 tailnet 名） | 换 tailnet 设备验证；用容器内回环做本地自测 |
| 3080 无响应 | `dsh` 或 `dsh-relay` 挂了 | `supervisorctl status` → 看 stderr 日志 → `restart` |
| `tailscale serve status` 里没有 3080 | Tailscale 包重装/重置 | `tailscale serve --bg --https=3080 http://127.0.0.1:3080` |
| 插件装了但重建后没了 | 用了 `npm i -g` | 改用 `dsh plugin --profile web add <pkg>` |

## 八、已知限制

- **DSH 无认证/TLS**：安全边界 = Tailscale 身份 + tailnet ACL。任何能上 tailnet 的设备都能操作这个 agent（含 shell）
- **生命周期耦合**：改 code-server 的 Dockerfile 重建会同时重启 DSH
- **agent 权限面**：以 coder 身份在容器内可读写 code-server 的配置卷、`gh`/`ssh` 凭据、`/data`
- **未纳入巡检**：DSH 不在 `nas/health-check.sh` 覆盖内（那套服务的是 langbot 栈）；漂移对账只覆盖镜像定义文件
