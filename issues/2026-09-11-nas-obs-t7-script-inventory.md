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
