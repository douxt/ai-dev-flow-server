#!/bin/bash
# NAS 看门狗（在开发机运行，cron 每小时）—— 补上"静默失效"的周期性发现
#
# 检查三件事：
#   1. 漂移对账：NAS 在版脚本 md5 vs 仓库 main（复用 nas/check-drift.sh）
#   2. 巡检心跳新鲜度：/tmp/health_check.log 最后写入时间（cron */5 → 超过阈值即异常）
#   3. 待发告警积压：NAS state/alert 非空说明云侧拉取/推送失败
#
# 静默原则：一切正常不输出、不通知。异常经阿里云 nas-alert-send.py 推 Telegram
#   （开发机与 NAS 均无法直连 Telegram；云服务器是唯一有通道的机器）。
# 去重：同一签名 6 小时内只通知一次（避免每小时刷屏）。
#
# 用法:
#   bash nas/watchdog.sh              # 正常巡检（cron 用）
#   WD_FORCE_PROBLEM=1 bash nas/watchdog.sh   # 自检：强制制造一条问题，验证通知链路
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
NAS_HOST=${WD_NAS:-root@nas}
CLOUD_HOST=${WD_CLOUD:-root@115.29.110.107}
SENDER=/usr/local/bin/nas-alert-send.py
SSH_OPTS=(-nT -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
# 推送用：必须保留 stdin（-n 会把管道内容丢掉），只禁 TTY
SSH_STDIN_OPTS=(-T -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)

STATE_DIR=${WD_STATE_DIR:-$HOME/.local/state}
STATE_FILE=$STATE_DIR/nas-watchdog.state
LOG_FILE=$STATE_DIR/nas-watchdog.log
HEARTBEAT_MAX_MIN=${WD_HEARTBEAT_MAX_MIN:-20}   # 巡检日志最大允许静默时长（分钟）
DEDUP_TTL=${WD_DEDUP_TTL:-21600}                # 同类问题 6 小时内不重复通知
FORCE_PROBLEM=${WD_FORCE_PROBLEM:-0}

mkdir -p "$STATE_DIR"
log() { echo "[$(date '+%F %T')] $*" >> "$LOG_FILE"; }

problems=()

# ---------- 1) 漂移对账 ----------
drift_out=$(timeout 120 bash "$REPO_ROOT/nas/check-drift.sh" 2>&1)
if [ $? -ne 0 ]; then
    drift_lines=$(printf '%s\n' "$drift_out" | grep -E '^(DRIFT|DOWN)' | sed 's/^/  /')
    [ -z "$drift_lines" ] && drift_lines="  （check-drift 失败但无 DRIFT/DOWN 行，可能 NAS 不可达）"
    problems+=("NAS 脚本漂移:${drift_lines}")
fi

# ---------- 2)+3) NAS 侧取数（一次 ssh 取全）----------
nas_info=$(ssh "${SSH_OPTS[@]}" "$NAS_HOST" '
    LOG=/tmp/health_check.log
    if [ -f "$LOG" ]; then
        age=$(( $(date +%s) - $(stat -c %Y "$LOG" 2>/dev/null || echo 0) ))
        last=$(tail -1 "$LOG" 2>/dev/null)
    else
        age=-1; last="(no log)"
    fi
    pend=$(wc -l < /volume1/docker/langbot/state/alert 2>/dev/null || echo 0)
    printf "AGE=%s\nLAST=%s\nPEND=%s\n" "$age" "$last" "$pend"
' 2>/dev/null)

if [ -z "$nas_info" ]; then
    problems+=("NAS 不可达（ssh 取数失败）")
else
    age=$(printf '%s\n' "$nas_info" | sed -n 's/^AGE=//p')
    last=$(printf '%s\n' "$nas_info" | sed -n 's/^LAST=//p')
    pend=$(printf '%s\n' "$nas_info" | sed -n 's/^PEND=//p')

    case "$age" in ''|*[!0-9-]*) age=-1 ;; esac
    if [ "$age" -lt 0 ]; then
        problems+=("巡检日志不存在（$last）")
    elif [ "$age" -gt $((HEARTBEAT_MAX_MIN * 60)) ]; then
        problems+=("巡检心跳停止: 最后写入 $((age / 60)) 分钟前（阈值 ${HEARTBEAT_MAX_MIN} 分钟）｜末行: $last")
    fi

    case "$pend" in ''|*[!0-9]*) pend=0 ;; esac
    if [ "$pend" -gt 0 ]; then
        problems+=("NAS 有待发告警 $pend 条（说明云侧拉取或推送失败）")
    fi
fi

# 自检钩子：验证通知链路（仅手动使用，cron 不设置）
if [ "$FORCE_PROBLEM" = "1" ]; then
    problems+=("【自检】看门狗通知链路演练（WD_FORCE_PROBLEM=1）")
fi

# ---------- 判定与通知 ----------
if [ "${#problems[@]}" -eq 0 ]; then
    log "OK（漂移/心跳/积压 均正常）"
    exit 0
fi

body=$(printf '%s\n' "${problems[@]}")
signature=$(printf '%s' "$body" | md5sum | awk '{print $1}')

now=$(date +%s)
last_sig=""; last_ts=0
if [ -f "$STATE_FILE" ]; then
    last_sig=$(sed -n 's/^sig=//p' "$STATE_FILE" | tail -1)
    last_ts=$(sed -n 's/^ts=//p' "$STATE_FILE" | tail -1)
fi
case "$last_ts" in ''|*[!0-9]*) last_ts=0 ;; esac

if [ "$signature" = "$last_sig" ] && [ $((now - last_ts)) -lt "$DEDUP_TTL" ]; then
    log "SUPPRESSED（同类问题 $(( (now - last_ts) / 60 )) 分钟内已通知）: $(printf '%s' "$body" | tr '\n' '; ')"
    exit 1
fi

msg="🐕 NAS 看门狗告警（开发机）
$body
时间: $(date '+%F %T')"

if printf '%s' "$msg" | ssh "${SSH_STDIN_OPTS[@]}" "$CLOUD_HOST" "python3 $SENDER" >/dev/null 2>&1; then
    printf 'sig=%s\nts=%s\n' "$signature" "$now" > "$STATE_FILE"
    log "NOTIFIED: $(printf '%s' "$body" | tr '\n' '; ')"
else
    log "NOTIFY-FAILED（云侧发送失败，未记录去重状态）: $(printf '%s' "$body" | tr '\n' '; ')"
fi
exit 1
