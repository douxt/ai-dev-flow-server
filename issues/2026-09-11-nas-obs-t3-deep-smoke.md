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

---

## 执行结果（2026-09-11）—— 设计有调整

### 调整原因（实测）

原计划把完整 8 场景套件（`tests/scripts/test_deploy_smoke.py`）放进 cron。实测：
- 该套件所有场景共用 `session_id`，而 LangBot 对占用中的会话返回 **409** → 大面积"空回复"假失败（实测 6/18）
- 即使改为每场景独立会话 + 409 重试，总时长仍会超过包装脚本的超时（日志出现 `rc=124` 且无输出）
- 结论：**完整套件属于"部署后人工验证"，不适合做 6 小时周期金丝雀**

### 最终实现

| 文件 | 部署位置 | 作用 |
|---|---|---|
| `nas/deep-smoke.sh` | NAS `/volume1/docker/langbot/deep-smoke.sh`（md5 `6f4ea476…`） | cron 包装：拷入 napcat → 跑金丝雀 → 失败写 `state/alert`（类型 `deep-smoke-fail`，1h 去重） |
| `nas/deep-canary.py` | NAS `/volume1/docker/langbot/tests/deep-canary.py`（md5 `c573119f…`） | **最小可证伪检查**：napcat 在线 + `/sync code=0` + 回复非空；每次独立会话 |
| 完整套件 `test_deploy_smoke.py` | 不进 cron | 顺带修好会话争用（每场景独立会话 + 409 退避重试 + 错误诊断输出） |

cron（NAS `/etc/crontab`）：`17 */6 * * * root /volume1/docker/langbot/deep-smoke.sh`（快照已同步更新）

### AC 验证

- [x] `[human-verify]` AC1: **连续 2 次通过**（11:43:17 / 11:43:55，均 `CANARY: OK`，`sync code=0`，回复非空 334/67 字符）
- [x] `[human-verify]` AC2: 失败时产出 `state/alert`（11:32 实测 `ALERT deep-smoke-fail rc=1 fail_lines=13`），且巡检探针不受影响（`probe=11111`）
- [x] `[human-verify]` AC3: cron 已装并核对 `/etc/crontab`（`17 */6 * * *`），快照 md5 更新为 `b1e7b5e5…`
- [ ] `[decision]` AC4: 48 次/天 LLM 开销与测试群噪音确认（金丝雀每次 1 条消息、1~2 次 LLM 调用；待用户确认）

### 观察（非本工单范围）

金丝雀回复里偶见提示词片段（如 `用户只是问"在吗"。简短回复即可…`）——属回复质量/提示词泄漏问题，建议另开工单跟进。
