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

---

## 调查结果（2026-09-11）

### 事实

| 项 | 实测 |
|---|---|
| `onebot11_3228649756.json` | `httpServers: [{enable:true, name:"test-api", url:"0.0.0.0:5700", token:…}]`（mtime 2026-07-14） |
| 配置里是否出现 3000 | **没有任何配置文件提到 3000**（镜像内仅 `node_modules/mime-db/db.json` 命中，无关） |
| `napcat_protocol_3228649756.json` | `{"enable": false, …}` → 未启用 |
| 容器实际监听 | `127.0.0.1:3000`（仅登录后）+ `0.0.0.0:6099`(WebUI)，**5700 无监听** |
| compose（`/volume1/docker/langbot/docker-compose.yaml:59`） | `ports: 6099:6099, 5700:5700`；`environment: ACCOUNT=3228649756, WSR_ENABLE=true, WS_URLS=["ws://langbot:2280/ws"], WEBUI_TOKEN=…`；volume `./data/napcat/config:/app/napcat/config` |
| 宿主 `:5700` | docker-proxy 在听 → 容器内无后端 → `Connection reset by peer` |
| 宿主 `:3000` | **nginx**（另一服务），与 napcat 无关 |

### 结论（漂移成因）

反向 WS 与账号是通过**环境变量**（`WS_URLS` / `ACCOUNT`）配置的，而 OneBot **HTTP 服务**走 JSON 配置。JSON 里的 `"url": "0.0.0.0:5700"` 是旧写法；当前 NapCat 4.18.1 下它没有生效，HTTP 服务实际落在 `127.0.0.1:3000`。也就是说：**配置文件字段与实际运行行为不一致**（不是"文档写错"，是"配置不生效"）。

### 建议（待决策）

- **方案 B（推荐，零风险）**：承认现实并统一记录——文档/脚本一律写"容器内 `127.0.0.1:3000`（登录后才有）"；compose 的 `5700:5700` 保持不动或加注释标注"当前无后端"。不动 napcat 配置 → 不会碰掉线风险。
- **方案 A（改动配置）**：把 HTTP 服务修成期望形态（需先确认 4.18.1 的正确字段/环境变量写法），改动后重启 napcat 验证 `get_status` 与 `link=1`。**风险**：napcat 配置改动可能触发掉线（T2 已证明掉线要人工扫码），必须留维护窗口且先备份配置。

**推荐 B**：当前没有任何调用方依赖宿主 `:5700`（金丝雀与巡检都走容器内 3000），修配置的收益为零、风险非零。

### AC 状态

- [x] `[human-verify]` AC1: 生效配置来源与证据已给出（env 驱动 WS + JSON 字段不生效 → 实际 3000）
- [ ] `[human-verify]` AC2: **需你选 A/B**（我按 B 先写文档；选 A 我再排维护窗口）
- [x] `[human-verify]` AC3: 未改配置 → `get_login_info` / `link=1` 均未受影响（巡检 `probe=11111 link=1 qq=1`）
