---
name: claude-code-dual-config-hooks-sync
description: settings.json+settings.local.json 双配置文件 hooks 段必须手动同步
created: 2026-07-29
source: offline-scan
origin_session: 4ff993d7-6deb-4edd-9593-7024b43584a2
---

settings.local.json 和 settings.json 各自独立的 hooks 注册段。部署新 hook 后只改了 settings.json（指向 claude-config 仓库的软链），settings.local.json 的 hooks 段未同步更新，导致 session-start/pre-compact/stop 钩子部署后不生效。

**根因：** settings.local.json 是 Claude 个人覆盖配置，hooks 段独立于 settings.json。两者 hooks 段需各自维护，无自动同步机制。

**预防：** 部署 hooks 时两步确认：(1) ~/.claude/settings.json 的 hooks 注册完毕；(2) ~/.claude/settings.local.json 的 hooks 段也同步更新。验证环节追加 `jq '.hooks'` 同时检查两文件。

