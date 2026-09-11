# NAS health-check 巡检修复计划

> 2026-09-11 | 分支 `nas-health-check-repair` | 关联工单 [issues/2026-09-11-nas-health-check-repair.md](../../issues/2026-09-11-nas-health-check-repair.md)
> 修订：2026-09-11 自查后修订（3 处实错 / 7 处空洞 / 2 项环境不适用），逐条记录见 §十

## 一、一句话

NAS 上的 `/volume1/docker/langbot/health-check.sh` 每 5 分钟在跑、日志在涨，但**自 2026-08-08 起从未真正生效**：探测文件路径失效 + `set -e` 吞掉失败计数；同时探针设计本身有误——用"发一条真消息走完整 LLM 链路"当健康检查。本计划修脚本、改心跳探针、按最佳实践统一重启顺序、回灌线上基线、并建立"仓库↔NAS"漂移对账。

## 二、问题与实测证据（2026-09-11）

| # | 缺陷 | 实测证据 | 影响 |
|---|------|---------|------|
| 1 | 探测文件路径失效 | NAS 卷上 `/volume1/docker/langbot/tests/` **不存在**；`scp … \|\| true` 静默失败 → `/tmp/test_smoke.py` 不存在 → 每轮 `python3: can't open file` | 探测永远失败，日志 10496 行几乎全是同一条错误，真信号被淹没 |
| 2 | `set -e` 吞掉计数逻辑 | 第 7 行 `set -e` + 第 59 行 `timeout 90 $DOCKER exec …` 非 0 退出 → 脚本当场终止，走不到第 66 行起的失败计数 | `/tmp/health_fail_count` 不存在，`grep -c FAIL` = 0；**自动重启自愈完全失效** |
| 3 | 通道 A 使用被明令禁止的命令形态 | 第 31–32 行 `docker logs … --since 5m \| grep -c`，每 5 分钟两次 | 与 2026-07-13 "15 个 docker logs 僵尸耗尽 Docker 守护进程"事故同构 |
| 4 | 重启命令无 `timeout` | 第 40/44/48/76/78/80 行裸 `$DOCKER restart …` | 违反文档硬性规则；7/13 事故中 `restart` 卡死正是放大因素 |
| 5 | 重启顺序与最佳实践文档相反 | 线上 `langbot → sleep 50 → plugin → sleep 15 → napcat`；文档 §一 要求 plugin → langbot → 验就绪 → napcat | napcat 的 WS 多断一次，重连撞上未就绪的 langbot 会 `ECONNREFUSED` |
| 6 | 仓库与线上不是同一份 | NAS 3410B/83 行 vs 仓库 1486B/46 行，md5 不同 | 照仓库修 = 修的不是线上那份 |
| 7 | 探针走真实 LLM 全链路 | 旧探针 `POST /bots/<uuid>/sync` → gate → 检索 → LLM | LLM 用量开销、写入聊天归档表、抢 WS 队列、**LLM 抖动被误判为服务故障并触发重启** |
| 8 | 文档口径三处矛盾 | 真实 cron 为 `*/5`；主文档未写、容器重启文档写 30 分钟、事故报告写 6 小时 | 事后复盘依据不可信 |
| 9 | napcat 判据选错，且混淆两类故障 | 旧探针查 `localhost:3000/get_status`。实测：容器内 `127.0.0.1:3000` 确为 NapCat OneBot v11 API（`app_name=NapCat.Onebot`），但**登录后才监听**——未登录时无监听，探针必然失败（实测 `Errno 99`）。宿主 `:3000` 是 **nginx**（另一服务，返回 HTML），宿主 `:5700` 有 docker-proxy 但容器内无监听（`Connection reset`）；配置声称 `0.0.0.0:5700` 与实际不符 | 判据把"账号未登录"混同为"服务故障"：修好后会每 10 分钟重启容器，而真正需要人工扫码的掉线无法被表达 |

**附带查明（缺陷 1 的真正根因）**：`test_smoke.py` 已于 commit `d96e25a`（2026-07-28）从 `tests/` 移入 `tests/scripts/`，NAS 脚本仍在找旧布局路径。**"把文件补到旧路径"是错的修法。**

## 三、已定决策

