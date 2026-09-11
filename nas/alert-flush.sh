#!/bin/bash
# 告警投递（NAS 本地 cron `*/2`）——把 state/alert 里的待发告警经网关代理推 Telegram。
#
# 设计：NAS 自洽，不依赖任何外部主机。
#   - 生产者（health-check / selfcheck / deep-smoke）只写 state/alert，不做网络请求
#   - 本脚本原子认领队列（mv alert → alert.sending），逐条发送
#   - 成功 → 追加到 alert.history；失败 → 并回 state/alert（不丢数据，下轮重试）
#   - 发送失败只记日志（此时通知通道本身不可用，只能靠"收不到每日摘要"暴露）
set -uo pipefail
REPO_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib-telegram.sh
. "$REPO_DIR/lib-telegram.sh"

STATE_DIR=${AF_STATE_DIR:-/volume1/docker/langbot/state}
ALERT_FILE=$STATE_DIR/alert
SENDING_FILE=$STATE_DIR/alert.sending
HISTORY_FILE=$STATE_DIR/alert.history
LOG=${AF_LOG:-/tmp/nas_alert_flush.log}
LOG_KEEP_LINES=500

mkdir -p "$STATE_DIR"
log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }

rotate_log() {
    [ -f "$LOG" ] || return 0
    local lines; lines=$(wc -l < "$LOG" 2>/dev/null || echo 0)
    if [ "${lines:-0}" -gt "$LOG_KEEP_LINES" ]; then
        tail -n "$LOG_KEEP_LINES" "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG"
    fi
}
trap rotate_log EXIT

[ -s "$ALERT_FILE" ] || exit 0
mv "$ALERT_FILE" "$SENDING_FILE" 2>/dev/null || { log "claim failed"; exit 0; }

if ! tg_load; then
    log "conf error, requeue"
    cat "$SENDING_FILE" >> "$ALERT_FILE" 2>/dev/null; rm -f "$SENDING_FILE"; exit 1
fi

failed=0; sent=0
while IFS= read -r line; do
    [ -z "$line" ] && continue
    msg="🛰 NAS 告警
$line"
    ftype=$(printf '%s' "$line" | cut -d'|' -f2)
    fdetail=$(printf '%s' "$line" | cut -d'|' -f3-)
    msg="🛰 NAS 告警 [${ftype}]
${fdetail}
时间: $(date '+%F %T')"
    if tg_send "$msg"; then
        printf '%s\n' "$line" >> "$HISTORY_FILE"
        sent=$((sent + 1))
    else
        printf '%s\n' "$line" >> "$ALERT_FILE.retry"
        failed=$((failed + 1))
    fi
done < "$SENDING_FILE"
rm -f "$SENDING_FILE"

if [ -s "$ALERT_FILE.retry" ]; then
    cat "$ALERT_FILE.retry" >> "$ALERT_FILE"
    rm -f "$ALERT_FILE.retry"
fi
log "sent=${sent} failed=${failed}"
[ "$failed" -eq 0 ]
