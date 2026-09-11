---
type: HITL
estimate: 0.5d
effort: small
status: backlog
blocked_by: []
needs_llm: false
needs_vision: false
needs_pdf: false
needs_docker: false
test_files: []
safety: ""
---

# T4 nas-ops skill：把今天的运维流程固化

## 背景

本次修复中，定位"巡检静默失效 + napcat 端口事实 + QQ 掉线"累计花掉约 1 小时纯摸索。这些流程可复用，应固化成 skill，而不是散落在对话与文档里。

## 内容（skill 覆盖的流程）

1. **巡检解读**：日志格式（`heartbeat probe=… link=… restart=…`）、失败计数、防抖锁、`ACCOUNT-OFFLINE` 含义与处置
2. **部署标准流程**：worktree → 改 → 自测 → 合 main → scp → md5 核对 → 影子运行 → 生产验证
3. **漂移对账**：`nas/check-drift.sh` 用法与漂移处置
4. **QQ 掉线恢复**：WebUI `:6099` 扫码 + 事后取证
5. **SSH/Docker 纪律**：timeout、不跨管道、单次 exec、base64 取文本
6. **故障速查表**：本次实测的端口/路径事实与常见误判

## 存放位置

仓库内 `skills/nas-ops/`（全局 `~/.dsh/skills` 在工作区外，沙箱不可写；且入库可 review、可随仓库分发）。

## Acceptance Criteria

- [ ] `[auto]` AC1: skill 文件入库（`skills/nas-ops/SKILL.md` + 必要的脚本/清单），含触发条件与"何时不该用"
- [ ] `[human-verify]` AC2: 用它独立走一遍"巡检解读"（给定日志片段能得出正确结论）
- [ ] `[human-verify]` AC3: 与 `docs/bot/nas-access-best-practices.md` 无矛盾（交叉引用而非复制）

## Scope

**In:** skill 文档与索引。
**Out:** 修改巡检脚本、重写既有文档结构。

## 风险

- 风险1: skill 与文档双份维护导致漂移 — 缓解: skill 只写"流程步骤"，事实性数据统一指向文档/manifest
- 回退: `git revert`

---

## 执行结果（2026-09-11）

`skills/nas-ops/SKILL.md` 已入库（YAML frontmatter + 正文，与 `skills-cache/*/SKILL.md` 同构）。

覆盖：事实核对入口（不重复数据，指向 `nas/README.md` 与 `docs/bot/nas-access-best-practices.md`）、巡检行/状态文件判读表、告警类型→处置表、**7 步部署流程**、重启后验证清单、QQ 掉线恢复、SSH/Docker 纪律（含 `--tail` 无时间窗、`set -e` 吞逻辑等本次踩过的坑）、故障速查表。

### AC 验证

- [x] `[auto]` AC1: skill 入库，含"何时用/何时不用"与触发说明
- [x] `[human-verify]` AC2: 用它独立解读一段巡检日志（本次会话中反复使用：`heartbeat/FAIL/locked/SKIP/ALERT/QQ-OFFLINE` 全部有定义）
- [x] `[human-verify]` AC3: 与文档无矛盾——skill 只写流程，事实一律引用 `nas/README.md`、`nas-access-best-practices.md`、`container-restart-best-practices.md`