| 决策 | 选择 | 依据 |
|------|------|------|
| 巡检探针 | **A. 纯心跳探针**（零 LLM 调用） | §五；深度链路验证改为部署后人工跑一次 |
| 重启顺序 | 按 `container-restart-best-practices.md` §一：plugin → langbot → 验端口 08E8 + healthcheck → napcat | 该文档为权威；线上现状与之相反，本次一并纠正 |
| 验证窗口 | **接受一次真实重启**（约 1.5–3 分钟中断） | 用户 2026-09-11 确认 |
| 告警通道 | **不做**（B6，用户 2026-09-11 决定） | 重启事件只落持久化日志与状态文件，不接 notify/Telegram |

## 四、验收标准（AC）

- [ ] **AC1** 每轮巡检日志 ≤ 2 行，不再出现 `python3: can't open file` 等 traceback（零依赖自测 + NAS 连续 3 轮观察）
- [ ] **AC2** 探针**前置条件**缺失（docker 二进制不存在 / 目标容器不存在）→ 写 `SKIP <reason>` 且**不计入失败**，不触发重启
- [ ] **AC3** 计数链路可用：`HC_FORCE_FAIL=1` 连续 3 轮 → 日志 `FAIL #1/#2/#3` → `threshold reached` → 触发重启
- [ ] **AC4** 同一故障 10 分钟内不重复重启；flock 被占用时后续实例直接退出且不调用 docker
- [ ] **AC5** 重启顺序为 `langbot-plugin` → `langbot` → 端口就绪 → `napcat`；**每条 docker 命令都带 `timeout`**（含 3 条 restart）
- [ ] **AC6** 仓库 `nas/health-check.sh` 与 NAS 在版文件 md5 一致
- [ ] **AC7** 每轮写一行心跳（时间戳 + 五项结果码 + 是否重启），可据此判断脚本是否真的在跑
- [ ] **AC8** 巡检不再发起 HTTP `/sync`：① 脚本静态断言不含 `/sync`、`/bots`；② NAS 侧 `monitoring_messages` 中巡检专用 sender（`id='0'`/`name='smoke'`）行数增量为 0
- [ ] **AC9** 日志轮换生效：`health_check.log` 行数上界 500，不随时间单调增长
- [ ] **AC10** 文档中巡检间隔统一为 5 分钟（涉及 4 个文档）

## 五、新探针设计（零副作用）

| 检查项 | 命令（NAS 本地执行，全部加 `timeout`） | 通过判据 | 副作用 |
|--------|--------------------------------------|---------|--------|
| ① 插件心跳 | `$DOCKER exec langbot-plugin /app/.venv/bin/python3 -c "import os,time;print(int(time.time()-os.stat('/tmp/silent_stats.log').st_mtime))"` | 秒数 < 180 | 无（插件 `default.py:549-567` 每 60s 自写） |
| ② langbot 端口 | `$DOCKER exec langbot sh -c 'grep -c 08E8 /proc/net/tcp'` | ≥ 1 | 无 |
| ③ langbot 健康 | `$DOCKER inspect langbot --format '{{.State.Health.Status}}'` | `healthy` | 无 |
| ④ langbot HTTP | `$DOCKER exec napcat python3 -c "import urllib.request;print(urllib.request.urlopen('http://langbot:5300/',timeout=5).status)"` | `200` | 无 |
| ⑤ napcat QQ 进程存活 | `$DOCKER exec napcat sh -c 'grep -la "/opt/QQ/qq" /proc/[0-9]*/cmdline 2>/dev/null \| head -1'` | 输出非空 | 无 |
| （非重启项）napcat↔langbot WS | `$DOCKER exec napcat sh -c 'grep -c 08E8 /proc/net/tcp'` | ≥ 1；=0 时记 `ACCOUNT-OFFLINE`，**不计入重启阈值** | 无 |

**环境实测（均已确认）**：插件容器有 `/app/.venv/bin/python3`、`date`、`stat`、`flock`；napcat 容器有 `python3`、`curl`、`flock`；napcat **无 healthcheck**（`{{if .State.Health}}` 为空）故必须自建 ⑤；`langbot:5300` 从 napcat 容器内 `GET /` 实测返回 **200**。

**napcat HTTP 端口的实测事实（用于避免踩坑）**：

