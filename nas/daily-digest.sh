#!/bin/bash
# NAS 日报（NAS 本地 cron `0 9 * * *`）——"死者开关"：
#   收到 = 巡检/自检/代理出口/Telegram 都活着；收不到 = 有东西坏了（这本身就是信号）
set -uo pipefail
REPO_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib-telegram.sh
. "$REPO_DIR/lib-telegram.sh"

STATE_DIR=${DG_STATE_DIR:-/volume1/docker/langbot/state}
LOG=${DG_LOG:-/tmp/nas_digest.log}

log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }
mkdir -p "$STATE_DIR"

age_min() {   # 文件 mtime 到现在多少分钟；不存在 → "无"
    [ -f "$1" ] || { echo "无"; return; }
    echo "$(( ( $(date +%s) - $(stat -c %Y "$1" 2>/dev/null || echo 0) ) / 60 )) 分钟前"
}

hb=$(tail -1 /tmp/health_check.log 2>/dev/null)
sc=$(tail -1 /tmp/nas_selfcheck.log 2>/dev/null)
pend=0
[ -f "$STATE_DIR/alert" ] && pend=$(wc -l < "$STATE_DIR/alert")
hist=$(tail -1 "$STATE_DIR/alert.history" 2>/dev/null)

msg="🛰 NAS 日报 $(date '+%F %T')
· 巡检心跳: $(age_min /tmp/health_check.log)
· 自检心跳: $(age_min /tmp/nas_selfcheck.log)
· 待发告警: ${pend:-0} 条
· 最近已发: ${hist:-（无）}
· 巡检末行: ${hb:-（无）}
· 自检末行: ${sc:-（无）}"

if tg_load && tg_send "$msg"; then
    log "digest sent (pending=${pend})"
else
    log "digest FAILED"
    exit 1
fi
