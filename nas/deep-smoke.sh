#!/bin/bash
# 深度链路冒烟（NAS 本地，cron `17 */6 * * *`）
#
# 目的：补回"业务能跑通"这一层覆盖——巡检探针只证进程/端口/心跳活着，
#       证明不了 KB 检索、pipeline、LLM 是否还能出结果。
# 内容：跑 nas/deep-canary.py（最小金丝雀：napcat 在线 + /sync code=0 + 回复非空）。
#       完整 8 场景套件（tests/scripts/test_deploy_smoke.py）仍在部署后人工跑，
#       不进 cron——多场景串行会被会话占用（409）干扰且总时长不可控。
# 频率：每 6 小时一次（48 次/天，对比早期设计 288 次/天降 98%）。
# 策略：只告警、不重启（LLM 抖动不是服务故障）；失败写 state/alert（1 小时去重）。
#
# 部署：本文件 → NAS `/volume1/docker/langbot/deep-smoke.sh`
#       `tests/scripts/test_deploy_smoke.py` → NAS `/volume1/docker/langbot/tests/deep-smoke.py`
set -uo pipefail

DOCKER=/volume1/@appstore/ContainerManager/usr/bin/docker
STATE_DIR=/volume1/docker/langbot/state
SCRIPT=/volume1/docker/langbot/tests/deep-canary.py
LOG=/tmp/deep_smoke.log
ALERT_FILE=$STATE_DIR/alert
ALERT_STATE_FILE=$STATE_DIR/alert.last
DEDUP_TTL=${DS_DEDUP_TTL:-3600}
LOG_KEEP_LINES=300

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
    if [ -f "$ALERT_STATE_FILE" ]; then
        last=$(awk -v t="$type" '$1==t {v=$2} END{print v}' "$ALERT_STATE_FILE" 2>/dev/null || true)
    fi
    case "$last" in ''|*[!0-9]*) last=0 ;; esac
    [ $((now - last)) -lt "$DEDUP_TTL" ] && return 0
    { grep -v "^${type} " "$ALERT_STATE_FILE" 2>/dev/null || true; echo "${type} ${now}"; } \
        > "$ALERT_STATE_FILE.tmp" 2>/dev/null && mv "$ALERT_STATE_FILE.tmp" "$ALERT_STATE_FILE"
    printf '%s|%s|%s\n' "$now" "$type" "$detail" >> "$ALERT_FILE"
    log "ALERT ${type} ${detail}"
    return 0
}

# === 前置条件 ===
if [ ! -x "$DOCKER" ]; then
    log "SKIP docker-missing"
    exit 0
fi
if [ ! -f "$SCRIPT" ]; then
    log "SKIP smoke-script-missing path=$SCRIPT"
    raise_alert "deep-smoke-missing" "path=${SCRIPT}"
    exit 0
fi

# === 运行（拷入 napcat 容器执行：脚本内的 localhost:3000 是 napcat 自身）===
if ! timeout 20 "$DOCKER" cp "$SCRIPT" napcat:/tmp/deep-canary.py >/dev/null 2>&1; then
    log "FAIL docker-cp (napcat)"
    raise_alert "deep-smoke-fail" "stage=docker-cp"
    exit 1
fi

out=$(timeout 150 "$DOCKER" exec napcat python3 /tmp/deep-canary.py 2>&1)
rc=$?
printf '%s\n' "$out" >> "$LOG"

if [ "$rc" -eq 0 ]; then
    log "OK rc=0"
    exit 0
fi

fail_lines=$(printf '%s\n' "$out" | grep -cE '❌|FAIL|Traceback' 2>/dev/null || true)
log "FAIL rc=${rc} fail_lines=${fail_lines:-0}"
raise_alert "deep-smoke-fail" "rc=${rc} fail_lines=${fail_lines:-0}"
exit 1
