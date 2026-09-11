#!/bin/bash
# 从 NAS 拉取巡检告警并推送 Telegram。
#
# 运行位置：阿里云服务器（唯一有 Telegram 通道的机器；NAS 无外网、开发机被墙）。
# 设计：NAS 侧零外网（只写 state/alert 文件），出口集中在本机。
# 语义：只有发送成功才把 NAS 上的 alert 归档到 alert.history；失败则留在 NAS 等下次重试（不丢数据）。
set -uo pipefail

NAS_HOST=root@nas
ALERT=/volume1/docker/langbot/state/alert
HISTORY=/volume1/docker/langbot/state/alert.history
LOG=/var/log/nas-alert.log
SENDER=/usr/local/bin/nas-alert-send.py
SSH_OPTS=(-nT -o BatchMode=yes -o ConnectTimeout=6 -o StrictHostKeyChecking=accept-new)

log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }

out=$(ssh "${SSH_OPTS[@]}" "$NAS_HOST" "cat $ALERT 2>/dev/null" 2>/dev/null)
rc=$?
if [ "$rc" -ne 0 ]; then
    log "fetch failed (ssh rc=$rc)"
    exit 2
fi
[ -z "$out" ] && exit 0

msg="🛰 NAS 巡检告警
$(printf '%s\n' "$out" | sed 's/^/· /')"

if printf '%s' "$msg" | python3 "$SENDER" >/dev/null 2>&1; then
    ssh "${SSH_OPTS[@]}" "$NAS_HOST" "cat $ALERT >> $HISTORY 2>/dev/null; rm -f $ALERT" >/dev/null 2>&1
    log "sent $(printf '%s\n' "$out" | wc -l) alert line(s)"
else
    log "send failed, alert kept pending on NAS"
    exit 3
fi
