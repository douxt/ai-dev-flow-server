#!/bin/bash
# 后台调度器 — 替代 cron（容器无 systemd/无 cron 权限）
# dispatch: 每 5 分钟 / reconciler: 每 15 分钟
set -euo pipefail
PROJECT="/home/coder/project/ai-dev-flow-server"
LOG="$PROJECT/logs/scheduler.log"
[ -f ~/.devflow-env ] && source ~/.devflow-env
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

echo "[$(date -Iseconds)] scheduler started (dispatch=*/5, reconcile=*/15)" >> "$LOG"

DISPATCH_COUNT=0
while true; do
    DISPATCH_COUNT=$((DISPATCH_COUNT + 1))
    bash "$PROJECT/archon/dispatch.sh" "$PROJECT" >> "$LOG" 2>&1 && echo "[$(date -Iseconds)] dispatch OK" >> "$LOG" || echo "[$(date -Iseconds)] dispatch FAIL" >> "$LOG"
    if [ $((DISPATCH_COUNT % 3)) -eq 0 ]; then
        bash "$PROJECT/archon/reconciler.sh" "$PROJECT" >> "$LOG" 2>&1 && echo "[$(date -Iseconds)] reconciler OK" >> "$LOG" || echo "[$(date -Iseconds)] reconciler FAIL" >> "$LOG"
    fi
    sleep 300
done
