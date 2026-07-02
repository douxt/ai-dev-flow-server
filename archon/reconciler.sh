#!/bin/bash
# reconciler.sh — 通用状态修复器（服务器版）
# 由 systemd timer 每 15 分钟触发。检测卡住/孤儿 issue。
# 用法: bash reconciler.sh <项目路径>
# 隔离策略: git worktree add origin/main --detach（替代旧版 stash 模式）
set -euo pipefail

WORKSPACE="${1:-$(pwd)}"
SCRIPTS_DIR="$WORKSPACE/.devflow/scripts"
LOG_FILE="$WORKSPACE/logs/reconcile.log"

mkdir -p "$(dirname "$LOG_FILE")"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

# 原子锁（防并发 reconcile）
LOCKDIR="$WORKSPACE/.reconcile.lock"
mkdir "$LOCKDIR" 2>/dev/null || { log "SKIP: 已有 reconcile 在运行"; exit 0; }

# 统一清理（lock + worktree，覆盖所有退出路径）
cleanup_exit() {
    rmdir "$LOCKDIR" 2>/dev/null || true
    if [ -n "${RECONCILE_WT:-}" ] && [ -d "$RECONCILE_WT" ]; then
        cd "$WORKSPACE" 2>/dev/null || true
        git worktree remove "$RECONCILE_WT" --force 2>/dev/null || true
    fi
    git worktree prune 2>/dev/null || true
}
trap cleanup_exit EXIT INT TERM

# git fetch 替代 git pull
git fetch origin 2>/dev/null || { log "FATAL: git fetch 失败"; exit 1; }

# 创建临时 worktree
RECONCILE_WT=$(mktemp -d /tmp/reconcile-XXXXXX) && rmdir "$RECONCILE_WT" || {
    log "FATAL: 无法创建临时目录"
    exit 1
}
git worktree add "$RECONCILE_WT" origin/main --detach 2>/dev/null || {
    log "FATAL: worktree 创建失败"
    exit 1
}
cd "$RECONCILE_WT"
ISSUES_DIR="$RECONCILE_WT/issues"

# index.lock 时效检测（防僵尸 lock 阻塞所有 git 操作）
LOCK="$WORKSPACE/.git/index.lock"
if [ -f "$LOCK" ]; then
  AGE=$(( $(date +%s) - $(stat -c %Y "$LOCK" 2>/dev/null || echo 0) ))
  if [ "$AGE" -gt 300 ]; then
    rm -f "$LOCK" && log "CLEANED stale index.lock (${AGE}s)"
  else
    log "WARN: index.lock active (${AGE}s) — git locked"; exit 1
  fi
fi

CHANGED=false

# 0. 等待人工审批 → 跳过（不修改状态，不 push）
while IFS= read -r f; do
    [ -z "$f" ] && continue
    ISSUE_NUM=$(basename "$f" | cut -d- -f1)
    log "SKIP: #${ISSUE_NUM} awaiting human approval (waiting-approval)"
done < <(grep -rl "^status: waiting-approval$" "$ISSUES_DIR" --include="*.md" 2>/dev/null || true)

# 1. in_progress >6h 无 git 活动 → 回收（但 Archon 活跃时跳过）
while IFS= read -r f; do
    [ -z "$f" ] && continue
    ISSUE_NUM=$(basename "$f" | cut -d- -f1)
    ISSUE_BRANCH=$(git branch -a | grep "ai/.*${ISSUE_NUM}" | head -1 | xargs || true)
    if [ -n "$ISSUE_BRANCH" ]; then
        LAST_COMMIT=$(git log -1 --format="%ct" "$ISSUE_BRANCH" 2>/dev/null || echo 0)
        NOW=$(date +%s)
        HOURS=$(( (NOW - LAST_COMMIT) / 3600 ))
        if [ "$HOURS" -gt 6 ]; then
            # 有活跃 Archon 进程 → 不回收（新的 archon/task-* 分支在干活）
            pgrep -f "archon workflow run" >/dev/null 2>&1 && continue
            # 有 archon/ 分支或 worktree 与此 issue 匹配 → 不回收
            if git -C "$WORKSPACE" branch -a | grep -qE "archon/task-"; then continue; fi
            if git -C "$WORKSPACE" worktree list --porcelain 2>/dev/null | grep -qE "archon/task-"; then continue; fi
            log "RECLAIM: #${ISSUE_NUM} in_progress >6h 无活动 (${HOURS}h)，回收为 ready"
            sed -i "s/^status: in_progress$/status: ready/" "$f"
            CHANGED=true
        fi
    fi
done < <(grep -rl "^status: in_progress$" "$ISSUES_DIR" --include="*.md" 2>/dev/null || true)

# 2. failed >24h → backlog
while IFS= read -r f; do
    [ -z "$f" ] && continue
    ISSUE_NUM=$(basename "$f" | cut -d- -f1)
    LAST_MOD=$(stat -c %Y "$f" 2>/dev/null || echo 0)
    NOW=$(date +%s)
    HOURS=$(( (NOW - LAST_MOD) / 3600 ))
    if [ "$HOURS" -gt 24 ]; then
        log "RECLAIM: #${ISSUE_NUM} failed >24h (${HOURS}h)，回收为 backlog"
        sed -i "s/^status: failed$/status: backlog/" "$f"
        CHANGED=true
    fi
done < <(grep -rl "^status: failed$" "$ISSUES_DIR" --include="*.md" 2>/dev/null || true)

