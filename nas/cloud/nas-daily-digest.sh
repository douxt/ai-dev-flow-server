#!/bin/bash
# NAS 日报（阿里云 cron `0 9 * * *`）——"死者开关"：
#   收得到日报 = 云 cron、NAS ssh、Telegram 通道都活着；
#   收不到日报 = 整条告警链路（或其上游）已经坏了，这本身就是要知道的信号。
# 同时把当日关键状态汇总出来：巡检心跳年龄、自检心跳年龄、待发告警数、最近一次告警。
set -uo pipefail

NAS_HOST=root@nas
STATE_DIR=/volume1/docker/langbot/state
SENDER=/usr/local/bin/nas-alert-send.py
SSH_OPTS=(-nT -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
LOG=/var/log/nas-alert.log

log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }

info=$(ssh "${SSH_OPTS[@]}" "$NAS_HOST" '
    hb=/tmp/health_check.log; sc=/tmp/nas_selfcheck.log
    age() { [ -f "$1" ] && echo $(( $(date +%s) - $(stat -c %Y "$1") )) || echo -1; }
    pend=$(wc -l < /volume1/docker/langbot/state/alert 2>/dev/null || echo 0)
    hist=$(tail -1 /volume1/docker/langbot/state/alert.history 2>/dev/null)
    printf "HB_AGE=%s\nSC_AGE=%s\nHB_LAST=%s\nSC_LAST=%s\nPEND=%s\nHIST=%s\n" \
        "$(age $hb)" "$(age $sc)" "$(tail -1 $hb 2>/dev/null)" "$(tail -1 $sc 2>/dev/null)" "$pend" "$hist"
' 2>/dev/null)

if [ -z "$info" ]; then
    printf '%s' "🚨 NAS 日报获取失败：无法 ssh 到 NAS（或 NAS 关机/网络异常）。时间 $(date '+%F %T')" \
        | python3 "$SENDER" >/dev/null 2>&1
    log "digest: NAS unreachable（已尝试告警）"
    exit 2
fi

get() { printf '%s\n' "$info" | sed -n "s/^$1=//p"; }
hb_age=$(get HB_AGE); sc_age=$(get SC_AGE); pend=$(get PEND)
hb_last=$(get HB_LAST); sc_last=$(get SC_LAST); hist=$(get HIST)

fmt_age() { case "$1" in ''|-1) echo "无";; *) echo "$(( $1 / 60 )) 分钟前";; esac; }

msg="🛰 NAS 日报 $(date '+%F %T')
· 巡检心跳: $(fmt_age "$hb_age")   ${hb_last:-（无）}
· 自检心跳: $(fmt_age "$sc_age")   ${sc_last:-（无）}
· 待发告警: ${pend:-0} 条
· 最近已发告警: ${hist:-（无）}"

if printf '%s' "$msg" | python3 "$SENDER" >/dev/null 2>&1; then
    log "digest sent (hb_age=${hb_age} sc_age=${sc_age} pend=${pend})"
else
    log "digest send FAILED"
    exit 3
fi
