# NAS health-check 巡检修复计划

> 2026-09-11 | 分支 `nas-health-check-repair` | 关联工单 [issues/2026-09-11-nas-health-check-repair.md](../../issues/2026-09-11-nas-health-check-repair.md)

## 一句话

NAS 上的 `/volume1/docker/langbot/health-check.sh` 每 5 分钟在跑、日志在涨，但**自 2026-08-08 起从未真正生效**：探测文件路径失效 + `set -e` 吞掉失败计数；同时探针设计本身有误——用"发一条真消息走完整 LLM 链路"当健康检查。本计划修脚本、改心跳探针、按最佳实践统一重启顺序、回灌线上基线、并建立"仓库↔NAS"漂移对账。

## 二、问题与实测证据（2026-09-11）

| # | 缺陷 | 实测证据 | 影响 |
|---|------|---------|------|
| 1 | 探测文件路径失效 | NAS 卷上 `/volume1/docker/langbot/tests/` **不存在**；`scp … \|\| true` 静默失败 → `/tmp/test_smoke.py` 不存在 → 每轮 `python3: can't open file` | 探测永远失败，日志 10496 行几乎全是同一条错误，真信号被淹没 |
| 2 | `set -e` 吞掉计数逻辑 | 脚本第 7 行 `set -e`，第 59 行 `timeout 90 $DOCKER exec …` 非 0 退出 → 脚本当场终止，走不到第 66 行起的失败计数 | `/tmp/health_fail_count` 至今不存在，`grep -c FAIL` = 0；**自动重启自愈完全失效** |
| 3 | 通道 A 使用被明令禁止的命令形态 | 第 31–32 行 `docker logs … --since 5m \| grep -c`，每 5 分钟两次 | 与 2026-07-13 "15 个 docker logs 僵尸耗尽 Docker 守护进程"事故同构，属活的复发风险 |
| 4 | 重启顺序与最佳实践文档相反 | 线上：`langbot → sleep 50 → plugin → sleep 15 → napcat`；[container-restart-best-practices.md §一](../bot/container-restart-best-practices.md) 要求 plugin → langbot → 验端口就绪/healthcheck → napcat | napcat 的 WS 多断一次，重连撞上未就绪的 langbot 会 `ECONNREFUSED` |
| 5 | 仓库与线上不是同一份 | NAS 在版 3410B / 83 行（含 LangRAG 通道 A）；仓库 `nas/health-check.sh` 1486B / 46 行；md5 不同 | 照仓库修 = 修的不是线上那份 |
| 6 | 探针用真实 LLM 全链路 | `tests/scripts/test_smoke.py` 走 `POST /bots/<uuid>/sync` → gate → 检索 → LLM | 288 次/天 LLM 调用、写入 `monitoring_messages`、抢 WS 队列、**LLM 抖动会被误判为服务故障并触发重启** |
| 7 | 文档口径三处矛盾 | 真实 cron 为 `*/5`；主文档未写、容器重启文档写 30 分钟、事故报告写 6 小时 | 事后复盘依据不可信 |

**附带查明（缺陷 1 的真正根因）**：`test_smoke.py` 已于 commit `d96e25a`（2026-07-28，"测试目录整理：7 个 Docker 内联脚本移到 tests/scripts/"）从 `tests/` 移到 `tests/scripts/`，而 NAS 脚本仍在找旧布局路径。**所以"把文件补到旧路径"是错的修法。**

## 三、已定决策

| 决策 | 选择 | 依据 |
|------|------|------|
| 巡检探针 | **A. 纯心跳探针**（零 LLM 调用） | 见 §五；深度链路验证改为部署后人工跑一次 |
| 重启顺序 | 按 `container-restart-best-practices.md` §一：plugin → langbot → 验端口 08E8 + healthcheck → napcat | 该文档为权威；线上现状与之相反，本次一并纠正 |
| 验证窗口 | **接受一次真实重启**（langbot/plugin/napcat，约 95s 中断） | 用户 2026-09-11 确认 |

## 四、验收标准（AC）

- [ ] **AC1** 每轮巡检日志 ≤ 2 行，30 天窗口内不再出现 `python3: can't open file` 等 traceback
- [ ] **AC2** 探测文件缺失时写一条明确 `SKIP: probe script missing`，且**不计入失败**（不触发重启）
- [ ] **AC3** 计数链路可用：stub 令探针固定失败 → 日志出现 `FAIL #1/#2/#3` → `threshold reached` → 触发重启
- [ ] **AC4** 同一故障 10 分钟内不重复重启（flock 串行 + 持久化锁）
- [ ] **AC5** 重启顺序为 plugin → langbot → 端口就绪 → napcat，且重启后 `healthcheck=healthy`、napcat 无 `ECONNREFUSED`
- [ ] **AC6** 仓库 `nas/health-check.sh` 与 NAS 在版文件 **md5 一致**
- [ ] **AC7** 每轮巡检写一行心跳日志（时间戳 + 四项结果码），可据此判断"脚本有没有真的在跑"
- [ ] **AC8** 连续 5 轮巡检窗口内 LLM API 调用增量为 0（探针不再走 pipeline）
- [ ] **AC9** 文档中巡检间隔只剩一个数字（5 分钟），与 `/etc/crontab` 一致

