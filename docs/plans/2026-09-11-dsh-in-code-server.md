# DSH 装入 code-server（DSH on NAS）

> 2026-09-11 | 分支 `dsh-in-code-server` | 架构决策：[ADR-012](../decisions/012-dsh-inside-code-server-container.md) | 运维手册：[../bot/dsh-on-nas.md](../bot/dsh-on-nas.md)

## 一、目标与验收

**目标**：NAS 上有一个 24/7 可用的 DSH（DeepSeek Harness）Web 实例，经 Tailscale 远程访问，且**重建 docker 后认证/插件/配置/会话全部不丢**。

**验收（全部实测通过）**：

| ID | 验收项 | 结果 |
|---|---|---|
| AC1 | 经 `https://nas.tail152b92.ts.net:3080` 从 tailnet 设备可打开 GUI | ✅ 首页 200；证书公信 CA 校验通过（`ssl_verify=0`，无需 `-k`） |
| AC2 | `/api` 未被信任栅栏拦（真同源可用） | ✅ 同源与无 Origin 均 `404`（已进路由）；恶意 Origin `403`（证明栅栏在生效，非全放行） |
| AC3 | 真实 agent 轮次可跑（LLM + bash 工具） | ✅ 返回内核 `5.10.55+` 与 `NAS_DSH_OK`，`rc=0` |
| AC4 | 未暴露到 LAN | ✅ 仅 `127.0.0.1:3080` 监听（`netstat` 实测） |
| AC5 | **重建镜像 + 重建容器后状态不丢** | ✅ 12 项指纹逐项一致（详见表下） |
| AC6 | 既有服务无回归 | ✅ `code-server` healthy、密码登录 302、扩展数不变；`claude 2.1.226` 在 Node 22 下正常；archon/bgutil-pot/youtube-kb 全部 RUNNING |
| AC7 | 镜像定义入库 + 漂移可发现 | ✅ 两个文件进 `nas/manifest.tsv`，`check-drift.sh` 13/13 OK |

### AC5 指纹对照（重建前 → 重建后）

| 项 | 前 | 后 |
|---|---|---|
| `settings.yaml` md5 | `95aa306ced37ad5478e32a97bbdf9752` | 同 |
| `AGENTS.md` md5 | `8a5c2afeaacdeee23aa146b673ad42bf` | 同 |
| preset 两文件 md5 | `79bca571…` / `de74671c…` | 同 |
| 插件清单 `profiles/web/package.json` md5 | `1da68b7c8045a35d4bc1717c034642c5` | 同 |
| `node_modules` 条目 / `DSH_HOME` 文件数 | 2 / 870 | 同 |
| 凭据（size/mode/owner） | 54 / 600 / 1000:1000 | 同 |
| profiles | `headless, node_modules, web` | 同 |
| VS Code 扩展数 / code-server 登录 | 1 / `302` | 同 |
| serve 3080 / supervisor 程序 | 在 / 5 个 | 同 |

## 二、实测钉死的约束（决定了方案形态）

| # | 约束 | 实测证据 | 对策 |
|---|---|---|---|
| C1 | DSH rc.7 需要 Node ≥ 22 | Node 20.19.2 下：`node:module` 无 `stripTypeScriptTypes`、`node:zlib` 无 `createZstdDecompress` → 插件树加载失败退出 | 镜像内置 Node 22.22.2（钉版，与开发机一致） |
| C2 | DSH 不能绑容器 eth0 地址 | `--host` schema：`expected "127.0.0.1" \| "0.0.0.0" but got "172.17.0.5"` | socat 转发（D4） |
| C3 | `--host 0.0.0.0` 被 CLI 拒绝 | 原话：*"would expose remote code execution to the network; use 127.0.0.1 instead"* | 不绕过；绑 loopback + 转发 |
| C4 | `~/.dsh` 默认没挂卷 | compose 仅挂 `config`/`project`/`code-server-data`/`data` | `DSH_HOME` 指向 config 卷内 |
| C5 | 容器缺 `pnpm` / `socat` | 探针：`pnpm=-`、`socat=-` | 两者进镜像 |
| C6 | `/api` 有 Host/Origin 栅栏 | `trustedHosts` 条目为 `host` 或 `host:port`，无端口条目匹配任意端口；恶意 Origin 实测 `403` | `--trusted-host nas.tail152b92.ts.net` |
| C7 | 内核无 Landlock、无 user namespaces | `/sys/kernel/security/lsm` 仅 `capability,apparmor`；`bwrap` → "Creating new namespace failed"；`unshare --user` → `EINVAL` | `DSH_PERMISSION_MODE=danger-full-access` |
| C8 | NAS 连不上自己的 tailnet 名/IP | 自测 `https://nas.tail152b92.ts.net:3080` 与 `:8686` 均超时；直连 `100.106.2.24:3080` 亦超时 | 验证必须在另一台 tailnet 设备上做 |
| C9 | DSH 递归 watch `DSH_HOME` | 放了 root 所有 600 的备份文件 → chokidar `EACCES` → 进程崩溃 | 备份放 `DSH_HOME` 之外（已修） |

