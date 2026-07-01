---
name: pipeline-deploy-lessons
description: openlobby pipeline 部署踩坑 — cp 静默失败 / worktree 脏状态 / 部署需commit / Bash节点变量隔离 / dispatch死循环根因链 / root属主阻塞 / stash pop冲突 / 锁竞态 / 旧版install缺文件
metadata: 
  node_type: memory
  type: feedback
  originSessionId: cb30a46c-7f44-477d-be6a-5bd9d7d9659f
---

## 根因 → 解决方法 → 预防

### 1. cp -fv 静默失败
- **根因**：cp 报告成功但目标文件未替换（可能 FS 缓存或路径重定向）
- **解决**：部署后 md5sum 双向验证
- **预防**：每次 cp 后立即 md5sum src dst

### 2. Archon worktree 脏状态阻断 git pull
- **根因**：LLM 实现节点留未提交文件，`git pull --rebase` 失败
- **解决**：bash 节点 push 前加 `git stash` → pull/push → `git stash pop`
- **预防**：所有涉及 git 操作的 YAML bash 节点必须加 stash

### 3. 部署文件必须 commit 到仓库
- **根因**：Archon worktree 从 main **committed** 状态分支，cp 改工作区不生效
- **解决**：cp 后立即 `git commit --no-verify` + `git push`
- **预防**：部署检查清单含 commit 步骤

### 4. Bash 节点变量跨节点不共享
- **根因**：Archon 每个 bash 节点独立 shell（类似 GHA steps）
- **解决**：每个节点单独定义 `BRANCH=$(git rev-parse --abbrev-ref HEAD)`
- **预防**：review YAML 时确认变量在每个节点都有定义

### 5. dispatch 死循环根因链
- **根因**：archon_output.log 不存在 → PR_URL 空 → auto-merge skip → in_review push 失败 → 孤儿误判 → ready → 重新 dispatch
- **关键特征**：多条小 bug 串联，单独看每条都不致命，组合成死循环
- **预防**：排查时沿完整数据流追踪，不能只看单节点

### 6. SSH 操作留 root 属主文件阻塞 git
- **根因**：SSH root 登录后新建文件/目录默认属主 root:root，www 用户（dispatch/Agent B）无法写入
- **现象**：git commit/push 被拒，dispatch 日志报 FATAL
- **解决**：`chown -R www:www` 修复受影响路径
- **预防**：服务器上任何新建文件/目录操作后立即 `chown www:www`；优先 `sudo -u www` 执行

### 7. 配置更新导致 dirty working tree 阻塞管线
- **根因**：在服务器上直接修改 git 跟踪的配置文件（CLAUDE.md、AGENTS.md），未提交 → working tree dirty → dispatch.sh 的 `git checkout main` 失败 → 管线停摆
- **现象**：dispatch 日志 `FATAL: 无法切回 main`，持续到提交为止
- **解决**：改完立刻 `git add + git commit + git push`
- **预防**：改服务器配置文件前先 `git status` 确认干净，改完立即提交推送

### 8. dispatch.sh trap stash pop 重新制造冲突
- **根因**：dispatch.sh 流程 stash push → checkout → pull → stash pop。若 stash 含旧版本文件，pop 时与已推送的新版本冲突 → 产生 merge conflict 标记 → 下轮 dispatch 再次 FATAL
- **现象**：冲突已解决并推送后，下一轮 dispatch 又出现同样的冲突标记
- **解决**：`git stash clear` 清空脏 stash；确认 stash list 为空
- **预防**：解决冲突后检查 `git stash list`，清空后再启动 dispatch

### 9. touch/rm 锁文件存在 TOCTOU 竞态
- **根因**：`if [ -f lock ]; then rm -f lock; fi; touch lock` — 两个进程同时检查、同时删除、同时创建，双双通过
- **现象**：dispatch 日志每条消息出现两次，两个 dispatch 进程并行跑
- **解决**：改用 `mkdir` 原子锁（目录存在则 mkdir 失败，天然互斥）
```bash
if ! mkdir "$LOCKDIR" 2>/dev/null; then
  # 检查是否超时 stale lock
  AGE=$(( $(date +%s) - $(stat -c %Y "$LOCKDIR") ))
  [ "$AGE" -lt 55 ] && exit 0
  rmdir "$LOCKDIR" && mkdir "$LOCKDIR" || exit 0
fi
trap 'rmdir "$LOCKDIR" 2>/dev/null || true' EXIT
```
- **预防**：锁一律用 `mkdir`，不用 `touch`/`ln`/`flock`

### 10. 旧版 install.sh 部署的项目缺 hooks/settings 目录
- **根因**：v2.0 之前的 install.sh 不创建 `.claude/hooks/` 和 `settings.local.json`。`--update` 只刷新已存在文件，不引入新文件
- **现象**：新 hook（plan-backup.sh）无法自动部署到旧项目
- **解决**：手动 `cp` + `mkdir` + 写 `settings.local.json`
- **预防**：重大版本升级后检查所有目标路径是否存在，缺的手动补

### 11. pre-push hook 误拦 `git push --delete`
- **根因**：pre-push 检查 `git rev-parse --abbrev-ref HEAD`（当前分支），删除远程分支时当前仍在 main → 被拦截
- **现象**：`git push origin --delete archon/task-*` 报 BLOCKED
- **解决**：pre-push 开头读 stdin 检测 zero SHA（删除操作标志），放行
```bash
REF_LIST=$(cat)
if echo "$REF_LIST" | grep -q "0000000000000000000000000000000000000000"; then
    exit 0  # 分支删除 → 放行
fi
```
- **预防**：pre-push 模板必须包含 stdin 读取和 zero SHA 检测

**Why:** v2.1 部署 + #006 调度 + 管线修复过程中遇到以上新坑，反复回退。**How to apply:** 服务器操作后检查属主、检查 git status、清空 stash、用 mkdir 锁。
