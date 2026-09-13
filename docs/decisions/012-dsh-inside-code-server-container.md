# ADR-012：DeepSeek Harness 装在 code-server 容器内，经 Tailscale 访问

> 2026-09-11 | 状态：✅ 已采纳并部署验证 | 计划与验收：[../plans/2026-09-11-dsh-in-code-server.md](../plans/2026-09-11-dsh-in-code-server.md) | 运维手册：[../bot/dsh-on-nas.md](../bot/dsh-on-nas.md)

## 背景

需求（用户提出）：在 NAS 上的 code-server Docker 里装 DeepSeek Harness（DSH），
像 code-server 一样经 Tailscale 远程访问，并且**重建 docker 不丢认证、不丢插件、不丢配置**。

先确定了三条环境事实（实测，非推断）：

| 事实 | 证据 |
|---|---|
| NAS 主机本身没有 Node/npm | `which node npm` 为空；DSH 只能跑在容器里 |
| code-server 容器已具备全套工具链、凭据、项目目录 | 容器内 `git/gh/tmux/jq/python3`、`/home/coder/.config/{gh,ssh,gitconfig}`（挂载卷）、`/home/coder/project`（挂载卷）；archon 已作为 supervisord 程序跑在同容器 8420 |
| NAS 直连 `api.deepseek.com` 与 `registry.npmjs.org` 均可达 | 主机与容器内 curl 分别返回 401（0.09s）与 200 —— **不需要走网关代理** |

## 决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | DSH 装在 **code-server 容器内**（不另起独立容器） | 工具链/凭据/项目/出网通路都已在该容器；该容器已有"supervisord 追加服务"的成熟先例（archon/bgutil-pot/youtube-kb）。另起容器等于把这些年积累的 Dockerfile 重造一遍 |
| D2 | 用**预下载 Node 22 tarball + sha256** 覆盖 `/usr/bin` 版本，钉 `v22.22.2` | base 镜像自带的 Debian Node **20.19.2 上 DSH rc.7 起不来**（`node:module` 缺 `stripTypeScriptTypes`、`node:zlib` 缺 `createZstdDecompress`，插件树加载即失败）。版本与开发机完全一致，消除"两边行为不同"这一变量。不用 NodeSource 是为了不跟随上游漂版本 |
| D3 | 状态根 `DSH_HOME=/home/coder/.config/dsh`（落在**已挂载的 config 卷**内），并加 `~/.dsh` 符号链接 | `~/.dsh` 默认位置**没有挂卷，重建即丢**。放进 config 卷同时让 `gh`/`ssh`/`gitconfig` 等既有凭据与 DSH 同处持久层。符号链接沿用该容器 `.claude`/`.gitconfig` 的既有做法，是漏传环境变量时的第二道保险 |
| D4 | 暴露链路：DSH 绑 `127.0.0.1:3081` → **socat 转容器 `0.0.0.0:3080`** → compose 只发布 `127.0.0.1:3080` → NAS `tailscale serve --https=3080`（tailnet only） | DSH 的 `--host` schema **只接受 `127.0.0.1\|0.0.0.0`**，且 `0.0.0.0` 被 CLI 明确拒绝（原话：*"would expose remote code execution to the network"*）。**选择不绕过这道护栏**：用一次 TCP 转发保住 loopback 姿态，对 DSH 内部实现零依赖，升级不会失效。socat 是裸 TCP 转发，WebSocket/SSE 天然可用 |
| D5 | **不做应用层认证**（2026-09-13 修订：该前提已被上游改掉，见文末「修订」） | DSH 自身不提供认证/TLS（官方明确列为限制）。用户决策：Tailscale 单人可达即门禁。因此**端口只发布到 NAS 回环**，LAN 上没有入口 |
| D6 | 沙箱策略固定为 `danger-full-access`（`DSH_PERMISSION_MODE`） | Synology 内核 5.10 **既无 Landlock 又未开 user namespaces**：`workspace-write` 沙箱"没有可用后端"，bash 工具 fail-closed 直接拒绝执行；bubblewrap 实测不可用（`unshare --user` → `EINVAL`）。该变量是 base bundle 认的部署默认值（同时决定沙箱模式与审批策略）。**隔离边界交给容器本身** |
| D7 | 程序在镜像（钉版本）、状态在卷 | 这是"重建不丢"的机制本身：`npm i -g @deepseek-ai/dsh@0.1.0-rc.7` 进镜像；认证/设置/插件/会话全在 `$DSH_HOME`。**用户手工 `npm i -g` 装的东西会随重建丢失**，装插件要走 `dsh plugin` |
| D8 | 必须声明 `--trusted-host nas.tail152b92.ts.net` | `/api` 要求 Host 是 loopback 或在 `trustedHosts` 内（无端口条目匹配任意端口），否则**页面能打开但对话连不上**（静默假成功）。实测经 serve 访问时 Host 为 `nas.tail152b92.ts.net:3080` |

