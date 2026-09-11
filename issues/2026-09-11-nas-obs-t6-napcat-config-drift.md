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

# T6 napcat 配置漂移：声称 0.0.0.0:5700，实际仅容器内 127.0.0.1:3000

## 背景

实测（2026-09-11）：

| 位置 | 事实 |
|---|---|
| 容器内 `127.0.0.1:3000` | NapCat OneBot v11 API 正常（`app_name=NapCat.Onebot` v4.18.1），**仅登录后监听** |
| 宿主 `:3000` | **nginx**（另一服务） |
| 宿主 `:5700` | docker-proxy 在听但容器内无后端 → `Connection reset by peer` |
| 配置 `onebot11_3228649756.json` | `"url": "0.0.0.0:5700"` —— **与实际不符** |

## 调查

- [ ] 确认哪个配置真正生效（`onebot11_*.json` / `napcat_protocol_*.json` / `napcat.json` / WebUI 托管状态）
- [ ] 为何 5700 未监听：配置未加载？被 WebUI 覆盖？端口被占？版本行为变更？
- [ ] 盘点调用方：谁在从宿主/其他容器访问 napcat HTTP API（文档、alias、脚本、CI）

## 决策（二选一，需用户确认）

- **A. 修配置**：让 `httpServers` 与期望一致（如容器内 3000 + 宿主发布端口对齐），改动后用 `get_status` 实测
- **B. 统一到实际**：不改配置，改文档/脚本，明确"API 仅在容器内 127.0.0.1:3000 可用（登录后）"

## Acceptance Criteria

- [ ] `[human-verify]` AC1: 给出生效配置来源与证据（含"为何漂移"的解释）
- [ ] `[human-verify]` AC2: 产出 A/B 结论并落地（配置改动或文档统一，二选一，不两头都动）
- [ ] `[human-verify]` AC3: 改动前后 `get_login_info` 均实测通过；不破坏 langbot WS 链路（`link=1`）

## Scope

**In:** 只读调查 + 一项落地（A 或 B）。
**Out:** 升级 NapCat 版本、改 langbot 侧配置。

## 风险

- 风险1: 改 napcat 网络配置导致 WS 断连 → Bot 掉线 — 缓解: 先备份配置、改后立即验证 `link=1` 与消息收发；低活跃时段
- 回退: 恢复配置备份 + `docker restart napcat`