# 0. 清理已合并的 ai/ 分支 + 超过 7 天的 archon/ 废弃分支
AGE_7DAYS=604800
git branch --merged main 2>/dev/null | grep '  ai/' | xargs -r git branch -d 2>/dev/null || true
git branch 2>/dev/null | grep 'archon/task-' | while read br; do
  br=$(echo "$br" | xargs)
  COMMIT_DATE=$(git log -1 --format="%ct" "$br" 2>/dev/null || echo 0)
  [ $(($(date +%s) - COMMIT_DATE)) -gt $AGE_7DAYS ] && git branch -D "$br" 2>/dev/null || true
done

# 3. 孤儿检测：in_progress >5min + 无活跃进程 + 无匹配分支/worktree
while IFS= read -r f; do
    [ -z "$f" ] && continue
    ISSUE_NUM=$(basename "$f" | cut -d- -f1)

    ISSUE_MTIME=$(stat -c %Y "$f" 2>/dev/null || echo 0)
    NOW=$(date +%s)
    AGE_SEC=$((NOW - ISSUE_MTIME))
    [ "$AGE_SEC" -lt 300 ] && continue

    pgrep -f "dispatch.sh.*$(basename "$WORKSPACE")" >/dev/null 2>&1 && continue
    pgrep -f "archon workflow run" >/dev/null 2>&1 && continue

    if git -C "$WORKSPACE" branch -a | grep -qE "(ai|archon)/[^/]*(${ISSUE_NUM}|task-auto-execute)($|[^0-9])"; then continue; fi
    if git -C "$WORKSPACE" worktree list --porcelain 2>/dev/null | grep -qE "(^|[-/])${ISSUE_NUM}($|[^0-9])"; then continue; fi

    log "ORPHAN: #${ISSUE_NUM} in_progress >5min 无进程无分支/worktree，回收为 ready"
    sed -i "s/^status: in_progress$/status: ready/" "$f"
    CHANGED=true
done < <(grep -rl "^status: in_progress$" "$ISSUES_DIR" --include="*.md" 2>/dev/null || true)

# 4. backlog 依赖全部 done → 自动标 ready
while IFS= read -r f; do
    [ -z "$f" ] && continue
    BLOCKED_BY=$(grep "^blocked_by:" "$f" | sed 's/.*\[\(.*\)\].*/\1/' | tr ',' '\n' | sed 's/^ *"//;s/" *$//;s/^ *//;s/ *$//' | grep -v "^$\|^\[\]$" || true)
    [ -z "$BLOCKED_BY" ] && continue
    ALL_DONE=true
    for dep in $BLOCKED_BY; do
        [ -z "$dep" ] && continue
        # 精确匹配 + 前缀匹配（兼容不同 issue 命名格式）
        DEP_FILE=$(find "$ISSUES_DIR" -maxdepth 1 \( -name "${dep}.md" -o -name "${dep}-*.md" \) -exec grep -l "^status: done$" {} \; 2>/dev/null | head -1)
        [ -z "$DEP_FILE" ] && ALL_DONE=false && break
    done
    if [ "$ALL_DONE" = true ]; then
        ISSUE_NUM=$(basename "$f" | cut -d- -f1)
        log "AUTO_READY: #${ISSUE_NUM} 依赖全部 done，backlog → ready"
        sed -i "s/^status: backlog$/status: ready/" "$f"
        CHANGED=true
    fi
done < <(grep -rl "^status: backlog$" "$ISSUES_DIR" --include="*.md" 2>/dev/null || true)

# 5. in_review → 检查 PR 是否已合并 → done
while IFS= read -r f; do
    [ -z "$f" ] && continue
    ISSUE_NUM=$(basename "$f" | cut -d- -f1)
    PR_URL=$(grep -oP 'pr:\s*\["?\Khttps://[^"\] ]+' "$f" 2>/dev/null | head -1 || echo "")
    if [ -n "$PR_URL" ]; then
        MERGED=$(gh pr view "$PR_URL" --json merged --jq '.merged' 2>/dev/null || echo "false")
        if [ "$MERGED" = "true" ]; then
            log "AUTO_DONE: #${ISSUE_NUM} PR 已合并，in_review → done"
            sed -i "s/^status: in_review$/status: done/" "$f"
            CHANGED=true
        fi
    else
        BRANCH=$(git branch -a | grep "ai/.*${ISSUE_NUM}" | head -1 | xargs || true)
        if [ -n "$BRANCH" ]; then
            MERGED_PR=$(gh pr list --head "$BRANCH" --state merged --json url --jq '.[0].url' 2>/dev/null || echo "")
            if [ -n "$MERGED_PR" ]; then
                log "AUTO_DONE: #${ISSUE_NUM} PR 已合并（via branch），in_review → done"
                sed -i "s/^status: in_review$/status: done/" "$f"
                sed -i "/^---$/a pr: [\"$MERGED_PR\"]" "$f"
                CHANGED=true
            fi
        fi
    fi
done < <(grep -rl "^status: in_review$" "$ISSUES_DIR" --include="*.md" 2>/dev/null || true)

if [ "$CHANGED" = true ]; then
    git add "$ISSUES_DIR" 2>/dev/null || true
    git commit -m "reconcile: 状态修复 ($(date +%Y-%m-%d))" 2>/dev/null || true
    git push origin HEAD:main 2>/dev/null || log "WARN: push 失败"
    log "RECONCILE: 状态修复完成"
else
    log "RECONCILE: 无需修复"
fi
