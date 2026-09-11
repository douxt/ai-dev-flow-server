---
type: HITL
estimate: 0.5d
effort: small
status: backlog
blocked_by: ["2026-09-11-nas-obs-t1"]
needs_llm: true
needs_vision: false
needs_pdf: false
needs_docker: true
test_files:
  - docker/langbot/plugins/silent-observer/tests/scripts/test_deploy_smoke.py
safety: ""
---

# T3 深度链路低频冒烟（每 6 小时一次）

## 背景

阶段一把巡检探针改成"只证活着"（零 LLM），代价是丢失"业务能跑通"覆盖：KB/chroma 损坏、pipeline 配置错误、发不出消息都测不出。本工单用低频全链路补回该层：**每 6 小时一次 `/sync`（48 次/天，对比旧设计 288 次/天降 98%）**。

## 方案

- NAS cron：`17 */6 * * *` 运行深度冒烟（`tests/scripts/test_deploy_smoke.py`，8 场景，含 LLM + 检索）
- 结果落 `/tmp/deep_smoke.log`；失败写 `state/alert`（类型 `deep-smoke-fail`），**不影响巡检重启阈值**
- 被测会话固定，避免污染真实群（用测试群 `group_1104330614`）

## Acceptance Criteria

- [ ] `[human-verify]` AC1: 连续 2 次运行通过，记录单次耗时
- [ ] `[human-verify]` AC2: 失败时产出 `state/alert`，且巡检探针不受影响（心跳仍 `probe=11111`）
- [ ] `[human-verify]` AC3: cron 实测按 `17 */6 * * *` 触发（看日志时间戳）
- [ ] `[decision]` AC4: 48 次/天的 LLM 开销与测试群噪音可接受（由用户确认）

## Scope

**In:** 深度冒烟 cron 化、结果落盘、失败写 alert。
**Out:** 把深度冒烟放回 5 分钟巡检（明确不做）、改冒烟用例内容。

## 风险

- 风险1: 测试消息进测试群，可能被误当真实数据 — 缓解: 固定 session + 结论中说明
- 风险2: LLM 抖动导致误告警 — 缓解: 只写 alert、不触发重启；允许连续 2 次失败才告警
- 回退: 摘掉 crontab 行 + `git revert`
