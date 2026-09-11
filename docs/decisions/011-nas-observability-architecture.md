# ADR-011: NAS 可观测性架构——检测在 24/7 主机、发送自洽、文件队列 + 死者开关

## 状态：已采纳

## 日期：2026-09-11

## 背景

2026-09-11 排查发现三件事同时"静默"发生，且**都不是被监控发现的**，而是人工上机偶然撞见：

| 事实 | 持续时长 | 发现方式 |
|---|---|---|
| `health-check.sh` 自愈逻辑完全失效（`set -e` 吞掉失败计数 + 探测文件路径失效） | **30+ 天** | 取证时读到日志异常 |
| QQ 账号掉线、Bot 停止工作（会话失效，需人工扫码） | **约 2 天** | 探针上机实测撞见二维码循环 |
| 仓库与 NAS 在版脚本完全不同（3410B vs 1486B） | ≥1 个月 | 同上 |

共同的根因是**没有任何机制把异常告诉人**。修复过程中又暴露三条环境事实，直接决定架构：

1. **NAS 基本无外网**：直连 `api.telegram.org` 与 google 均不可达；
2. **开发机经常关机**（被监控者比监控者更可靠）→ 把看门狗放开发机不成立；
3. **网关（iStoreOS）上有 Clash 代理且从 NAS 可用**（`192.168.31.1:7890`，实测 `getMe → ok:true`）；而云服务器发 Telegram 走的**正是同一个代理**——所以"NAS → 云 → Telegram"不提供冗余，只是多一跳。
4. 另有一条判据性发现：QQ 掉线期间 **OneBot WS 一直连着**（0 条 WS 错误），故"链路通"不能代表"已登录"。

## 决策

1. **执行者位置：检测与发送全部落在 24/7 的 NAS**，不引入第三方主机。判定顺序是"这台机器 24/7 吗"优先于"这台机器有什么"。需要外网时经网关 Clash 代理（HTTP 7890 / SOCKS 7891）。
2. **故障分类决定动作**，三类不得混用一个失败计数：
   - 可自愈（进程死/端口不通/healthcheck 失败）→ 计入阈值并**按序重启**（`plugin → langbot → 等端口就绪 → napcat`，每条 docker 命令带 `timeout`）；
   - 需人工（账号掉线/风控）→ **只告警不重启**（重启无效），单列 `qq-offline`/`ACCOUNT-OFFLINE`；
   - 需告警但别动（LLM/检索抖动）→ 低频金丝雀只告警，不进重启阈值。
3. **探针不得使用真实业务链路**。巡检只证"活着"（插件心跳文件年龄、端口、healthcheck、HTTP 200、进程存活）；业务链路验证改为**每 6 小时一次最小金丝雀**（`/sync` 一次 + 回复非空），比原设计 288 次/天降 98%。
4. **登录态用双通道交叉判定**：状态探针（登录后才存在的 API/文件）+ 日志事件扫描（`账号状态变更为离线|请扫描下面的二维码|你的用户身份已失效|快速登录错误`），带**时间窗**（`--since 5m --tail N`；单独 `--tail` 会横跨约 25 小时 → 永久误重启）。
5. **告警用文件队列做生产者/消费者接口**：生产者（巡检/自检/金丝雀/开发机看门狗）只写 `state/alert`，零网络依赖；消费者 `alert-flush.sh`（`*/2`）**原子认领**（`mv` → `.sending`）→ 经代理发 Telegram → 成功归档 `alert.history`，失败**回队重试**（不丢数据）。同类告警 1 小时去重。
6. **死者开关**：NAS 每日 09:00 发摘要（心跳年龄/待发条数/最近告警）。**收不到摘要即为信号**——NAS 是唯一执行者时，这是暴露整机或通道故障的唯一手段（该代价经确认接受）。
7. **漂移防护采用"清单 + 双机视角"**：
   - 单一来源 `nas/manifest.tsv` → `make-manifest.sh` 生成 `state/expected.md5`（随部署下发）→ NAS `selfcheck.sh`（`*/15`）本地比对，可发现"在版被改动"；
   - 跨机 `nas/check-drift.sh` 用仓库 `main` 兜底（开发机开机时），并可检出"清单与脚本被一致篡改"。
8. **凭据只落 NAS**：`state/telegram.conf`（`chmod 600`），仓库仅存模板 `nas/telegram.conf.example`；不因告警功能把第三方主机密钥关系引入 NAS（已移除此前为云拉取添加的 `authorized_keys` 条目）。

## 后果

**收益**
- 单一执行者、无跨机跳数与密钥关系；告警延迟从 ≤5 分钟降到 ≤2 分钟；
- 三类故障各走各的路径，消除"假故障触发重启"；
- 静默失效被两层覆盖：`selfcheck`（巡检自身停跳 / 在版漂移）+ 每日摘要（通道级）。

**代价与已知限制（明示）**
- NAS 整机宕机时不会有任何通知（缺日报即信号）——为"NAS 自洽优先"付出的代价；
- `expected.md5` 与脚本同在 NAS：若两者被一致篡改则本地比对失效，需靠开发机 `check-drift.sh` 兜底；
- 凭据（代理 + bot token）落在 NAS 上；
- 云侧脚本已删除（保留于 git 历史），如未来需要异地观察者，应重新设计而非复用旧脚本。

## 相关文件

| 类别 | 位置 |
|---|---|
| 执行者（NAS crontab） | `*/5` health-check ｜ `*/15` selfcheck ｜ `*/2` alert-flush ｜ `17 */6` deep-smoke ｜ `0 9` daily-digest |
| 仓库镜像 | `nas/health-check.sh`、`nas/selfcheck.sh`、`nas/alert-flush.sh`、`nas/lib-telegram.sh`、`nas/deep-smoke.sh`、`nas/deep-canary.py`、`nas/daily-digest.sh`、`nas/check-drift.sh`、`nas/manifest.tsv`、`nas/make-manifest.sh` |
| 计划与工单 | `docs/plans/2026-09-11-nas-health-check-repair.md`、`docs/plans/2026-09-11-nas-observability-hardening.md`、`issues/2026-09-11-nas-obs-t1..t9-*.md` |
| 流程固化 | `skills/nas-ops/SKILL.md` |
| 教训 | `memory/nas-observability-lessons-20260911.md` |
| 运维手册 | `docs/bot/nas-access-best-practices.md` §一/§十二 |