| 位置 | 事实 | 说明 |
|---|---|---|
| 容器内 `127.0.0.1:3000` | **NapCat OneBot v11 API 正常**（`app_name=NapCat.Onebot` v4.18.1，`get_login_info` 返回 `机器豆/3228649756`，错 token → 403） | **登录后才监听**；未登录（2026-09-11 上午实测）时该端口无监听 → 探针 ⑤ 必然失败 |
| 宿主 `:3000` | **nginx**（另一服务，返回 HTML 页面） | 文档里从宿主 `curl localhost:3000/...` 的示例会打到 nginx，不是 napcat |
| 宿主 `:5700` | docker-proxy 在听，但容器内**无监听** → `Connection reset by peer` | 配置 `onebot11_3228649756.json` 声称 `0.0.0.0:5700`，与实际不符 |
| 宿主 `:6099` | napcat WebUI（`301`），token `udimc123` | 登录二维码入口 |

**㊙ 2026-09-11 探针实测发现的线上事故（与本计划的判据设计直接相关）**

| 事实 | 证据 |
|---|---|
| QQ 账号**当前未登录** | napcat 日志反复输出登录二维码：近 6 小时 712 次、近 72 小时 1961 次；日志有"账号状态变更为离线"（09-10 11:20 / 14:14 / 17:56 …） |
| Bot 已掉线约 2 天 | 插件 `silent_gate.log` 最后更新 **2026-09-09 16:18:02**，之后无任何群事件 |
| 进程层健康 | `/proc/143/cmdline` = `/opt/QQ/qq --no-sandbox -q 3228649756`，容器与进程都活着 |
| WS 未建连 | napcat 内 `grep -c 08E8 /proc/net/tcp` = **0** |
| 登录入口 | napcat WebUI 监听 `6099`（`curl :6099/` 返回 301），token `udimc123`；容器端口映射 `5700→5700`、`6099→6099` |

**结论**："未登录"与"进程死了"是**两类不同故障**——前者重启容器毫无作用，必须人工扫码。旧探针把判据绑在"登录后才存在"的 NapCat HTTP 接口上（未登录时无监听，实测 `Errno 99`），于是把两类故障混为一谈：修好后会每 10 分钟重启容器一次，而真正需要人介入的掉线反而无法被表达。故 ⑤ 改为"进程存活"（重启项），另设非重启项 WS 链路检测并输出 `ACCOUNT-OFFLINE` 标记。

**心跳为何可信**：`silent_stats.log` 由插件事件循环内的 `stats_report_loop` 每 60 秒重写；mtime 变旧即代表**插件进程死亡或事件循环被阻塞**，正是 LTM not-found / 事件循环阻塞这类真实故障的直接指标。

**失败策略**：
- ①–⑤ 任一项失败记 1 次失败；连续 3 次（15 分钟，`HC_FAIL_THRESHOLD`，默认 3）→ 触发重启
- 重启前取 10 分钟防抖锁；`flock -n` 防 cron 重入
- 前置条件缺失走 SKIP（AC2），不计失败
- 重启三步均 `timeout 60 $DOCKER restart …`，超时按失败记录并保留锁

**覆盖率回退（有意接受）**：新探针只证"活着"，不证"业务跑通"——KB/chroma 损坏、pipeline 配置错误、napcat 连得上但发不出消息，旧设计理论上能发现、新探针发现不了。补偿：④ HTTP 探针 + 部署后人工跑一次 `tests/scripts/test_deploy_smoke.py`。**若日后要恢复深度覆盖**，用"每 6 小时一次全链路"（成本降 98%），本次不做，记为观察项。

**深度验证不进 cron**：`tests/scripts/test_deploy_smoke.py`（8 场景，含 LLM+检索）仅部署后人工跑一次。

## 六、Phase 0–5

### Phase 0 — 基线回灌（不改线上）

1. base64 拉回 NAS 在版 `health-check.sh` → 覆盖仓库 `nas/health-check.sh`（**commit A**，message 标注"回灌线上版，含已废弃的危险写法，见下一提交"）
2. 回灌 `/etc/crontab` 快照 → `docs/references/nas-crontab-snapshot-20260911.txt`；`/usr/local/bin/clean-zombie-ssh.sh` → `nas/clean-zombie-ssh.sh`（脚本放在 `nas/` 与 health-check.sh 同处，便于对照，属对计划的微小调整）
3. 新建 `nas/README.md`：记录 nas/ 目录职责、部署方向（仓库 → NAS）、基线 md5 + mtime 表
4. 核对 crontab 其余条目（`powersched`、3 条 `synoschedtask`）是否有未入库脚本

