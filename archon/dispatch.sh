#!/bin/bash
# dispatch.sh — 通用 AFK 调度器（服务器版）
# 由 systemd timer 每 5 分钟触发。从 .devflow/config.yaml 读项目配置。
# 用法: bash dispatch.sh <项目路径>
# 隔离策略: git worktree add origin/main --detach（替代旧版 stash 模式）
set -euo pipefail

WORKSPACE="${1:-$(pwd)}"
DEVFLOW_DIR="$WORKSPACE/.devflow"
CONFIG="$DEVFLOW_DIR/config.yaml"
SCRIPTS_DIR="$DEVFLOW_DIR/scripts"
ARCHON_DIR="$DEVFLOW_DIR/archon"
LOG_FILE="$WORKSPACE/logs/dispatch.log"
ARCHON_WORKFLOW="auto-execute-afk"
MAX_RETRIES=3

mkdir -p "$(dirname "$LOG_FILE")"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

# 前置检查
if [ ! -f "$CONFIG" ]; then
    log "FATAL: config.yaml 不存在 ($CONFIG)"
    exit 1
fi

# 原子锁（防并发 dispatch）
LOCKDIR="$WORKSPACE/.dispatch.lock"
mkdir "$LOCKDIR" 2>/dev/null || { log "SKIP: 已有 dispatch 在运行"; exit 0; }

# 统一清理（lock + worktree + ARCHON_OUT，覆盖所有退出路径）
cleanup_exit() {
    rmdir "$LOCKDIR" 2>/dev/null || true
    rm -f "$ARCHON_OUT" 2>/dev/null || true
    if [ -n "${DISPATCH_WT:-}" ] && [ -d "$DISPATCH_WT" ]; then
        cd "$WORKSPACE" 2>/dev/null || true
        git worktree remove "$DISPATCH_WT" --force 2>/dev/null || true
    fi
    git worktree prune 2>/dev/null || true
}
ARCHON_OUT=""
trap cleanup_exit EXIT INT TERM

# git fetch 替代 git pull（worktree 从 origin/main 创建，无需本地 checkout main）
FETCH_ERR=$(git fetch origin 2>&1 1>/dev/null) || {
    log "FATAL: git fetch 失败 — ${FETCH_ERR}"
    python3 "$SCRIPTS_DIR/notify.py" status 2>/dev/null <<< "⛔ git fetch 失败" || true
    exit 1
}

# 创建临时 worktree（从 origin/main detached）
DISPATCH_WT=$(mktemp -d /tmp/dispatch-XXXXXX) && rmdir "$DISPATCH_WT" || {
    log "FATAL: 无法创建临时目录"
    exit 1
}
git worktree add "$DISPATCH_WT" origin/main --detach 2>/dev/null || {
    log "FATAL: worktree 创建失败"
    python3 "$SCRIPTS_DIR/notify.py" status 2>/dev/null <<< "⛔ worktree 创建失败" || true
    exit 1
}
cd "$DISPATCH_WT"
ISSUES_DIR="$DISPATCH_WT/issues"

# Archon workspace 去冲突：dispatch 用临时 worktree，Archon 注册了旧路径 → 下次报错
# 删除 stale source symlink，让 Archon 重新注册到当前 worktree 路径；结束后一并清理
ARCHON_WS="$HOME/.archon/workspaces/unknown/default"
ARCHON_REMOTE=$(git -C "$WORKSPACE" remote get-url origin 2>/dev/null || true)
if [ -n "$ARCHON_REMOTE" ]; then
    ARCHON_USER=$(echo "$ARCHON_REMOTE" | grep -oP '(?<=:)[^/]+(?=/)' || echo "$ARCHON_REMOTE" | grep -oP 'github\.com/\K[^/]+' || true)
    ARCHON_REPO=$(echo "$ARCHON_REMOTE" | grep -oP '[^/]+(?=\.git$)' || echo "$ARCHON_REMOTE" | sed 's|.*/||; s|\.git$||' || true)
    if [ -n "$ARCHON_USER" ] && [ -n "$ARCHON_REPO" ]; then
        ARCHON_WS="$HOME/.archon/workspaces/$ARCHON_USER/$ARCHON_REPO"
        rm -f "$ARCHON_WS/source" 2>/dev/null || true
    fi
fi

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

# 从 config.yaml 读取配置（简单 grep 解析，无 yq 依赖）
PROJECT_NAME=$(grep -E '^\s+name:' "$CONFIG" | head -1 | awk '{print $2}' | tr -d '"'"'" || echo "unknown")
BRANCH_PREFIX=$(grep -E '^\s+branch_prefix:' "$CONFIG" | head -1 | awk '{print $2}' | tr -d '"'"'" || echo "ai/")

log "--- dispatch 扫描: $PROJECT_NAME ---"