## 三、决策记录（用户批准）

| # | 决策 |
|---|---|
| D1 | Node 升级方式：**预下载 tarball + sha256**（不用 NodeSource），版本钉 `v22.22.2` |
| D2 | 工作区：DSH 默认工作目录 = `/home/coder/project`（与 code-server 共用同一批仓库） |
| D3 | 纳入漂移对账：镜像定义文件进 `nas/manifest.tsv` |
| D4 | 认证：不做应用层认证（tailnet 单人可达即门禁） |

## 四、工作分解与执行结果

| ID | 内容 | 结果 |
|---|---|---|
| T0 | 收尾对齐：compose CLI、回滚镜像打 tag | ✅ `docker compose v2.32.2`；旧镜像存为 `code-server:rollback-dsh-20260911` |
| T1 | Dockerfile：Node 22 层 + `dsh@0.1.0-rc.7` + `pnpm@11` + `socat` + `~/.dsh` 符号链接 | ✅ 构建 `BUILD_EXIT=0`；Node tarball `sha256` 校验 OK |
| T2 | compose：`127.0.0.1:3080:3080` + `DSH_HOME` + `DSH_PERMISSION_MODE`；supervisord 加 `dsh`/`dsh-relay` | ✅ 两程序 RUNNING，与既有三程序并存 |
| T3 | 配置种子（凭据/设置/AGENTS.md/preset）+ 真实 agent 轮次 | ✅ 见 AC3；`standard-lite` preset 无开发机路径，可整体移植 |
| T4 | Tailscale 暴露 | ✅ `tailscale serve --bg --https=3080`，与 8686 并列，均为 tailnet only |
| T5 | 重建演练（真实 `build` + `--force-recreate`） | ✅ AC5 全绿 |
| T6 | 入库：镜像定义回灌 + manifest + 文档 | ✅ 本文件 + ADR-012 + 运维手册 + 教训 + 索引 |

**顺带回灌**：仓库里的 `docker/code-server/*` 原本**落后于 NAS**（NAS 上后加的离线安装、openkb、`/data` 权限等未入库）。本次以 NAS 为准整体回灌，因此 diff 里除 DSH 相关改动外，还包含这些历史差异。其中 `sysctls: fs.inotify.max_user_watches` 在 NAS 上已不存在（实际运行版本为准），未重新加回 —— 若需恢复请单独确认。

## 五、遗留与后续可选

| 项 | 说明 |
|---|---|
| 首次访问确认 | 请用浏览器打开 `https://nas.tail152b92.ts.net:3080` 跑一轮真实对话（我无法点 GUI） |
| 纳入巡检 | 可把「DSH 3080 可达 + serve 配置在」加入 NAS 自检（`nas/selfcheck.sh`）或独立探针 —— 当前未做 |
| 备份 | `$DSH_HOME` 现状约 870 文件；是否需要定期备份/快照未定 |
| 插件同步 | NAS 目前只有 `dsh-context`；开发机另有 MCP/hooks 桥接（依赖开发机绝对路径，未移植） |
| `DSH_HOME` 空间 | pnpm store 落在 `config/.pnpm-store`（同卷，重建不丢），长期增长需观察 |