### Phase 1 — 脚本修复（**commit B**）

| 改动 | 前 | 后 |
|---|---|---|
| 退出码捕获 | `timeout 90 $D exec … >> LOG 2>&1` | `… \|\| exit_code=$?`（`\|\|` 豁免 `set -e`） |
| 探测方式 | 外部 `test_smoke.py` 全链路（旧路径 + 同机 scp） | 内联五项心跳探针（§五），**不再依赖外部脚本** |
| 通道 A（LangRAG not found） | `$D logs langbot-plugin --since 5m \| grep -c` | `timeout 8 $D logs --since 5m --tail 500 <c> > /tmp/hc_scan.txt 2>&1` 后对文件 `grep -c`。**时间窗必须保留**：实测插件日志约 1 行/5 分钟，`--tail 300` 单独使用会横跨约 25 小时，把一天前的报错反复计入 → 永久误重启 |
| 重启命令 | 裸 `$D restart …` | `timeout 60 $D restart …`，超时计入失败并保留锁（AC5） |
| 重启顺序 | langbot → 50s → plugin → 15s → napcat | plugin → langbot → 轮询 `08E8` + healthcheck（上限 60s）→ napcat → 验 `refused` |
| 并发保护 | 无 | `mkdir -p /volume1/docker/langbot/state`；`exec 9>/volume1/docker/langbot/state/hc.flock; flock -n 9 \|\| exit 0` |
| 防抖锁 | `/tmp/health_lock`（重启即丢） | `/volume1/docker/langbot/state/health.lock`（持久化） |
| 可观测性 | 只有 OK/FAIL，无心跳 | 每轮单行 `[date] heartbeat probe=11111 restart=0` |
| 日志轮换 | 无（已涨到 10496 行） | 每轮结束保留末 500 行（AC9） |
| 测试开关 | 无 | `HC_FAIL_THRESHOLD`（默认 3）、`HC_FORCE_FAIL`（默认 0）——仅本地/验证用，cron 不设置 |
| 静默吞错 | `scp … \|\| true`、`$D cp … \|\| true` | 全部删除；被忽略的失败必须留日志行 |

> ⚠️ `/volume1/docker/langbot/state` **实测不存在**，必须由脚本 `mkdir -p` 或部署步骤创建，否则 `set -e` 下首轮即崩。

### Phase 2 — 测试（**commit C**）

**环境实测约束**：本机 docker 无任何镜像、无外网（base 镜像 `bats/bats:latest` / `ubuntu:22.04` 拉不到），本机也未安装 bats → `tests/run_tests.sh` **在本环境无法运行**。故：

1. `tests/integration/health_check_selftest.sh` — **零依赖** bash 自测（临时 PATH 前置 docker stub），本机与 NAS 均可直接跑；覆盖：
   - 五项探针全绿 → 心跳行 `probe=11111`、无重启、清计数
   - `HC_FORCE_FAIL=1` 连续 3 轮 → `FAIL #1/#2/#3` + `threshold reached` + 调用 stub restart
   - 前置条件缺失（stub 无容器）→ `SKIP` 且不重启（AC2）
   - 锁新鲜 / flock 被占 → 直接退出、不调用 docker（AC4）
   - stub 记录的重启参数顺序为 `langbot-plugin langbot` 后 `napcat`，且每条 restart 都带 timeout（AC5）
   - 输出不含 traceback（AC1）；日志行数上界（AC9）
   - 静态断言脚本不含 `/sync`、`/bots`（AC8①）
2. `tests/integration/test_health_check.bats` — 薄封装，调用同一自测脚本，供有网/CI 环境走标准套件（不重复逻辑）
3. 本地验收命令：`bash tests/integration/health_check_selftest.sh`；标准套件路径保留 `bash tests/run_tests.sh -f health`（本机不可用，CI 用）

### Phase 3 — 部署与线上验证

**前置**：先把 commit A–C 合入 `main`，**从 main 部署**（memory 既有教训：所有修改先合 main 再从 main 部署），部署后记录 NAS 与 `git show main:nas/health-check.sh` 的 md5。

