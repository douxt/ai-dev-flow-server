---
name: nas-devflow-v3.2-upgrade
description: NAS code-server DevFlow v3.0→v3.2 全栈升级——skills/hooks/checklists/内存系统部署踩坑
metadata:
  type: feedback
  created: 2026-07-28
  source: manual-session
---

# NAS code-server DevFlow v3.2 升级全流程

## 背景

NAS code-server 容器内有 DevFlow v3.0（gate-1~6），需升级到 v3.2（grill→to-spec→to-tickets→implement），同时部署完整内存钩子系统。

## 关键踩坑

### 1. tar 打包软链陷阱

**根因**：`tar czf` 默认保留软链，不解引用。本地 `~/.claude/hooks/` 下的文件是指向 `claude-config/hooks/` 的软链，打包后传到 NAS 解压出来仍是软链，指向不存在的 `/home/dou/` 路径。

**解决**：`tar czhf`（`-h` = dereference）跟踪软链打包实际文件内容。

**预防**：打包前 `ls -la` 确认是否存在软链；跨机器部署一律用 `tar czhf`。

### 2. NAS volume 路径 vs 容器内路径

**根因**：NAS 宿主机上的 `/volume7/docker/codeserver/config/claude/` 对应容器内 `/home/coder/.config/claude/`。直接从 NAS 宿主机操作文件时容易混淆两套路径。软链目标必须用容器内路径（如 `/home/coder/project/claude-config/hooks/xxx.sh`），不能是 NAS 宿主机路径。

**解决**：文件拷贝用宿主机路径（`cp`），软链目标用容器内路径（`ln -sf /home/coder/...`）。

**预防**：操作前明确当前在哪一层（NAS 宿主机 vs 容器内）。容器内操作优先用 `docker exec`，避免路径混淆。

### 3. settings.json hooks 路径全部指向错误机器

**根因**：NAS 的 `settings.json` 是从 dou 本地机器直接拷贝的，hooks 路径全部指向 `/home/dou/.claude/...`，容器内这些路径不存在 → **所有 hook 都没在跑**。

**解决**：Python 脚本遍历 JSON 全部替换 `/home/dou/.claude/` → `/home/coder/.claude/`；移除容器中不存在的工具引用（rtk、claudeline）。

**预防**：跨环境部署配置模板时，路径必须用变量或安装脚本替换，不能硬编码用户 home 路径。

### 4. settings.json 是软链到 claude-config

**根因**：`~/.claude/settings.json` → `claude-config/settings.json`。通过 Python 写入时是 transparent 的（自动 follow symlink），但如果用 `cp` 替换会断开软链变成普通文件。

**预防**：部署前先 `ls -la` 确认目标是否为软链；如软链指向 git 仓库，修改后记得 git commit。

### 5. Docker USER + NAS 宿主机文件权限

**根因**：容器以 `USER coder`（UID 1000）运行。NAS root 宿主机拷贝的文件默认 owner 为 root:root，容器内 coder 无法读取。

**解决**：`chown 1000:1000` 后再在容器内操作。

**预防**：NAS 宿主机部署文件到 volume 后，先 chown 再进容器操作。

### 6. git merge --allow-unrelated-histories

**根因**：容器内新 init 的 claude-memories 仓库与 gitee 远端有完全独立的历史，`git pull` 和 `git merge` 都会拒绝合并。

**解决**：`git merge gitee/master --allow-unrelated-histories`，冲突文件用 `git checkout --theirs` 保留远端版本后 commit。

**预防**：容器初始化已有远端仓库时，应 `git clone` 而非 `git init` + `git remote add`。如已 init，需 `git fetch + merge --allow-unrelated-histories`。

### 7. DEVFLOW v3.0→v3.2 组件对照

| 组件 | v3.0 | v3.2 | 迁移方式 |
|------|------|------|---------|
| Skills | gate-1~6 | grill-with-docs/to-spec/to-tickets/implement/tdd/code-review | 新增 6 个，旧版保留 |
| Checklists | gate-*-*.md | *-checklist.md | 删除旧的，替换新的 |
| CLAUDE.md | 65 行无路由 | 178 行含工作流路由表 | 替换 + 合并旧版独有段 |
| Hooks | 6 个 | +4（workflow-gate/stage-tracker/suggest-rules/block-git-worktree）| 新增，注册到 settings |

## 部署检查清单

- [ ] `tar czhf` 打包（含软链用 -h）
- [ ] 确认目标路径是宿主机路径还是容器内路径
- [ ] 软链目标用容器内路径
- [ ] NAS 宿主机文件 chown 1000:1000
- [ ] settings.json hooks 路径全部指向当前环境有效路径
- [ ] 新增 hook 文件 `bash -n` 语法校验
- [ ] settings.json 中注册新 hook 事件（PreCompact/Stop/SessionStart）
- [ ] git commit claude-config 所有变更
- [ ] 内存系统 SSH key + git remote + push 测试
- [ ] 旧 CLAUDE.md 独有段（踩坑自省/CodeGraph/工具使用）合并到新模板
