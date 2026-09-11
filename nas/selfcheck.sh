#!/bin/bash
# NAS 自检（NAS 本地 cron `*/15`）——24/7 覆盖两件"没人会注意"的事：
#   ① 巡检自身是否停跳（/tmp/health_check.log 末次写入年龄）
#   ② 在版脚本是否被改动（对照 state/expected.md5 清单）
# 另记录待发告警积压（说明云侧拉取/推送可能失效）。
#
# NAS 无外网，本脚本**不做发送**：结果写入 state/alert，由阿里云 cron 拉取后推 Telegram。
# 测试/影子运行开关（cron 不设置）：
#   SC_STATE_DIR / SC_LOG / SC_HB_LOG / SC_MANIFEST / SC_HB_MAX_MIN / SC_DEDUP_TTL
set -uo pipefail

STATE_DIR=${SC_STATE_DIR:-/volume1/docker/langbot/state}
MANIFEST=${SC_MANIFEST:-$STATE_DIR/expected.md5}
ALERT_FILE=$STATE_DIR/alert
ALERT_STATE_FILE=$STATE_DIR/alert.last
LOG=${SC_LOG:-/tmp/nas_selfcheck.log}
HB_LOG=${SC_HB_LOG:-/tmp/health_check.log}
HB_MAX_MIN=${SC_HB_MAX_MIN:-20}      # 巡检日志最大允许静默（分钟）
PENDING_MAX_MIN=${SC_PENDING_MAX_MIN:-30}
DEDUP_TTL=${SC_DEDUP_TTL:-3600}
LOG_KEEP_LINES=500

mkdir -p "$STATE_DIR"
log() { echo "[$(date '+%F %T')] $*" >> "$LOG"; }

rotate_log() {
    [ -f "$LOG" ] || return 0
    local lines
    lines=$(wc -l < "$LOG" 2>/dev/null || echo 0)
    if [ "${lines:-0}" -gt "$LOG_KEEP_LINES" ]; then
        tail -n "$LOG_KEEP_LINES" "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG"
    fi
}
trap rotate_log EXIT

raise_alert() {   # type detail
    local type="$1"; shift
    local detail="$*"
    local now last=0
    now=$(date +%s)
    [ -f "$ALERT_STATE_FILE" ] && last=$(awk -v t="$type" '$1==t {v=$2} END{print v}' "$ALERT_STATE_FILE" 2>/dev/null || true)
    case "$last" in ''|*[!0-9]*) last=0 ;; esac
    [ $((now - last)) -lt "$DEDUP_TTL" ] && return 0
    { grep -v "^${type} " "$ALERT_STATE_FILE" 2>/dev/null || true; echo "${type} ${now}"; } \
        > "$ALERT_STATE_FILE.tmp" 2>/dev/null && mv "$ALERT_STATE_FILE.tmp" "$ALERT_STATE_FILE"
    printf '%s|%s|%s\n' "$now" "$type" "$detail" >> "$ALERT_FILE"
    log "ALERT ${type} ${detail}"
    return 0
}

problems=0

# ① 巡检心跳
hb_age=-1
if [ -f "$HB_LOG" ]; then
    hb_age=$(( $(date +%s) - $(stat -c %Y "$HB_LOG" 2>/dev/null || echo 0) ))
fi
if [ "$hb_age" -lt 0 ]; then
    raise_alert "selfcheck-heartbeat" "detail=log-missing path=${HB_LOG}"
    problems=$((problems + 1))
elif [ "$hb_age" -gt $((HB_MAX_MIN * 60)) ]; then
    raise_alert "selfcheck-heartbeat" "detail=stale age_min=$((hb_age / 60)) threshold_min=${HB_MAX_MIN}"
    problems=$((problems + 1))
fi

# ② 在版文件是否被改动（对照清单）
drift_count=0
drift_detail=""
if [ ! -f "$MANIFEST" ]; then
    raise_alert "selfcheck-drift" "detail=manifest-missing path=${MANIFEST}"
    problems=$((problems + 1))
else
    while IFS=$'\t' read -r exp_md5 nas_path desc; do
        [ -z "${nas_path:-}" ] && continue
        act_md5=$(md5sum "$nas_path" 2>/dev/null | awk '{print $1}')
        if [ -z "$act_md5" ]; then
            drift_count=$((drift_count + 1)); drift_detail="${drift_detail}missing:${nas_path};"
        elif [ "$act_md5" != "$exp_md5" ]; then
            drift_count=$((drift_count + 1)); drift_detail="${drift_detail}changed:${nas_path};"
        fi
    done < "$MANIFEST"
    if [ "$drift_count" -gt 0 ]; then
        raise_alert "selfcheck-drift" "count=${drift_count} ${drift_detail}"
        problems=$((problems + 1))
    fi
fi

# ③ 待发告警积压（只记日志：若传输坏了，这条 alert 也送不出去，靠云侧日报兜底）
pending=0; pend_age=-1
if [ -f "$ALERT_FILE" ]; then
    pending=$(wc -l < "$ALERT_FILE" 2>/dev/null || echo 0)
    pend_age=$(( $(date +%s) - $(stat -c %Y "$ALERT_FILE" 2>/dev/null || echo 0) ))
    if [ "$pend_age" -gt $((PENDING_MAX_MIN * 60)) ]; then
        log "WARN pending-alerts age_min=$((pend_age / 60)) count=${pending}（传输链路可能失效）"
    fi
fi

log "heartbeat hb_age_s=${hb_age} drift=${drift_count} pending=${pending} problems=${problems}"
[ "$problems" -eq 0 ]
