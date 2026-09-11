---
name: nas-ops
description: NAS（Synology Docker）运维流程——巡检解读、在版脚本部署、漂移对账、QQ 掉线恢复、SSH/Docker 纪律与故障速查。当需要查看/修改 NAS 上的 langbot / langbot-plugin / napcat、解读 /tmp/health_check.log、部署 nas/ 下的脚本、处理 QQ 掉线或排查容器异常时使用。
---

# NAS 运维（nas-ops）

面向"把 NAS 上的服务跑稳、且改动可回退"的操作流程。**事实性数据不在这里重复**，一律指向仓库内的权威文件；本 skill 只写"怎么做、按什么顺序做、什么不能做"。

## 何时用 / 何时不用

- 用：巡检判读、在版脚本部署与对账、容器/QQ 异常排查、告警处置
- 不用：改插件业务逻辑（走 `.claude/gate-checklists/bot-plugin-review.md` + `docs/bot/silent-observer-dev-journal.md`）；DevFlow 管线自身问题（走 `docs/design/`）

## 0. 先确认事实，不要凭记忆

| 要确认的事 | 命令 / 位置 |
|---|---|
| 仓库与 NAS 在版是否一致 | `bash nas/check-drift.sh`（3 项 md5 对账） |
| 巡检是否真的在跑 | `ssh root@nas 'tail -1 /tmp/health_check.log'` |
| 端口/路径事实 | `docs/bot/nas-access-best-practices.md` §一（napcat 端口）、§十二（巡检） |
| 脚本清单与 md5 基线 | `nas/README.md` |
| 当前阶段工单 | `issues/2026-09-11-nas-obs-t*.md` |

> 环境事实（2026-09-11 实测）：NAS 基本无外网；开发机无法访问 Telegram；**唯一 Telegram 通道是阿里云 `115.29.110.107`**。

## 1. 巡检解读

日志：NAS `/tmp/health_check.log`（保留末 500 行）；每轮一行心跳。

| 行样式 | 含义 | 需要动作 |
|---|---|---|
| `heartbeat probe=11111 link=1 restart=0 qq=1` | 五项探针全绿、WS 通、登录态正常 | 无 |
| `probe=11110` 等含 0 | 对应探针失败（位序：心跳/端口/healthcheck/HTTP/napcat进程） | 看是否累计到阈值 |
| `FAIL #N probe=…` | 第 N 次连续失败（阈值默认 3） | 连续 3 次会触发重启 |
| `threshold reached (…), restart: …` | 正在按序重启 | 等待 + 按 §4 验证 |
| `locked (last restart …)` | 10 分钟防抖锁内，本轮直接退出 | 正常 |
| `SKIP <reason>` | 前置条件缺失（docker/容器不存在），不计失败 | 连续 3 次会告警 |
| `QQ-OFFLINE state=0 events=N link=1` | **登录态异常**（`link=1` 也可能是离线！） | 走 §5 人工扫码 |
| `ACCOUNT-OFFLINE …` | WS 未建连 | 同上 |
| `ALERT <type> <detail>` | 已写本地告警文件 | 见 §2 |

状态文件（`/volume1/docker/langbot/state/`）：`health_fail_count`（连续失败数）、`health.lock`（上次重启时间戳）、`health_skip_count`、`alert`（待发告警）、`alert.history`（已发归档）、`alert.last`（去重时间）。

测试/演练开关（cron 不设置）：`HC_FORCE_FAIL=1` 强制探针失败、`HC_FAIL_THRESHOLD=N` 覆盖阈值、`HC_STATE_DIR/HC_LOG` 覆盖路径（影子运行用）。

## 2. 告警类型 → 处置

| 类型 | 含义 | 处置 |
|---|---|---|
| `qq-offline` | 账号未登录/被置离线（含"进程活着但掉线"） | **人工扫码**：`http://nas:6099`（token `udimc123`）；重启容器无效 |
| `restart` | 巡检触发了重启 | 按 §4 验证清单确认恢复 |
| `skip` | 前置条件连续缺失 3 次 | 查 docker 二进制与三个容器是否存在 |
| `deep-smoke-fail` | 6 小时金丝雀失败（LLM/检索链路） | 看 `/tmp/deep_smoke.log`；LLM 抖动可忽略一次，连续失败需查 |

