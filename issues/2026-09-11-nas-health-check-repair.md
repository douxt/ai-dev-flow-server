---
type: HITL
estimate: 0.5d
effort: small
status: backlog
blocked_by: []
needs_llm: false
needs_vision: false
needs_pdf: false
needs_docker: true
test_files:
  - tests/integration/health_check_selftest.sh
  - tests/integration/test_health_check.bats
safety: ""
---

# NAS health-check 巡检失效：自愈从未生效 + 探针走 LLM 全链路

- 日期：2026-09-11（同日自查修订）
- 发现方式：SSH 实测 NAS（`ssh root@nas`）+ cron/日志/在版脚本取证 + 本机工具链实测
- 涉及组件：NAS `/volume1/docker/langbot/health-check.sh`（cron `*/5`）、仓库 `nas/health-check.sh`
- 严重度：P1（保护机制静默失效 30+ 天；探针设计还会引入 288 次/天 LLM 调用与误重启风险）
- 修复计划：[docs/plans/2026-09-11-nas-health-check-repair.md](../docs/plans/2026-09-11-nas-health-check-repair.md)

## 摘要

NAS cron 每 5 分钟运行 `health-check.sh`，但该脚本**自 2026-08-08 起从未真正生效**：探测文件路径失效 + `set -e` 使失败计数与自动重启分支永远不可达。日志累积 10496 行，几乎全是同一条 `python3: can't open file '/tmp/test_smoke.py'`。此外探针用"发一条真消息走完整 LLM pipeline"做健康检查，修好路径反而会引入 288 次/天 LLM 调用、写入聊天数据、并把 LLM 抖动误判为服务故障而自动重启容器。

## 缺陷一：探测文件路径失效（根因：7/28 目录重构）

`test_smoke.py` 在 commit `d96e25a`（2026-07-28，"测试目录整理：7 个 Docker 内联脚本移到 tests/scripts/"）由 `tests/` 移入 `tests/scripts/`；NAS 脚本仍在找 `$PROJECT_DIR/tests/test_smoke.py`，而 NAS 卷 `/volume1/docker/langbot/tests/` **从未存在过**。第 57 行 `scp … || true` 静默吞掉失败 → 后续 `docker cp`、`python3` 全链路空转。

## 缺陷二：`set -e` 使自愈逻辑不可达

第 7 行 `set -e` + 第 59 行 `timeout 90 $DOCKER exec …` 非 0 退出 → 脚本当场终止，第 66 行起的失败计数、阈值重启全部执行不到。证据：`/tmp/health_fail_count` 不存在，日志中 `FAIL` 计数为 0，最后一次真实自愈是 2026-08-08 16:51（LangRAG ×5 触发）。

## 缺陷三：通道 A 使用被文档禁止的命令形态

第 31–32 行 `$DOCKER logs langbot-plugin --since 5m | grep -c`（另加一条 `langbot` 同款），每 5 分钟执行两次。与 2026-07-13"15 个 `docker logs` 僵尸耗尽 Docker 守护进程"事故同构。

## 缺陷四：重启命令无 `timeout`

第 40/44/48/76/78/80 行均为裸 `$DOCKER restart …`。文档硬性规则要求所有 docker 命令加 `timeout`；7/13 事故中 `restart` 卡死正是放大因素。修复后 3 条 restart 均加 `timeout 60`，超时计入失败路径。

## 缺陷五：重启顺序与最佳实践文档相反

线上：`langbot → sleep 50 → plugin → sleep 15 → napcat`。
`docs/bot/container-restart-best-practices.md` §一 要求：`langbot-plugin → langbot → 等端口 08E8 + healthcheck → napcat`（理由：napcat 依赖到 langbot:2280 的 WS，langbot 后重启会让 napcat 多断一次，重连撞上未就绪的 langbot 会 `ECONNREFUSED`）。

## 缺陷六：仓库与线上不是同一份，且文档口径矛盾

NAS 在版 3410B / 83 行；仓库 `nas/health-check.sh` 1486B / 46 行；md5 不同 → 照仓库修无效。巡检间隔文档三处矛盾（5 / 30 分钟 / 6 小时），实测 `/etc/crontab` 为 `*/5`。

## 缺陷七：探针走真实 LLM 全链路

