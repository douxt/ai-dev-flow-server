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

---

## 执行结果（2026-09-11）

### ⚠️ 架构修正：出口不是开发机，而是阿里云服务器

原设计假设"开发机 cron → `scripts/notify.py` → Telegram"。实测推翻：

| 位置 | 到 Telegram |
|---|---|
| 开发机 | `code=000`（国内网络，baidu=200 但 telegram/github 不通） |
| NAS | `code=000`，google 超时 → **基本无外网** |
| **阿里云 115.29.110.107** | ✅ 有 `telegram-bot.service`（凭据 `/opt/maf-hub/config/telegram.json`，经 Tailscale 上的 Clash 代理 `100.83.141.78:7890` 出海） |

**最终链路**：

```
NAS 巡检（零外网，只写 state/alert）
   ↑ 每 5 分钟 ssh 拉取（走 Tailscale，9–22ms）
阿里云 /usr/local/bin/nas-fetch-alerts.sh → nas-alert-send.py → Telegram
```

新增凭据关系：云服务器公钥（`maf-hub-server`）加入 NAS `authorized_keys`（反向拉取用；NAS 不新增出网依赖，符合 D2 原意）。

### 交付物

| 文件 | 位置 | 说明 |
|---|---|---|
| `nas/health-check.sh`（v2） | NAS `/volume1/docker/langbot/health-check.sh`（md5 `7a9b5bc9ea35811510025a3d72f66f16`） | 新增登录态双探测 + `state/alert`（1h 去重）+ 连续 SKIP 告警 |
| `nas/cloud/nas-fetch-alerts.sh` | 云 `/usr/local/bin/nas-fetch-alerts.sh` | 拉取 → 推送 → **成功后**才归档（失败留在 NAS 重试，不丢数据） |
| `nas/cloud/nas-alert-send.py` | 云 `/usr/local/bin/nas-alert-send.py` | 复用 `telegram.json` 凭据与代理（不复制 token） |
| 云 crontab | `*/5 * * * * flock -n /tmp/nas-fetch-alerts.lock …` | 已安装 |

### AC 验证

- [x] `[auto]` AC1: 重启时写 `state/alert`（自测 T11 + 真机演练）
- [x] `[auto]` AC2/AC3: `qq-offline`（状态探针/事件扫描）与 `skip` 告警（自测 T12/T13/T16）；正常轮次不写（T14）
- [x] `[auto]` AC7/AC8: 登录态双探测，**均不计入重启阈值**（自测 T12 断言探针仍 `probe=11111`、无 restart 调用）
- [x] `[human-verify]` AC4: ssh 失败/发送失败时不归档、不丢数据（脚本逻辑 + 云日志 `send failed, alert kept pending on NAS`）
- [x] `[human-verify]` AC5: 通道实测可达（云侧 `sent`，退出码 0；两次真实消息已发出，待用户确认收到）
- [x] `[human-verify]` AC6: 端到端演练 —— 真机强制失败 ×3 → 31 秒完成重启 → `state/alert` 写入 → 云侧 `sent 1 alert line(s)` → NAS 侧 `alert` 归档为 `alert.history`；恢复后 `health=healthy / link=1 / qq online`
- [ ] `[human-verify]` AC9: 文档更新（本次提交完成）

---

## 收官确认（2026-09-11）

- [x] `[human-verify]` AC5 补记：**用户确认 Telegram 已收到消息** → Cloud → Clash 代理（Tailscale `100.83.141.78:7890`）→ Telegram 链路正式可用
- [x] `[human-verify]` AC9: 文档已更新（`nas-access-best-practices.md` §十二·补、`automated-testing-guide.md`、`skills/nas-ops`）

---

## 架构再修订（2026-09-11，用户要求：NAS 自洽、不牵扯阿里云）

发现 NAS 经**局域网网关上的 Clash 代理**（`192.168.31.1:7890`）可直连 Telegram（`getMe → ok:true`），故发送端也搬回 NAS：

| 环节 | 现状 |
|---|---|
| 生产（health-check / selfcheck / deep-smoke） | 写 `state/alert`（不变） |
| 投递 | **NAS** `alert-flush.sh`（cron `*/2`）→ 网关代理 → Telegram；原子认领队列，失败回队重试 |
| 每日摘要 | **NAS** `daily-digest.sh`（cron `0 9`）——死者开关 |
| 凭据 | NAS `state/telegram.conf`（600） |
| 阿里云 | **已完全移除**：cron 条目、脚本、NAS 上的公钥（实测云→NAS `Permission denied`） |

验证：注入测试告警 → `sent=1 failed=0`、队列清空、`alert.history` 留痕；日报 `rc=0`；自检 `drift=0`（清单 11 项）。