## 五、新探针设计（零副作用）

| 检查项 | 命令（NAS 本地执行，均加 `timeout`） | 通过判据 | 副作用 |
|--------|--------------------------------------|---------|--------|
| 插件心跳 | `$DOCKER exec langbot-plugin stat -c %Y /tmp/silent_stats.log` 与容器内 `date +%s` 比较 | 差值 < 180s | 无（插件 `default.py:549-567` 每 60s 自写） |
| langbot 端口 | `$DOCKER exec langbot sh -c 'grep -c 08E8 /proc/net/tcp'` | ≥ 1 | 无 |
| langbot 健康 | `$DOCKER inspect langbot --format '{{.State.Health.Status}}'` | `healthy` | 无 |
| napcat 存活 | `$DOCKER exec napcat python3 -c "urllib…/get_status?access_token=…"` | `data.online == true` | 无 LLM |

**心跳探针为什么可信**：`silent_stats.log` 由插件事件循环内的 `stats_report_loop` 每 60 秒重写一次，文件 mtime 变旧即代表**插件进程死亡或事件循环被阻塞**——正是 LTM not-found / 事件循环阻塞这类真实故障的直接指标。

**失败策略**：探针失败连续 3 次（15 分钟）→ 触发重启；重启前先取 10 分钟锁；`flock -n` 防 cron 重入。

**深度验证不进 cron**：`tests/scripts/test_deploy_smoke.py`（8 场景，含 LLM+检索）仅在**部署后人工跑一次**。

## 六、Phase 0–5

### Phase 0 — 基线回灌（不改线上）

1. 用 base64 拉回 NAS 在版 `health-check.sh`，覆盖仓库 `nas/health-check.sh`（**commit A**，message 标注"回灌线上版，含已废弃的危险 `docker logs` 管道写法，见下一提交"）
2. 回灌 `/etc/crontab` 快照与 `/usr/local/bin/clean-zombie-ssh.sh` 到 `docs/references/`，记录 md5 + mtime
3. 核对 crontab 其余条目是否有未入库脚本

### Phase 1 — 脚本修复（**commit B**）

| 改动 | 前 | 后 |
|---|---|---|
| 退出码捕获 | `timeout 90 $D exec … >> LOG 2>&1` | `… \|\| exit_code=$?`（`\|\|` 豁免 `set -e`） |
| 探测文件来源 | `scp "$PROJECT_DIR/tests/test_smoke.py"`（同机自我拷贝 + 旧路径） | 删除；改为 §五 的四项心跳探针，命令内联，无外部脚本依赖 |
| 通道 A | `$D logs langbot-plugin --since 5m \| grep -c` | 保留"LangRAG not found"检测，但改为 `timeout 8 $D logs --tail 300 <c> > /tmp/hc_scan.txt 2>&1` 后对文件 `grep -c`（实测 langbot 0 行/5min、plugin 1 行/5min，300 行远超 5 分钟产量，不漏检） |
| 重启顺序 | langbot → 50s → plugin → 15s → napcat | plugin → langbot → 轮询 `08E8` + healthcheck（上限 60s）→ napcat → 验 `refused` |
| 并发保护 | 无 | `exec 9>/var/lock/hc.lock; flock -n 9 \|\| exit 0` |
| 锁文件 | `/tmp/health_lock`（重启即丢） | `/volume1/docker/langbot/state/health.lock`（持久化） |
| 可观测性 | 只有 OK/FAIL | 每轮固定写 `[date] heartbeat probe=1111 restart=0` 单行 |
| 静默吞错 | `scp … \|\| true`、`$D cp … \|\| true` | 全部删除；任何被忽略的失败必须留日志行 |

### Phase 2 — bats 测试（**commit C**）

`tests/integration/test_health_check.bats`，用 docker stub（临时 PATH 前置一个假 `docker`）覆盖：

1. 四项探针全绿 → 日志 `heartbeat probe=1111`、无重启、清空计数
2. 探针固定失败 3 次 → `FAIL #1/#2/#3` + `threshold reached` + 调用 stub 的 restart
3. 探针脚本缺失 → `SKIP` 且不重启（AC2）
4. 锁新鲜 / flock 被占 → 直接退出、不调用 docker
5. 断言输出**不含 traceback**（AC1）
6. stub 返回码为 0 时重启调用顺序为 `plugin langbot … napcat`（AC5）

