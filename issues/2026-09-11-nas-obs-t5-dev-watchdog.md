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
