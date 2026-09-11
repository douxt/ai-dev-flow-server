---
type: HITL
estimate: 0.5d
effort: small
status: backlog
blocked_by: ["2026-09-11-nas-obs-t1"]
needs_llm: false
needs_vision: false
needs_pdf: false
needs_docker: false
test_files: []
safety: ""
---

# T5 开发机看门狗 cron（漂移 + 告警抓取）

## 背景

阶段一交付了 `nas/check-drift.sh` 与（T1 的）`nas/fetch-alerts.sh`，但没有调度，等于没有看门狗——"静默失效"仍然只能靠人偶然发现。

## 方案

开发机每小时执行 `nas/watchdog.sh`：

1. `check-drift.sh`：NAS 在版脚本 vs main 分支 md5
2. `fetch-alerts.sh`：抓取 NAS 侧 `state/alert`
3. 汇总结果写 `~/.local/state/nas-watchdog.log`；异常经 `scripts/notify.py` 推送（与 T1 共用出口）
4. 静默原则：一切正常不产生输出/通知

## Acceptance Criteria

- [ ] `[auto]` AC1: `nas/watchdog.sh` 可重复运行、幂等、无副作用（重复跑不重复告警）
- [ ] `[human-verify]` AC2: 调度落地（crontab 或 systemd user timer），写明具体行；手动触发一次通过
- [ ] `[human-verify]` AC3: 人为制造漂移（本地改一个字节后不部署）→ 1 小时内收到告警；恢复后不再告警
- [ ] `[decision]` AC4: 若沙箱限制导致无法直接写 crontab，则由用户执行安装命令（提供成一行）

## Scope

**In:** watchdog 脚本 + 调度 + 静默/去重。
**Out:** NAS 侧新增守护进程（不做）、告警平台化。

## 风险

- 风险1: 告警疲劳（每次 ssh 抖动都报） — 缓解: 连续 2 次失败才告警；正常轮次静默
- 回退: 删除 cron 行 + `git revert`

---

## 执行结果（2026-09-11）

### 交付物

`nas/watchdog.sh`（开发机运行；形态按 T1 的架构修正调整）：

| 检查 | 方法 | 异常示例 |
|---|---|---|
| ① 漂移对账 | 复用 `nas/check-drift.sh`（NAS 在版 md5 vs 仓库 main） | `NAS 脚本漂移: DRIFT [cron 快照] /etc/crontab` |
| ② 巡检心跳新鲜度 | NAS `/tmp/health_check.log` 末次写入年龄 > 20 分钟 | `巡检心跳停止: 最后写入 N 分钟前` |
| ③ 待发告警积压 | NAS `state/alert` 非空（说明云侧拉取/推送失败） | `NAS 有待发告警 N 条` |

- 静默原则：全部正常时**不输出、不通知**（exit 0）
- 通知路径：开发机 → `ssh` 阿里云 → `nas-alert-send.py` → Telegram（开发机/NAS 均无 Telegram 通道）
- 去重：同签名 6 小时内只通知一次；发送失败不写去重状态（下次重试）
- 自检钩子：`WD_FORCE_PROBLEM=1`（仅手动，cron 不设置）

### AC 验证

- [x] `[auto]` AC1: 幂等、无副作用（重复运行结果一致；状态目录可覆盖，测试用 `/tmp/wd-*`）
- [x] `[human-verify]` AC3: **真实漂移演练** —— NAS `/etc/crontab` 追加一行注释 → md5 `0983f296…` → 看门狗 `NOTIFIED: NAS 脚本漂移` → 还原后 md5 回到 `968d2619…` → 看门狗 `OK`（静默）
- [x] `[human-verify]` AC1（通知链路）: `WD_FORCE_PROBLEM=1` → `NOTIFIED`；连跑第二次 → `SUPPRESSED（同类问题 0 分钟内已通知）`
- [ ] `[decision]` AC2: **调度需用户执行一行**（沙箱不允许写 crontab：`/var/spool/cron/: mkstemp: Permission denied`）：

```bash
( crontab -l 2>/dev/null; echo '0 * * * * /home/dou/dev/ai-dev-flow-server/nas/watchdog.sh' ) | crontab -
```

### 备注

- 看门狗日志/状态默认在 `~/.local/state/`（`WD_STATE_DIR` 可覆盖）
- 云侧两个脚本（`nas-fetch-alerts.sh` / `nas-alert-send.py`）尚未纳入 `check-drift.sh` 对账范围 → 见 T7/后续

---

## 架构修正（2026-09-11，用户指出开发机常关机）

**问题**：T5 把看门狗放在开发机，而开发机经常关机 → 24/7 覆盖实际不存在。

**修正后的拓扑**（检测在 24/7 的 NAS，发送在唯一有通道的云）：

| 职责 | 位置 | 频率 | 产物 |
|---|---|---|---|
| ① 巡检自身是否停跳（`health_check.log` 年龄） | **NAS** `nas/selfcheck.sh` | `*/15` | 写 `state/alert`（`selfcheck-heartbeat`） |
| ② 在版脚本是否被改动（对照 `state/expected.md5`，8 项） | **NAS** 同上 | `*/15` | 写 `state/alert`（`selfcheck-drift`） |
| ③ 待发告警积压 | **NAS** 同上（只记日志） | `*/15` | `nas_selfcheck.log` |
| 传输：把 `state/alert` 推 Telegram | **阿里云** `nas-fetch-alerts.sh` | `*/5` | Telegram |
| 死者开关：每日摘要（收不到=链路坏） | **阿里云** `nas-daily-digest.sh` | `0 9 * * *` | Telegram |
| 仓库 `main` ↔ NAS 全量比对 + 自测 | 开发机 `nas/watchdog.sh`（**降级为可选**，仅在开机时补全量视角） | 每小时 | Telegram |

清单单一来源：`nas/manifest.tsv` → `nas/make-manifest.sh` 生成 `expected.md5` 并部署到 NAS；
`nas/check-drift.sh` 也改读同一份 tsv（消除两处维护）。

### 验证（NAS 实测）

- 影子①：清单里故意写错一条 md5 → `ALERT selfcheck-drift count=1 changed:/volume1/docker/langbot/health-check.sh`（rc=1）
- 影子②：清单正确 → rc=0、无告警
- 生产：rc=0，`heartbeat hb_age_s=… drift=0 pending=0 problems=0`，`state/alert` 为空
- 云日报手动试跑：`digest sent (hb_age=219 sc_age=8 pend=0)`（用户已收到 Telegram）

### 已知限制

- 自检脚本自身也在清单里（8 项），但**清单与脚本同时在 NAS** → 若两者被一致地篡改则无法发现；跨机校验仍以开发机 `check-drift.sh` 为准
- 云侧两个脚本（`nas-fetch-alerts.sh` / `nas-alert-send.py` / `nas-daily-digest.sh`）目前无仓库对账（云上没有仓库）——其存活由"每日摘要是否收到"间接保证