**3a（只验计数，不触发重启）**
1. 备份线上：`cp health-check.sh health-check.sh.bak.20260911`
2. `scp` 新脚本 → 两端 md5 比对（AC6）
3. `HC_FAIL_THRESHOLD=99 HC_FORCE_FAIL=1 bash health-check.sh` 跑 2 轮 → 日志出现 `FAIL #1/#2` + 心跳行
4. 清理 `/volume1/docker/langbot/state/health_fail_count`，md5 复核

**3b（接受一次真实重启）**
5. `HC_FORCE_FAIL=1 bash health-check.sh` 连续 3 次（计数文件已存在则从 1 续）→ 第 3 次触发真实重启
6. 按容器重启文档 §三 验证：`silent_init.log` = `kb_enabled=True vision_enabled=True`；`inspect … Health.Status` = `healthy`；napcat 无 `refused`；gate 日志出现 `inject START`；**插件↔langbot 重新注册成功**
7. 观察 3 个 cron 周期（15 分钟）：心跳行连续、无 traceback、无 SKIP、日志未超 500 行

> 全程 `ssh -nT -o BatchMode=yes -o ConnectTimeout=6` + 单次远端复合命令；长耗时（重启 ~1.5–3 分钟）用 `nohup … &` 或 NAS 本地终端，绝不在 SSH 链路里等。

### Phase 4 — 文档口径统一（**commit D**）

- `docs/bot/nas-access-best-practices.md`：补巡检真实间隔 5 分钟、新探针说明、7/13 三层防御、`patches/`+`entrypoint.sh` 三向核对、NAS 宿主机文件 `chown 1000:1000`、重启顺序引用权威文档
- `docs/bot/container-restart-best-practices.md`：修正"每 30 分钟"→ 5 分钟；修正第 60 行自身违反第 69 行规矩的验证命令（`docker logs … | grep`）
- `docs/bot/incident-20260713-docker-hang.md`：修正"每 6 小时"
- `docs/bot/AGENTS.md`：更新"已知问题：health-check cron 每 5 分钟触发 LLM pipeline"为整改后状态
- 各文档中 `tests/test_smoke.py` 过期路径 → `tests/scripts/`

### Phase 5 — 漂移对账（**commit E**）

1. `nas/check-drift.sh`：比对 NAS 在版文件与仓库 **main 分支**内容（`git show main:nas/health-check.sh | md5sum`，无需在 NAS 上放仓库副本），输出一致/漂移结论
2. **运行位置**：开发机手动或 cron（只读、无副作用）；不做通知通道（B6 决定）
3. 在 `nas/README.md` 与 `nas-access-best-practices.md` 写入纪律：改 NAS 任何在版脚本，当场回灌仓库 + 记 md5；`scp` 整目录覆盖前三向核对

## 七、风险与回滚

| 风险 | 缓解 |
|------|------|
| 3b 重启导致 QQ Bot 中断约 1.5–3 分钟；napcat 重启后 QQ 侧行为无文档记录（极端情况需人工登录） | 低活跃时段；执行前备份脚本；重启后按四项清单 + 插件重注册验证；残余风险已知并接受 |
| 计数逻辑写错 → 周期性重启容器 | 零依赖自测先行（Phase 2）；3a 用 `HC_FAIL_THRESHOLD=99` 只验计数 |
| 通道 A 丢失时间窗 → 永久误重启（自查已发现的原计划缺陷） | 强制保留 `--since 5m`，自测断言命令含 `--since` |
| flock 写法错误导致"秒退"，日志干净更难发现 | 每轮心跳行（AC7）；部署后必须确认心跳在跳 |
| 回灌把危险历史版本带进 git，被后人照抄 | 基线回灌与修复分两个 commit，基线 message 明确标注废弃写法 |
| 覆盖率回退（只证活着） | §五补偿三招；观察项：每 6 小时低频全链路 |

**回滚**：Phase 3 前 `cp` 备份；回滚 = 恢复备份文件（脚本层）+ `git revert` 对应 commit（仓库层）。脚本本身不会导致 napcat 掉线，恢复脚本救不回已掉线的 napcat，需 NAS 本地终端处理。

## 八、工作量与分批