## 代价与局限（明确接受）

- **生命周期耦合**：改这个 Dockerfile 重建，code-server 与 DSH 一起重启；反之 DSH 崩不影响 code-server（supervisord 各自拉起）
- **agent 权限面**：DSH 以 coder 身份在容器内拥有完整 shell，可触及 code-server 的配置卷、`gh` token、`ssh` key、`/data` 里的 cookie。这是既有终端权限的延伸，但**自动化后暴露面变大**；换来的正是"agent 能直接干活"
- **NAS 无法自测该 URL**：NAS 连自己的 tailnet 名/IP 均超时（既有现象，8686 通路同样如此），必须在另一台 tailnet 设备上验证
- **serve 配置存在 tailscaled 状态里**：Tailscale 包重装/重置后需重新执行一次 `tailscale serve --bg --https=3080 http://127.0.0.1:3080`
- **`DSH_HOME` 会被 DSH 递归 watch**：该目录内出现非 coder 可读文件（如 root 所有、600 的备份）会让 DSH 进程 `EACCES` 崩溃 —— 已实测踩到，备份必须放到 `DSH_HOME` 之外
- **未纳入巡检**：目前 DSH 不进 `nas/health-check.sh`（那是 langbot 栈的），漂移对账仅覆盖镜像定义文件

## 相关文件

| 类型 | 位置 |
|---|---|
| 镜像定义 | `docker/code-server/Dockerfile`（Node 22 层、DSH 层、socat、两个 supervisord 程序） |
| 编排 | `docker/code-server/docker-compose.yml`（`127.0.0.1:3080` 端口、`DSH_HOME`、`DSH_PERMISSION_MODE`） |
| 运维手册 | `docs/bot/dsh-on-nas.md`（访问、重建、升级、排查、种子） |
| 计划与验收 | `docs/plans/2026-09-11-dsh-in-code-server.md` |
| 教训 | `memory/dsh-on-nas-lessons-20260911.md` |
| 漂移对账 | `nas/manifest.tsv`（含上述两个文件行） |
| 取入口 URL | `nas/dsh-url.sh`（2026-09-13 新增，因 D5 修订而生） |

## 修订：2026-09-13 升级 `0.1.0-rc.7` → `0.1.5-rc.2`

D7 的钉版本已随之更新为 `0.1.5-rc.2`（仍与开发机一致）。两处事实变化：

1. **D5 的前提不再成立**：0.1.5 起 DSH web **自带浏览器鉴权**（`BrowserAuth`）。启动 token 是**进程级随机值**，
   只打印在 `dsh web` 的 stdout；用它访问 `/` 会 303 并签发绑定 host 的 cookie（有效期 30 天）。**token 每设备只需一次性使用**：
   cookie 校验只依赖持久签名密钥（存在卷内凭据文件），**dsh 重启/容器重建都不使其失效**（2026-09-13 实测旧 cookie 重启后仍 200）。
   新设备、清 cookie、超 30 天时才需重新取 token → 新增 `nas/dsh-url.sh`。
   实查上游**无关闭/固定该鉴权的开关**（`dsh web --help`、`settings.yaml` schema、安装包内 `noAuth/skipAuth` 均属第三方依赖噪声）。
   **安全面结论不变且略有改善**：LAN 依旧无入口；差别在于 tailnet 内其他设备现在也需要先拿到 token（只能从容器日志读），
   即"能进容器者等于有权限"这一既有前提没变。
2. **升级不再只是改一行版本号**：0.1.5 把 `@deepseek-ai/dsh-persona` 的 `config.text`（string 必填）改名为 `prefix`（必填），
   与 rc.7 **互不兼容** ⇒ 必须"先重建升级、再改 preset 一行"，否则 preset 挂载失败、没有 agent
   （症状：新会话建不了、老会话 resume 失败、前端狂刷 `commands/list`）。完整流程见运维手册 §五。
