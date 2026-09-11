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
test_files: []
safety: "auth"
---

# T9 QQ 掉线自动重登（回退密码登录）决策与落地

## 背景

T2 查明：QQ 会话失效后（2026-09-10 17:56 "你的用户身份已失效"），NapCat 的**快速登录失败**，只能人工扫码，导致 Bot 掉线 ~2 天。NapCat 日志自身给出的建议：

> `QQ 3228649756 未配置回退密码环境变量，建议优先使用 ACCOUNT + NAPCAT_QUICK_PASSWORD（NAPCAT_QUICK_PASSWORD_MD5 作为备用），将使用二维码`

即：配置账号 + 密码后，会话失效时 NapCat 可**自动重新登录**，无需人工介入。

## 需要你决策

| 选项 | 效果 | 代价/风险 |
|---|---|---|
| A. 配置 `ACCOUNT` + `NAPCAT_QUICK_PASSWORD`（明文） | 掉线可自动恢复 | QQ 密码明文进容器环境变量（`docker inspect` 可见） |
| B. 配置 `NAPCAT_QUICK_PASSWORD_MD5` | 同上，容器环境里只有摘要 | 仍属凭据落盘；需确认 NapCat 对该字段的校验方式 |
| C. 不配置，只靠 T1 告警 + 人工扫码 | 无凭据风险 | 每次会话失效都要人工介入（预计约 7 天一次，见 T2） |

## Acceptance Criteria

- [ ] `[decision]` AC1: 明确选 A / B / C，并记录理由
- [ ] `[human-verify]` AC2: 若选 A/B —— 配置落地（compose 环境变量或 napcat 配置），重启 napcat 后 `get_login_info` 实测通过、`link=1`、能收发消息
- [ ] `[human-verify]` AC3: 若选 A/B —— 演练一次"会话失效 → 自动重登"路径（可通过删除会话缓存/`docker restart napcat` 观察是否走密码回退而非二维码）
- [ ] `[human-verify]` AC4: 若选 C —— 在 `nas-access-best-practices.md` 写明"预计每约 7 天可能需扫码"与扫码入口（WebUI `:6099`）

## Scope

**In:** 决策 + 配置落地 + 演练 + 文档。
**Out:** 改 NapCat 版本、更换 QQ 账号、接入第三方登录网关。

## 风险

- 风险1: 密码进环境变量泄露（`docker inspect`、日志） — 缓解: 优先 B（MD5）；或把 compose 文件权限收紧
- 风险2: QQ 侧仍要求验证（风控/滑块），密码回退也可能失败 — 缓解: 保留 T1 告警作为兜底；AC3 演练验证真实有效性
- 回退: 删除环境变量并重启容器，恢复"扫码登录"模式
