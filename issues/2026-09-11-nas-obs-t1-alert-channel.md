---
type: HITL
estimate: 0.5d
effort: small
status: backlog
blocked_by: ["2026-09-11-nas-obs-t2"]
needs_llm: false
needs_vision: false
needs_pdf: false
needs_docker: true
test_files:
  - tests/integration/health_check_selftest.sh
safety: ""
---

# T1 巡检告警出口：异常能通知到人

## 背景

阶段一让巡检"看得见自己"（心跳行、失败计数、重启锁），但异常**只写 NAS 本地日志**——今天的 QQ 掉线 2 天无人知，正是这个缺口。T2 的结论决定告警内容与阈值。

## 方案（已定，用户 2026-09-11 批准）

- **NAS 侧零网络依赖**：巡检在「发生重启 / `ACCOUNT-OFFLINE` / 前置条件连续 SKIP」时写 `/volume1/docker/langbot/state/alert`（一行事件：时间戳、类型、probe、link、restart）；正常轮次不写；同一原因 **1 小时内去重**（防止每 5 分钟刷屏）
- **出口集中在开发机**：新增 `nas/fetch-alerts.sh`（ssh 读取 → 若存在则上报 → 清空为 `state/alert.sent`），异常经仓库现有 `scripts/notify.py`（Telegram）推送；与 T5 的看门狗 cron 共用调度

## Acceptance Criteria

- [ ] `[auto]` AC1: 巡检在重启发生时写 `state/alert`（自测新增用例覆盖）
- [ ] `[auto]` AC2: `ACCOUNT-OFFLINE` 与前置条件 SKIP 触发写 alert；同原因 1 小时内去重（自测断言）
- [ ] `[auto]` AC3: 正常轮次**不写** alert（自测断言）
- [ ] `[human-verify]` AC4: `nas/fetch-alerts.sh` 在 ssh 失败/断网时不丢数据（alert 仍留 NAS，不清空）
- [ ] `[human-verify]` AC5: `scripts/notify.py` 通道实测可达；不可达时降级为开发机日志 + 醒目文件，且降级本身可见
- [ ] `[human-verify]` AC6: 端到端演练——用 `HC_FORCE_FAIL` 造一次真实重启，开发机确实收到通知

## Scope

**In:** 巡检写 alert、开发机抓取脚本、通知出口、去重、降级。
**Out:** 告警平台化（不做）、n8n 流程（不采用）、改巡检探针语义。

## 风险

- 风险1: 自己也在重启容器，演练会再造成 1.5–3 分钟中断 — 缓解: 低活跃时段，且沿用已验证的重启序列
- 风险2: 通知渠道不可用导致"以为有告警" — 缓解: AC5 强制实测 + 降级可见
- 回退: `git revert` + 删除 NAS 侧 alert 文件

---

## 设计修订（2026-09-11，由 T2 结论驱动）

T2 查明：**掉线期间 OneBot WS 一直连着**（9/9 17:39 → 9/10 17:56 期间 0 条 WS 错误），因此阶段一的 `link` 探针存在**假健康窗口**。T1 必须补两条"登录态"探测，与既有 `link` 并列：

| 类型 | 实现 | 覆盖 | 代价 |
|---|---|---|---|
| **状态探针** | napcat 内 `curl -m5 http://127.0.0.1:3000/get_status` → 须 200 且 `online:true` | "持续掉线"（含被置离线但进程存活） | 1 次 docker exec |
| **日志事件扫描** | napcat 日志 5 分钟窗口匹配 `账号状态变更为离线\|请扫描下面的二维码\|用户身份已失效\|快速登录错误` | "掉线瞬间"（能在 09-09 17:42 就报出，早 42 小时） | 1 次 docker logs（复用既有扫描模式） |

**两者都只写 alert，不计入重启阈值**（重启对账号掉线无效，T9 才是处置手段）。

### 追加 AC

- [ ] `[auto]` AC7: 状态探针在 `online:false`/拒连时写 `alert: qq-offline`，且**不**增加失败计数、不触发重启（自测覆盖）
- [ ] `[auto]` AC8: 日志事件扫描命中任一模式即写 `alert: qq-offline`；正常日志不写（自测覆盖）
- [ ] `[human-verify]` AC9: 与 `link` 探针的关系写进 `nas-access-best-practices.md` §十二（说明各自的覆盖边界与"link=1 不等于已登录"）
