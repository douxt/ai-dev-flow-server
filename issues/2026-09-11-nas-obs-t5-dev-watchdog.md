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
