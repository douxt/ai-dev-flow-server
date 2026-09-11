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
test_files: []
safety: ""
---

# T2 QQ 掉线根因调查（2026-09-09 16:18 起离线约 2 天）

## 背景

2026-09-11 探针上机实测发现：napcat 每约 30 秒重新渲染登录二维码（近 6 小时 712 次、近 72 小时 1961 次），日志反复出现"账号状态变更为离线"；插件 `silent_gate.log` 最后事件停在 **2026-09-09 16:18:02** → Bot 掉线约 2 天无人发现，10:52 由人工扫码恢复。

本工单**只做只读取证**，产出根因假设与再次发生时的判定步骤；不改任何配置（配置改动属 T6）。

## 调查清单

- [ ] 定位离线起点：napcat 日志中"账号状态变更为离线"首次出现时间；同期是否有 `KickedOffline`/被踢/风控/登录状态 关键词
- [ ] 时间线对齐：容器启动（9/2，RestartCount=0）、宿主 uptime（36 天）、langbot/langbot-plugin 同期日志是否异常
- [ ] 排查宿主与网络侧：9/9 16:18 前后 NAS CPU/内存/网络是否异常（可查 dmesg、synolog 日志、Tailscale 状态）
- [ ] 检查会话持久化：`/app/napcat/cache`、`/app/napcat/config` 下会话文件时间戳是否被改写/清空
- [ ] 输出结论：被踢 / 风控 / 网络 / 版本问题 / 未知；若属周期性，给出可观测指标与阈值建议

## Acceptance Criteria

- [ ] `[human-verify]` AC1: 给出离线精确时间点 + 日志原文证据（用 base64 取回，避免 SSH 中间层污染）
- [ ] `[human-verify]` AC2: 给出至少一个**可证伪**的根因假设，并写明"若再次发生"的判定步骤
- [ ] `[auto]` AC3: 调查过程与结论写入本工单；若涉及操作变更，同步写入 `docs/bot/nas-access-best-practices.md`

## Scope

**In:** 只读取证、日志分析、结论与判定步骤。
**Out:** 修改 napcat 配置（T6）、加告警通道（T1）、改巡检脚本（阶段一已冻结）。

## 风险

- 风险1: napcat 日志随容器重启滚动，若再次重启可能丢证据 — 缓解: 先取回证据落盘再分析
- 回退: 只读工单，无回退需求