旧探针通过 `POST /bots/<uuid>/sync` 发起真实消息 → gate → 检索 → LLM。后果：LLM 用量开销、向聊天归档表写入巡检伪造记录、抢 WS 队列（dev-journal 第 16 坑）、**失败可能是 LLM 抖动而非服务故障，会诱发误重启**。

## 缺陷八：napcat 判据选错，且混淆"未登录"与"进程死了"

旧探针查 `http://localhost:3000/get_status`。实测（2026-09-11）：
- 容器内 `127.0.0.1:3000` **确为** NapCat OneBot v11 API（`app_name=NapCat.Onebot` v4.18.1，`get_login_info` 返回 `机器豆/3228649756`，错 token → 403），但**仅在登录后才监听**；账号未登录时该端口无监听 → 探针必然失败（实测 `Errno 99`）
- 宿主 `:3000` 是 **nginx**（另一服务，返回 HTML）；宿主 `:5700` 有 docker-proxy 但容器内无监听（`Connection reset by peer`）；配置 `onebot11_3228649756.json` 声称 `0.0.0.0:5700` 与实际不符

后果：判据把"账号未登录"混同为"服务故障"——修好后会每 10 分钟重启容器，而真正需要人工扫码的掉线无法被表达。修复：⑤ 改判"QQ 进程存活"（重启项，`grep -la "/opt/QQ/qq" /proc/[0-9]*/cmdline`），另设非重启项 WS 链路检测（`grep -c 08E8 /proc/net/tcp`），未建连时输出 `ACCOUNT-OFFLINE` 但不计入阈值。

## 附：2026-09-11 关联线上事故（QQ 掉线，需人工处置）

探针上机实测时发现：napcat 反复输出登录二维码（近 6 小时 712 次 / 近 72 小时 1961 次），日志有"账号状态变更为离线"；插件 `silent_gate.log` 最后更新停在 **2026-09-09 16:18:02** → **Bot 已掉线约 2 天**。QQ 进程与容器均存活，WS 到 `langbot:2280` 连接数为 0。登录入口：napcat WebUI `http://<nas>:6099`（token `udimc123`）。该事故本身不属于本工单修复范围（需人工扫码），但它是"未登录类故障重启无效"这一判据设计的直接依据。

## Acceptance Criteria

> 2026-09-11 执行结果：以下 AC 均已实测验证（证据见括号）。部署版本 md5 `8df813471e86be2f4f221ecae9ca20e0`。

- [x] `[auto]` AC1: 每轮日志 ≤ 2 行且无 traceback（自测 T1/T9；生产 11:00 轮次单行 `heartbeat probe=11111 link=1 restart=0`）
- [x] `[auto]` AC2: 前置条件缺失 → `SKIP container-missing`、不计失败、不重启（自测 T3）
- [x] `[auto]` AC3: 连续 3 轮强制失败 → `FAIL #1/#2/#3` + `threshold reached` + 重启（自测 T2；真机 3b：11:00:30 触发）
- [x] `[auto]` AC4: 锁新鲜/flock 被占时不调用 docker（自测 T4/T5）
- [x] `[auto]` AC5: 顺序为 `langbot-plugin` → `langbot` → `napcat`，每条 restart 带 timeout（自测 T2/T9；真机日志 `restart: langbot-plugin → langbot → napcat`、`langbot port ready=1 (waited ~24s)`）
- [x] `[auto]` AC6: 脚本不含 `/sync`、`/bots`（自测 T9）
- [x] `[auto]` AC7: 日志轮换生效（自测 T8；真机由 871 KB / 10496 行收敛到 500 行）
- [x] `[human-verify]` AC8: NAS 在版与 `git show main:nas/health-check.sh` md5 一致（`nas/check-drift.sh` 3 项全 OK）
- [x] `[human-verify]` AC9: 部署后 cron 轮次心跳连续、无 traceback、无 SKIP（11:00 / 11:05 / 11:10 三轮）
- [x] `[human-verify]` AC10: 重启验证 —— `healthcheck=healthy`、HTTP 200、`silent_init.log` 含 `kb_enabled=True vision_enabled=True`（11:00:54）、插件↔langbot 重新注册（`link=1`）、序列完成后无 refused（仅序列中 1 条瞬时 ECONNREFUSED，属预期）、QQ 登录未丢（`get_login_info` 正常）
- [x] `[human-verify]` AC11: `monitoring_messages` 中巡检专用标识（`user_id='0'`/`user_name='smoke'`）记录数 **0**，部署后无新增
- [x] `[decision]` AC12: 4 个文档巡检间隔统一为 5 分钟，并纠正历史误记
- [x] `[auto]` AC13: WS 掉线 → `ACCOUNT-OFFLINE` + `link=0` + 不重启（自测 T7c）；QQ 进程缺失 → `probe=11110` 计入阈值（自测 T7b）