跑 `bash tests/run_tests.sh -f health`（alpine + ubuntu 双发行版；断言避开 busybox 不支持的 `grep -oP`）。

### Phase 3 — 部署与线上验证

**3a（只验计数，不触发重启）**
1. 备份线上：`cp health-check.sh health-check.sh.bak.20260911`
2. `scp` 新脚本 → 两端 md5 比对（AC6）
3. 把探针阈值临时改为"永真失败"？**不**——改为把失败阈值临时设为 99，令其只累计不重启；观察 2 轮：日志出现 `FAIL #1/#2` + 心跳行
4. 还原阈值，md5 复核

**3b（接受一次真实重启）**
5. 低活跃时段触发一次真实重启（阈值还原为 3 后连续 3 轮，或手工跑一次重启分支）
6. 按容器重启文档 §三 四项验证：`silent_init.log` = `kb_enabled=True vision_enabled=True`；`inspect … Health.Status` = `healthy`；napcat 无 `refused`；gate 日志出现 `inject START`
7. 观察 3 个 cron 周期（15 分钟）心跳行连续、无 traceback

> 全程用 `ssh -nT -o BatchMode=yes -o ConnectTimeout=6` + 单次远端复合命令；长耗时（95s 重启）用 `nohup … &` 或在 NAS 本地终端跑，绝不在 SSH 链路里等。

### Phase 4 — 文档口径统一（**commit D**）

- `docs/bot/nas-access-best-practices.md`：补巡检真实间隔 5 分钟、新探针说明、7/13 三层防御、`patches/`+`entrypoint.sh` 三向核对、NAS 宿主机文件 `chown 1000:1000`、重启顺序引用权威文档
- `docs/bot/container-restart-best-practices.md`：修正"每 30 分钟"→ 5 分钟；修正第 60 行自身违反第 69 行规矩的验证命令（`docker logs … | grep`）
- `docs/bot/incident-20260713-docker-hang.md`：修正"每 6 小时"
- `docs/bot/AGENTS.md`：更新"已知问题：health-check cron 每 5 分钟触发 LLM pipeline"为整改后状态
- 顺带修正各文档中 `tests/test_smoke.py` 的过期路径 → `tests/scripts/`

### Phase 5 — 漂移对账（**commit E**）

1. 新增 `nas/check-drift.sh`：比对 NAS 在版脚本与仓库文件 md5，不一致则输出差异并（可选）Telegram 通知
2. 挂 cron 每小时一次（只读，无副作用）
3. 在 `nas-access-best-practices.md` 写入纪律：改 NAS 任何在版脚本，当场回灌仓库 + 记 md5；`scp` 整目录覆盖前三向核对

## 七、风险与回滚

| 风险 | 缓解 |
|------|------|
| 3b 重启导致 QQ Bot 中断约 95s；napcat 重启后的 QQ 侧行为无文档记录（极端情况需人工重新登录） | 低活跃时段执行；执行前备份脚本；重启后按四项清单验证；残余风险已知并接受 |
| 计数逻辑写错 → 每 10 分钟重启一次容器 | Phase 2 stub 测试先行；3a 用阈值 99 只验计数，不让第 3 次真正触发 |
| flock 写法错误导致脚本"秒退"，且日志干净更难发现 | 每轮写心跳行（AC7）；部署后必须确认心跳在跳 |
| 通道 A 改 `--tail 300` 漏检 | 已实测日志产量（0/1 行每 5 分钟），300 行远超窗口 |
| 回灌把危险历史版本带进 git，被后人照抄 | 基线回灌与修复分两个 commit，基线 message 明确标注废弃写法 |

**回滚**：Phase 3 前 `cp` 备份；回滚 = 恢复备份文件（脚本层）+ `git revert` 对应 commit（仓库层）。脚本本身不会导致 napcat 掉线，故恢复脚本不能救已掉线的 napcat，需 NAS 本地终端处理。

## 八、工作量与分批

| 批次 | 内容 | 估时 | 风险 |
|------|------|------|------|
| A | Phase 0+1+2（本地） | ~2.5h | 零风险 |
| B | Phase 4+5（文档+对账，只读 NAS） | ~1h | 零停机 |
| C | Phase 3a | ~20min | 极低 |
| D | Phase 3b | ~10min + 2min 停机 | 已知并接受 |

## 九、Out of scope

- 不动 `langbot` / `langbot-plugin` / `napcat` 之外的服务
- 不改容器 compose（`init: true`、healthcheck 已符合文档）
- 不重构文档结构，只改事实性数字与追加章节
- 不把深度冒烟（LLM+检索）放进 cron