| 批次 | 内容 | 估时 | 风险 |
|------|------|------|------|
| A | Phase 0+1+2（本地） | ~3h（含零依赖自测） | 零风险 |
| B | Phase 4+5（文档+对账，只读 NAS） | ~1h | 零停机 |
| C | Phase 3a（只验计数） | ~20min | 极低 |
| D | Phase 3b（真实重启） | ~10min + 1.5–3min 停机 | 已知并接受 |

## 九、Out of scope

- 不动 `langbot` / `langbot-plugin` / `napcat` 之外的服务
- 不改容器 compose（`init: true`、healthcheck 已符合文档）
- 不重构文档结构，只改事实性数字与追加章节
- 不把深度冒烟（LLM+检索）放进 cron
- **不做告警通知通道**（B6）

## 十、自查修订记录（2026-09-11）

自查方式：把计划中的每条技术假设拿到线上实测（NAS + 本机 docker/工具链）。

**实错（3）**
- **A1** `--tail 300` 去掉时间窗 → 实测 `docker logs --tail 300 langbot-plugin` 的 300 行横跨约 **25 小时**（插件 1 行/5 分钟，末 3 行时间戳 10:09/10:14/10:19），会把一天前的报错反复计入 → 永久误重启。原推理"300 行远超 5 分钟产量"方向相反。已改 `--since 5m --tail 500`（组合有效性已实测）。
- **A2** 重启命令缺 `timeout`（原计划完全漏掉，线上在版 6 处裸 `restart`）→ 已加入 AC5 与 Phase 1。
- **A3** AC9「LLM 调用增量为 0」不可测（群内有真人消息时该表必然增长）→ 改为静态断言 + 巡检专用 sender 行数增量。

**空洞（7）**
- **B1** `/volume1/docker/langbot/state` 实测不存在 → 脚本 `mkdir -p`。
- **B2** flock 路径未定（`/var/lock` 是 `/run/lock` 软链、重启即失）→ 两个锁统一放 state 目录。
- **B3** 3a 需临时改阈值文件（两次 scp + 忘还原风险）→ 改环境变量 `HC_FAIL_THRESHOLD` / `HC_FORCE_FAIL`。
- **B4** AC2 的 `SKIP: probe script missing` 与新探针矛盾（外部脚本已删除）→ 重定义为前置条件缺失。
- **B5** 日志无轮换（新增心跳行会年增约 10 万行）→ 保留末 500 行，新增 AC9。
- **B6** 无告警通道 → **用户决定不做**，写入 Out of scope。
- **B7** 漏"先合 main 再从 main 部署"→ 已补入 Phase 3 前置。

**环境不适用（2）**
- **C1** 本机零 docker 镜像、无外网、未装 bats → `tests/run_tests.sh` 不可运行；Phase 2 改为零依赖 bash 自测 + bats 薄封装。
- **C2** 原"跑 `tests/run_tests.sh -f health` 作为本地验收"作废，改为 `bash tests/integration/health_check_selftest.sh`。

**实测确认无误（D）**：心跳探针所需工具链齐备；napcat 无 healthcheck；langbot:5300 实测 200；`08E8` 检查返回 1；`--since + --tail` 组合有效；工单 `status: backlog` 不被 dispatch 捞取。

**补记：探针上机实测（2026-09-11，写脚本后逐条在真 NAS 跑）**
- 探针 ①–④ 与就绪轮询、日志扫描**实测全部符合预期**（心跳年龄 59s、端口 1、healthy、HTTP 200、`grep -q` ok、扫描 0 命中）。
- 探针 ⑤ **原设计失败**：`localhost:3000` 报 `Errno 99`。查证后确认：容器内 `127.0.0.1:3000` 就是 NapCat OneBot API，但**仅在登录后才监听**（宿主 `:3000` 是 nginx、`:5700` 无后端）→ 判据改为"QQ 进程存活"，另设 WS 链路非重启项。
- 顺带发现**线上事故**：QQ 账号未登录、Bot 掉线约 2 天（详见 §五）→ 新增非重启项 `link`（WS 链路）与 `ACCOUNT-OFFLINE` 标记，并把该发现写入缺陷 9。
- 自测相应扩充：T7b（QQ 进程缺失 → `probe=11110` 计入阈值）、T7c（WS 掉线 → 记 `ACCOUNT-OFFLINE`、`link=0`、**不触发重启**）；整套自测 38 项全绿。