# handoff 检测：outbox/agent-b/ 有新消息 → 通知人（30min 去重）
# WORKSPACE 始终指向主工作树，不受 cd 到 worktree 影响
HANDOFF_DIR="$WORKSPACE/_handoff/outbox/agent-b"
HANDOFF_STAMP="$WORKSPACE/logs/.handoff_last_notify"
if [ -d "$HANDOFF_DIR" ]; then
    LATEST_MSG=$(ls -t "$HANDOFF_DIR"/*.md 2>/dev/null | head -1)
    if [ -n "$LATEST_MSG" ]; then
        MSG_MTIME=$(stat -c %Y "$LATEST_MSG" 2>/dev/null || echo 0)
        LAST_NOTIFY=$(cat "$HANDOFF_STAMP" 2>/dev/null || echo 0)
        if [ "$(( $(date +%s) - LAST_NOTIFY ))" -gt 1800 ] || [ "$MSG_MTIME" -gt "$LAST_NOTIFY" ]; then
            MSG_ID=$(basename "$LATEST_MSG" .md)
            echo "📨 ${PROJECT_NAME}: B 有新委托 — ${MSG_ID}" | python3 "$SCRIPTS_DIR/notify.py" status 2>/dev/null || true
            date +%s > "$HANDOFF_STAMP"
            log "HANDOFF: 检测到新委托 ${MSG_ID}"
        fi
    fi
fi

# 扫描第一个无依赖阻塞的 ready AFK issue
BEST_ISSUE=""
while IFS= read -r f; do
    [ -z "$f" ] && continue
    TYPE=$(grep "^type:" "$f" | awk '{print $2}' || true)
    [ "$TYPE" != "AFK" ] && continue
    BLOCKED_BY=$(grep "^blocked_by:" "$f" | grep -oP '\[.*?\]' | tr -d '[]' | tr ',' '\n' | sed 's/^ *"//;s/" *$//;s/^ *//;s/ *$//' | grep -v "^$" || true)
    DEPS_OK=true
    for dep in $BLOCKED_BY; do
        [ -z "$dep" ] && continue
        DEP_FILE=$(find "$ISSUES_DIR" -name "${dep}-*.md" -exec grep -l "^status: done$" {} \; 2>/dev/null | head -1)
        [ -z "$DEP_FILE" ] && DEPS_OK=false && break
    done
    [ "$DEPS_OK" = true ] && BEST_ISSUE="$f" && break
done < <(grep -rl "^status: ready$" "$ISSUES_DIR" --include="*.md" 2>/dev/null | grep -vE '(PRD|TEMPLATE)' | sort)

if [ -z "$BEST_ISSUE" ]; then
    log "NO_MORE_TASKS: 无可用 ready issue"
    exit 0
fi

ISSUE_NUM=$(basename "$BEST_ISSUE" | cut -d- -f1)
ISSUE_SLUG=$(basename "$BEST_ISSUE" .md)
ISSUE_PATH=$(realpath --relative-to="$DISPATCH_WT" "$BEST_ISSUE")
log "DISPATCH: #${ISSUE_NUM} ${ISSUE_SLUG}"

# 宪法前置检查
CONSTITUTION_RESULT=$(python3 "$SCRIPTS_DIR/check_constitution.py" "$BEST_ISSUE" --json 2>&1 || true)
FAILED=$(echo "$CONSTITUTION_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('failed',0))" 2>/dev/null || echo 99)
if [ "$FAILED" -gt 0 ]; then
    FAIL_ITEMS=$(echo "$CONSTITUTION_RESULT" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for c in d.get('checks',[]):
    if c['severity']=='fail': print(f\"  [{c['rule']}] {c['desc']}\")
" 2>/dev/null || true)
    log "CONSTITUTION_FAIL: #${ISSUE_NUM} — ${FAILED} 项不通过"
    echo "⛔ ${PROJECT_NAME}: #${ISSUE_NUM} 宪法检查不通过（${FAILED} 项）" | python3 "$SCRIPTS_DIR/notify.py" status 2>/dev/null || true
    exit 1
fi
log "CONSTITUTION_PASS: #${ISSUE_NUM}"

# worktree 去重：同一 issue 已有活跃 worktree 则跳过
if git worktree list 2>/dev/null | grep -qE "(^|[-/])${ISSUE_NUM}($|[^0-9])"; then
    log "SKIP: #${ISSUE_NUM} 已有活跃 worktree"
    exit 0
fi

# 原子抢占（git push 竞态，先 push 者胜）
sed -i "s/^status: ready$/status: in_progress/" "$BEST_ISSUE"
git add "$BEST_ISSUE"
git commit -m "dispatch: claim #${ISSUE_NUM} -- ${ISSUE_SLUG}" 2>/dev/null || true
if ! git push origin HEAD:main 2>/dev/null; then
    sed -i "s/^status: in_progress$/status: ready/" "$BEST_ISSUE"
    git checkout -- "$BEST_ISSUE" 2>/dev/null || true
    log "FAIL: 抢占失败，push 被拒绝"
    exit 1
fi
log "CLAIMED: push OK"

# 通知：开始执行
echo "🚀 ${PROJECT_NAME}: #${ISSUE_NUM} ${ISSUE_SLUG} 开始执行" | python3 "$SCRIPTS_DIR/notify.py" status 2>/dev/null || true

# 派发 Archon
START_TIME=$(date +%s)
ATTEMPT=1
while [ $ATTEMPT -le $MAX_RETRIES ]; do
    log "ARCHON: 尝试 #${ATTEMPT}/${MAX_RETRIES}"
    ARCHON_OUT=$(mktemp)
    if archon workflow run "$ARCHON_WORKFLOW" "$ISSUE_PATH" --from main > "$ARCHON_OUT" 2>&1; then
        cat "$ARCHON_OUT" >> "$LOG_FILE"
        grep -E "##\[(AC_DONE|AC_EXISTS|AC_FAIL|IMPLEMENT_RESULT|AC_VERIFY_RESULT|HARD_GATE)\]" "$ARCHON_OUT" 2>/dev/null | while IFS= read -r marker; do
            log "ARCHON_NODE: $marker"
        done || true
        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))

        # 标记完成：检查 archon 是否已 auto-merge 标 done
        git pull --rebase --quiet 2>/dev/null || true
        if grep -q '^status: done$' "$BEST_ISSUE" 2>/dev/null; then
            log "AUTO_MERGED: #${ISSUE_NUM} archon 已自动合并为 done"
        else
            sed -i "s/^status: in_progress$/status: in_review/" "$BEST_ISSUE"
            git add "$BEST_ISSUE"
            git commit -m "dispatch: review #${ISSUE_NUM} -- ${ISSUE_SLUG} (待审批)" 2>/dev/null || true
            git push origin HEAD:main 2>/dev/null || log "WARN: push 失败"
        fi

        # 成本追踪
        python3 "$SCRIPTS_DIR/cost_tracker.py" log --issue "${ISSUE_SLUG}" --status "in_review" --duration "$DURATION" --workflow "$ARCHON_WORKFLOW" --workspace "$WORKSPACE" 2>/dev/null || true

        # 审批通知
        PR_URL=$(grep -oP 'pr:\s*\["?\Khttps://[^"\] ]+' "$BEST_ISSUE" 2>/dev/null | head -1 || echo "")
        FILES=$(git diff --name-only HEAD~1 2>/dev/null | head -20 | tr '\n' ',' | sed 's/,$//')
        python3 -c "
import json,sys
payload={'issue':'${ISSUE_SLUG}','pr_url':'${PR_URL}','files':[f.strip() for f in '${FILES}'.split(',') if f.strip()]}
sys.stdout.write(json.dumps(payload))
" | python3 "$SCRIPTS_DIR/notify.py" approve-request 2>/dev/null || log "WARN: notify 失败"

        archon isolation cleanup --merged 2>/dev/null || true
        rm -f "$ARCHON_WS/source" 2>/dev/null || true
        rm -f "$ARCHON_OUT"
        log "IN_REVIEW: #${ISSUE_NUM} ${ISSUE_SLUG} (耗时 ${DURATION}s)"
        exit 0
    fi
    # 失败：也捕获标记
    cat "$ARCHON_OUT" >> "$LOG_FILE" 2>/dev/null || true
    grep -E "##\[(AC_DONE|AC_EXISTS|AC_FAIL|IMPLEMENT_RESULT|AC_VERIFY_RESULT|HARD_GATE)\]" "$ARCHON_OUT" 2>/dev/null | while IFS= read -r marker; do
        log "ARCHON_NODE: $marker"
    done || true
    rm -f "$ARCHON_OUT"
    ATTEMPT=$((ATTEMPT + 1))
    sleep 10
done

# 全部重试失败
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
log "UNRESOLVED: #${ISSUE_NUM} ${ISSUE_SLUG} — ${MAX_RETRIES} 次尝试均失败"
git pull --rebase --quiet 2>/dev/null || true
sed -i "s/^status: in_progress$/status: failed/" "$BEST_ISSUE"
git add "$BEST_ISSUE"
git commit -m "dispatch: failed #${ISSUE_NUM} -- ${ISSUE_SLUG}" 2>/dev/null || true
git push origin HEAD:main 2>/dev/null || log "WARN: failed push"
python3 "$SCRIPTS_DIR/cost_tracker.py" log --issue "${ISSUE_SLUG}" --status "failed" --duration "$DURATION" --workflow "$ARCHON_WORKFLOW" --workspace "$WORKSPACE" 2>/dev/null || true
echo "❌ ${PROJECT_NAME}: #${ISSUE_NUM} 执行失败（${MAX_RETRIES} 次重试，耗时 ${DURATION}s）" | python3 "$SCRIPTS_DIR/notify.py" status 2>/dev/null || true
archon isolation cleanup --merged 2>/dev/null || true
rm -f "$ARCHON_WS/source" 2>/dev/null || true
exit 1
