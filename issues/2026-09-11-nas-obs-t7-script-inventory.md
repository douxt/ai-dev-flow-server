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

# T7 NAS 在版脚本清点入库

## 背景

2026-09-11 发现 `/volume1/docker/langbot/health-check.sh` 在版版本（3410B/83 行）与仓库（1486B/46 行）完全不同，"照仓库修 = 修的不是线上那份"。同类风险还存在于其他自建脚本。

## 清点范围

- `/usr/local/bin/*`（自定义脚本；已知 `clean-zombie-ssh.sh` 已入库）
- `/volume1/docker/*/` 下的脚本与 `entrypoint.sh`（含 `patches/`）
- `/etc/crontab` 引用的所有可执行项（逐条判定归属：系统自带 / 自建 / 第三方）
- 宿主上运行的自建 systemd/任务计划脚本（如有）

## Acceptance Criteria

- [ ] `[human-verify]` AC1: 产出一张清单表（路径、md5、mtime、归属判定、是否入库、理由），覆盖 crontab 引用项 **100%**
- [ ] `[human-verify]` AC2: 判定为"自建且未入库"的脚本全部回灌到仓库（`nas/` 或对应目录）并更新 `nas/README.md` 基线表
- [ ] `[auto]` AC3: `bash nas/check-drift.sh` 对新增入库项通过（或明确标注为"不参与对账"并写明理由）

## Scope

**In:** 只读清点 + 回灌入库 + 基线表更新。
**Out:** 重构/合并既有脚本、修改系统自带项。

## 风险

- 风险1: 误把系统文件当自建脚本入库造成噪音 — 缓解: 归属判定需给证据（包管理/DSM 路径/内容特征）
- 回退: `git revert`

---

## 执行结果（2026-09-11）

清单：`nas/INVENTORY.md`（分类：已入库的 7 项 / 系统文件 / 与本仓库无关的个人基础设施）。

**新发现并回灌**：`/volume1/docker/langbot/plugin-entrypoint.sh`（978B，2026-08-01，"等 LangBot 就绪再起插件运行时"）此前**未入库** → 已回灌为 `docker/langbot/plugin-entrypoint.sh`。
好消息：`entrypoint.sh` 仓库与线上**逐字节一致**（`3730cebb…`），ADR 010 的纪律守住了。

**对账范围扩展**：`nas/check-drift.sh` 从 3 项 → **7 项**（补 entrypoint、plugin-entrypoint、deep-smoke.sh、deep-canary.py），并在文件不在 `main` 时回退工作区并标注来源——顺带修掉一个自身 bug（`git show` 失败会得到空内容的 md5 `d41d8cd9…` 而被误判成漂移）。

**crontab 引用项覆盖 100%**：`clean-zombie-ssh.sh`、`health-check.sh`、`deep-smoke.sh`（自建，已入库）+ `powersched`、`synoschedtask`（DSM 系统二进制）。

### AC 验证

- [x] `[human-verify]` AC1: 清单表覆盖 crontab 引用项 100%（5/5），并给出归属判定依据（符号链接目标 = DSM 包）
- [x] `[human-verify]` AC2: 「自建且未入库」项已全部回灌（本次 1 项：plugin-entrypoint.sh）；`nas/README.md`/`INVENTORY.md` 记录 md5
- [x] `[auto]` AC3: `bash nas/check-drift.sh` 对新增入库项**全部通过（7/7 OK）**
