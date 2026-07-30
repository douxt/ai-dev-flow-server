---
name: wsl-tmp-not-persistent
description: WSL 重启后 /tmp 清空，持久状态文件不能放 /tmp
created: 2026-07-18
source: offline-scan
origin_session: dfa6089a-1cfa-410b-b935-2f9ca706fa7f
---

**根因**：SessionStart resume 注入依赖的状态文件放 /tmp，WSL 重启后 /tmp 清空（内核行为无例外），注入无声降级为"只有提醒行，压缩前任务状态丢失"。

**解决**：持久状态统一放 `~/.claude/mem-state/`，通过 `$HOME/.claude` 路径抗重启。

**预防**：
- 任何 Claude Code hook 的状态文件（水位线、任务状态、计数）永远不要放 `/tmp` 或 `/dev/shm`
- 设计时就按"机器随时重启、文件随时丢"做 fallback
- WSL 环境下 `/tmp` 不抗重启这个坑迟早会踩，直接定规矩省事

