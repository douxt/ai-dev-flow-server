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
  - tests/integration/test_health_check.bats
safety: ""
---

# NAS health-check 巡检失效：自愈从未生效 + 探针走 LLM 全链路

- 日期：2026-09-11
- 发现方式：SSH 实测 NAS（`ssh root@nas`）+ cron/日志/在版脚本取证
- 涉及组件：NAS `/volume1/docker/langbot/health-check.sh`（cron `*/5`）、仓库 `nas/health-check.sh`
- 严重度：P1（保护机制静默失效 30+ 天；同时探针设计会给线上引入 288 次/天 LLM 调用与误重启风险）
- 修复计划：[docs/plans/2026-09-11-nas-health-check-repair.md](../docs/plans/2026-09-11-nas-health-check-repair.md)

## 摘要

NAS cron 每 5 分钟运行 `health-check.sh`，但该脚本**自 2026-08-08 起从未真正生效**：探测文件路径失效 + `set -e` 使失败计数与自动重启分支永远不可达。日志累积 10496 行，几乎全是同一条 `python3: can't open file '/tmp/test_smoke.py'`。此外探针本身用"发一条真消息走完整 LLM pipeline"做健康检查，一旦修好路径反而会引入 288 次/天 LLM 调用、写入聊天数据、并把 LLM 抖动误判为服务故障而自动重启容器。

## 缺陷一：探测文件路径失效（根因：7/28 目录重构）

`test_smoke.py` 在 commit `d96e25a`（2026-07-28，"测试目录整理：7 个 Docker 内联脚本移到 tests/scripts/"）由 `tests/` 移入 `tests/scripts/`；NAS 脚本仍在找 `$PROJECT_DIR/tests/test_smoke.py`，而 NAS 卷 `/volume1/docker/langbot/tests/` **从未存在过**。第 57 行 `scp … || true` 静默吞掉失败 → 后续 `docker cp`、`python3` 全链路空转。

## 缺陷二：`set -e` 使自愈逻辑不可达

第 7 行 `set -e` + 第 59 行 `timeout 90 $DOCKER exec …` 非 0 退出 → 脚本当场终止，第 66 行起的失败计数、阈值重启全部执行不到。证据：`/tmp/health_fail_count` 不存在，日志中 `FAIL` 计数为 0，最后一次真实自愈是 2026-08-08 16:51（LangRAG ×5 触发）。

## 缺陷三：通道 A 使用被文档禁止的命令形态

第 31–32 行 `$DOCKER logs langbot-plugin --since 5m | grep -c`（另加一条 `langbot` 同款），每 5 分钟执行两次。与 2026-07-13"15 个 `docker logs` 僵尸耗尽 Docker 守护进程"事故同构。

## 缺陷四：重启顺序与最佳实践文档相反

线上：`langbot → sleep 50 → plugin → sleep 15 → napcat`。
`docs/bot/container-restart-best-practices.md` §一 要求：`langbot-plugin → langbot → 等端口 08E8 + healthcheck → napcat`（理由：napcat 依赖到 langbot:2280 的 WS，langbot 后重启会让 napcat 多断一次，重连撞上未就绪的 langbot 会 `ECONNREFUSED`）。

## 缺陷五：仓库与线上不是同一份，且文档口径矛盾

NAS 在版 3410B / 83 行；仓库 `nas/health-check.sh` 1486B / 46 行；md5 不同 → 照仓库修无效。巡检间隔文档三处矛盾（5 / 30 分钟 / 6 小时），实测 `/etc/crontab` 为 `*/5`。

## 缺陷六：探针走真实 LLM 全链路

`tests/scripts/test_smoke.py` 通过 `POST /bots/<uuid>/sync` 发起真实消息 → gate → 检索 → LLM。后果：LLM 用量开销、向聊天归档表写入巡检伪造记录、抢 WS 队列（dev-journal 第 16 坑）、**失败可能是 LLM 抖动而非服务故障，会诱发误重启**。

## Acceptance Criteria