告警链路：NAS 写 `state/alert` → 阿里云 cron `*/5` 拉取 → Telegram。排查：云侧 `/var/log/nas-alert.log`；开发机看门狗 `~/.local/state/nas-watchdog.log`。

## 3. 部署标准流程（7 步，逐条验证）

1. **worktree**：`git worktree add -b <task> .worktrees/<task>`（沙箱写不了 `/home/dou/wt`，用仓库内嵌套 worktree；项目铁律禁止直接改主仓库）
2. **改 + 本地自测**：`bash tests/integration/health_check_selftest.sh`（零依赖，52 项）
3. **合 main 并推送**：`git merge --ff-only` → `git push origin main`（main 可能被其他会话推进 → 先 `git rebase main` 再合）
4. **部署**：先备份 `cp <file> <file>.bak.<date>`，再 `scp` 到 NAS 生产路径
5. **两端 md5 一致**：`md5sum` 本地与 NAS 各一份，必须相同
6. **影子运行**：`HC_STATE_DIR=/tmp/shadow HC_LOG=/tmp/shadow.log bash <script>`（打真容器、写 /tmp，不碰生产状态）
7. **生产验证**：等 1–2 个 cron 周期看心跳行；`bash nas/check-drift.sh` 必须 3 项 OK；更新 `nas/README.md` 基线 md5

## 4. 重启后验证清单

1. `docker inspect langbot --format '{{.State.Health.Status}}'` → `healthy`
2. napcat 内 `grep -c 08E8 /proc/net/tcp` → ≥1（WS 通）
3. `/tmp/silent_init.log` 含 `kb_enabled=True vision_enabled=True` 且 mtime 是刚才
4. 序列**完成后**无 `refused`（重启窗口内 1 条瞬时 ECONNREFUSED 属预期）
5. `get_login_info` 正常（QQ 未掉线）

顺序权威：`docs/bot/container-restart-best-practices.md` §一 —— `langbot-plugin` → `langbot` → 等端口就绪 → `napcat`。

## 5. QQ 掉线恢复

1. 浏览器开 `http://nas:6099`（token `udimc123`），扫码（二维码约每 30 秒刷新，别用容器内 png 文件）
2. 恢复后验证：napcat 内 `curl 127.0.0.1:3000/get_login_info?access_token=…`、`link=1`、插件 `silent_gate.log` mtime 更新
3. 取证（判断是否为同一故障）：`docker logs --since <t> napcat` 里找 `账号状态变更为离线` / `你的用户身份已失效` / `请扫描下面的二维码`
4. 已知规律：会话失效前会有多次"变更为离线"，**期间 WS 仍连着**——所以只看 `link` 会误判

## 6. SSH / Docker 纪律（每条都是踩过的坑）

- 所有远端 docker 命令加 `timeout N`；`docker logs` 必须 `--since Xm --tail N`（**不能只给 `--tail`**：插件日志 1 行/5 分钟，300 行会横跨约 25 小时）
- 管道不跨 SSH 边界；要过滤就重定向到文件后在远端 grep
- 单次 `exec` 跑完多条命令，别连击（僵尸会话会耗尽 Docker 守护进程）
- 长耗时操作（>5s）不在 SSH 链路里等：用 `nohup … &` 或后台作业
- 文本证据用 base64 取回（明文会被中间层截断/串扰/伪造）
- 别用 `set -e` 直接包住会失败的探针命令（`cmd || rc=$?` 捕获），否则后续逻辑静默不可达

## 7. 故障速查

| 症状 | 先看 |
|---|---|
| 巡检日志不更新 | cron 行是否存在、`flock` 是否卡住、脚本 md5 是否被换 |
| 收到 `restart` 告警 | §4 验证清单 + `/tmp/health_check.log` 上下游几行 |
| 收到 `qq-offline` | §5 扫码 + 取证 |
| 消息不进插件 | `silent_gate.log` mtime、`link`、napcat `get_status` |
| 告警没到 Telegram | 云侧 cron/`/var/log/nas-alert.log`、NAS `state/alert` 是否积压 |
| 怀疑脚本被改过 | `bash nas/check-drift.sh`、`md5sum` 对照 `nas/README.md` |