## 前置准备

- [ ] NAS 备份点：`/volume1/docker/langbot/health-check.sh.bak.20260911`
- [ ] NAS 状态目录 `/volume1/docker/langbot/state/`（实测不存在，需 `mkdir -p`）
- [ ] 低活跃时段窗口（重启中断约 1.5–3 分钟）
- [ ] commit A–C 先合入 `main`，**从 main 部署**并记录 md5
- [ ] 本地零依赖自测可跑（`bash tests/integration/health_check_selftest.sh`）；`tests/run_tests.sh` 本机不可用（无镜像/无外网/未装 bats）

## 代码目录

- 实现: `nas/health-check.sh`（仓库为唯一事实源，scp 到 NAS）
- 测试: `tests/integration/health_check_selftest.sh`（零依赖）+ `tests/integration/test_health_check.bats`（薄封装）

## Scope

**In:** 脚本修复（退出码捕获、五项心跳探针、`--since` 时间窗、restart timeout、顺序纠正、flock、持久化锁、心跳行、日志轮换、测试开关）；线上基线回灌；零依赖自测 + bats 薄封装；4 个文档口径统一；漂移对账脚本。
**Out:** 容器 compose 变更；`langbot`/`langbot-plugin`/`napcat` 之外的服务；把深度冒烟放进 cron；**告警通知通道**（用户决定不做）；文档结构重构。

## 测试策略

- 集成自测：`tests/integration/health_check_selftest.sh`，docker stub（临时 PATH 前置假 docker），本机与 NAS 均可跑
- 标准套件：`tests/integration/test_health_check.bats` 薄封装调用同一自测（CI/有网环境走 `tests/run_tests.sh`）
- E2E：NAS 部署后 3a（`HC_FAIL_THRESHOLD=99` 只验计数）+ 3b（接受一次真实重启，按四项清单 + 插件重注册验证）

## 风险

- 风险1: 验证触发真实重启，QQ Bot 中断约 1.5–3 分钟；napcat 重启后 QQ 侧行为无文档记录 — 缓解: 低活跃时段 + 脚本备份 + 四项验证清单
- 风险2: 计数逻辑写错导致周期性重启 — 缓解: 零依赖自测先行；3a 只验计数（阈值 99）
- 风险3: 通道 A 若丢掉 `--since` 时间窗会永久误重启（实测 tail 300 横跨约 25 小时）— 缓解: 自测断言命令含 `--since`
- 风险4: flock 写法错误导致"秒退"，日志干净更难发现 — 缓解: 每轮心跳行 + 部署后确认心跳在跳
- 回退: 恢复 `health-check.sh.bak.20260911`；仓库侧 `git revert` 对应 commit

## 依赖表格

| SDK/工具 | 版本 | 参考 |
|----------|------|------|
| flock / timeout / stat / python3 | NAS `/usr/bin/`（已实测存在，容器内亦然） | `docs/bot/container-restart-best-practices.md` |
| bats-core | 现有 `tests/run_tests.sh`（alpine + ubuntu，本机不可用） | `tests/` |

## Ticket 质量自检

- [x] 1. estimate ≤1d
- [x] 2. type 正确（HITL：含人工验证与停机窗口）
- [x] 3. AC 可测量并标注 auto/human-verify/decision
- [x] 4. 代码目录已指定
- [x] 5. 前置准备含具体备份路径与目录
- [x] 6. mock/E2E 策略明确（docker stub + NAS 实机）
- [x] 7. 工具可用性已实测
- [x] 8. 验收无主观
- [x] 9. blocked_by 为空
- [x] 10. 架构约束引用最佳实践文档
- [x] 11. AC 覆盖集成层（AC5/AC9/AC10）
- [x] 12. Scope 边界清晰
- [x] 13. needs_* 已声明
- [x] 14. test_files 已指定
- [x] 15. 窗口预算 ≤40%
- [x] 16. safety 不适用
- [x] 17. 外部项目引用不适用