- [ ] `[auto]` AC1: 新脚本每轮日志 ≤ 2 行且不含 traceback；回归测试 `tests/integration/test_health_check.bats` 覆盖此项
- [ ] `[auto]` AC2: 探针资源缺失时输出 `SKIP` 且不触发重启（stub 测试断言）
- [ ] `[auto]` AC3: stub 令探针连续失败 3 次 → 日志 `FAIL #1/#2/#3` + `threshold reached` + 调用 restart
- [ ] `[auto]` AC4: 锁新鲜或 flock 被占时不调用 docker
- [ ] `[auto]` AC5: stub 记录的重启参数顺序为 `langbot-plugin langbot` 后 `napcat`
- [ ] `[human-verify]` AC6: NAS 在版脚本与仓库 md5 一致
- [ ] `[human-verify]` AC7: 部署后 3 个 cron 周期（15 分钟）心跳行连续、无 traceback
- [ ] `[human-verify]` AC8: 重启验证后 `healthcheck=healthy`、napcat 无 `ECONNREFUSED`、`silent_init.log` 含 `kb_enabled=True vision_enabled=True`
- [ ] `[human-verify]` AC9: 连续 5 轮巡检窗口内 LLM API 调用增量为 0
- [ ] `[decision]` AC10: 文档中巡检间隔统一为 5 分钟（涉及 4 个文档）

## 前置准备

- [ ] NAS 备份点：`/volume1/docker/langbot/health-check.sh.bak.20260911`
- [ ] 低活跃时段窗口（重启中断约 95s）
- [ ] 本机 docker（跑 `tests/run_tests.sh` 双发行版 bats）

## 代码目录

- 实现: `nas/health-check.sh`（仓库为唯一事实源，scp 到 NAS）
- 测试: `tests/integration/test_health_check.bats`

## Scope

**In:** 脚本修复（退出码捕获、探针改造、顺序纠正、flock、持久化锁、心跳日志）；线上基线回灌；bats 回归测试；4 个文档口径统一；漂移对账脚本。
**Out:** 容器 compose 变更；`langbot`/`langbot-plugin`/`napcat` 之外的服务；把深度冒烟放进 cron；文档结构重构。

## 测试策略

- 单元/集成：`tests/integration/test_health_check.bats`，docker stub（临时 PATH 前置假 docker）
- E2E：NAS 部署后 3a（阈值 99 只验计数）+ 3b（接受一次真实重启，按四项清单验证）

## 风险

- 风险1: 验证触发真实重启，QQ Bot 中断约 95s；napcat 重启后 QQ 侧行为无文档记录 — 缓解: 低活跃时段 + 脚本备份 + 四项验证清单
- 风险2: 计数逻辑写错导致周期性重启 — 缓解: stub 测试先行；3a 只验计数
- 风险3: flock 写法错误导致"秒退"，日志干净更难发现 — 缓解: 每轮心跳行 + 部署后确认心跳在跳
- 回退: 恢复 `health-check.sh.bak.20260911`；仓库侧 `git revert` 对应 commit

## 依赖表格

| SDK/工具 | 版本 | 参考 |
|----------|------|------|
| flock / timeout / stat | util-linux（NAS `/usr/bin/`，已实测存在） | `docs/bot/container-restart-best-practices.md` |
| bats-core | 现有 `tests/run_tests.sh`（alpine + ubuntu） | `tests/` |

## Ticket 质量自检

- [x] 1. estimate ≤1d
- [x] 2. type 正确（HITL：含人工验证与停机窗口）
- [x] 3. AC 可测量并标注 auto/human-verify/decision
- [x] 4. 代码目录已指定
- [x] 5. 前置准备含具体备份路径
- [x] 6. mock/E2E 策略明确（docker stub + NAS 实机）
- [x] 7. 工具可用性已实测
- [x] 8. 验收无主观
- [x] 9. blocked_by 为空
- [x] 10. 架构约束引用最佳实践文档
- [x] 11. AC 覆盖集成层（AC5/AC7/AC8）
- [x] 12. Scope 边界清晰
- [x] 13. needs_* 已声明
- [x] 14. test_files 已指定
- [x] 15. 窗口预算 ≤40%
- [x] 16. safety 不适用
- [x] 17. 外部项目引用不适用
