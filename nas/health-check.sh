#!/bin/bash
# Silent Observer 健康巡检 — NAS cron 每 5 分钟执行
#
# 探针（五项零副作用、零 LLM 调用，任一项失败 → 计入重启阈值）：
#   ① 插件心跳 /tmp/silent_stats.log 新鲜度  ② langbot 2280 端口在听
#   ③ langbot healthcheck 状态               ④ langbot HTTP 响应
#   ⑤ napcat QQ 进程存活
# 另有非重启项：napcat ↔ langbot WS 链路（link）。
#   未建连通常意味着 QQ 未登录/掉线，重启容器无用 → 只记 ACCOUNT-OFFLINE
#
# 通道 A：LangRAG "Plugin not found" 扫描（保留时间窗，出现即重启）
# 失败策略：连续 HC_FAIL_THRESHOLD（默认 3）次失败 → 按最佳实践顺序重启
#   langbot-plugin → langbot → 等端口就绪 → napcat
# 防护：flock 防重入 + 10 分钟重启防抖锁（state 目录持久化）
# 测试开关（仅本地/验证用，cron 不设置；默认值即生产路径）：
#   HC_FAIL_THRESHOLD=N  覆盖失败阈值    HC_FORCE_FAIL=1  强制五项探针失败
#   HC_DOCKER / HC_STATE_DIR / HC_LOG / HC_SCAN_FILE  覆盖路径（自测用 docker stub）
set -e

DOCKER=${HC_DOCKER:-/volume1/@appstore/ContainerManager/usr/bin/docker}
STATE_DIR=${HC_STATE_DIR:-/volume1/docker/langbot/state}
LOCK_FILE=$STATE_DIR/health.lock
FLOCK_FILE=$STATE_DIR/hc.flock
FAIL_COUNT_FILE=$STATE_DIR/health_fail_count
LOG=${HC_LOG:-/tmp/health_check.log}
SCAN_FILE=${HC_SCAN_FILE:-/tmp/hc_scan.txt}

LOCK_TTL=600          # 重启后 10 分钟内不再重启
FAIL_THRESHOLD=${HC_FAIL_THRESHOLD:-3}
FORCE_FAIL=${HC_FORCE_FAIL:-0}
HEARTBEAT_MAX=180     # 插件心跳允许的最大年龄（插件每 60s 自写）
LOG_KEEP_LINES=500    # 日志轮换上界

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

# === 防重入（cron 每 5 分钟，上一轮未结束则本轮直接退出）===
exec 9>"$FLOCK_FILE"
if ! flock -n 9; then
    log "busy: previous run still active, skip"
    exit 0
fi

# === 前置条件：docker / 目标容器不存在 → SKIP，不计失败 ===
if [ ! -x "$DOCKER" ]; then
    log "SKIP docker-missing path=$DOCKER"
    exit 0
fi
if ! timeout 15 "$DOCKER" inspect langbot langbot-plugin napcat >/dev/null 2>&1; then
    log "SKIP container-missing (langbot/langbot-plugin/napcat)"
    exit 0
fi

# === 10 分钟重启防抖 ===
now=$(date +%s)
if [ -f "$LOCK_FILE" ]; then
    last=$(cat "$LOCK_FILE" 2>/dev/null || echo 0)
    case "$last" in ''|*[!0-9]*) last=0 ;; esac
    if [ $((now - last)) -lt "$LOCK_TTL" ]; then
        log "locked (last restart ${last})"
        exit 0
    fi
fi

# === 五项探针：返回 0 通过，1 失败 ===
probe_heartbeat() {
    local age
    age=$(timeout 10 "$DOCKER" exec langbot-plugin /app/.venv/bin/python3 -c \
        "import os,time;print(int(time.time()-os.stat('/tmp/silent_stats.log').st_mtime))" 2>/dev/null) || return 1
    case "$age" in ''|*[!0-9]*) return 1 ;; esac
    [ "$age" -lt "$HEARTBEAT_MAX" ]
}

probe_port() {
    local n
    n=$(timeout 8 "$DOCKER" exec langbot sh -c 'grep -c 08E8 /proc/net/tcp' 2>/dev/null) || return 1
    case "$n" in ''|*[!0-9]*) return 1 ;; esac
    [ "$n" -ge 1 ]
}

probe_health() {
    local s
    s=$(timeout 8 "$DOCKER" inspect langbot --format '{{.State.Health.Status}}' 2>/dev/null) || return 1
    [ "$s" = "healthy" ]
}

probe_http() {
    local code
    code=$(timeout 10 "$DOCKER" exec napcat python3 -c \
        "import urllib.request;print(urllib.request.urlopen('http://langbot:5300/',timeout=5).status)" 2>/dev/null) || return 1
    [ "$code" = "200" ]
}

probe_napcat() {
    local pid
    pid=$(timeout 8 "$DOCKER" exec napcat sh -c \
        'grep -la "/opt/QQ/qq" /proc/[0-9]*/cmdline 2>/dev/null | head -1' 2>/dev/null) || return 1
    [ -n "$pid" ]
}

# 非重启项：napcat ↔ langbot 的 WS 链路。未建连通常意味着 QQ 未登录/掉线，
# 重启容器无用，需人工扫码 → 只记 ACCOUNT-OFFLINE，不计入重启阈值。
napcat_link_ok() {
    local n
    n=$(timeout 8 "$DOCKER" exec napcat sh -c 'grep -c 08E8 /proc/net/tcp' 2>/dev/null) || return 1
    case "$n" in ''|*[!0-9]*) return 1 ;; esac
    [ "$n" -ge 1 ]
}

probe_str=""
for p in probe_heartbeat probe_port probe_health probe_http probe_napcat; do
    if [ "$FORCE_FAIL" = "1" ]; then
        probe_str="${probe_str}0"
    elif $p; then
        probe_str="${probe_str}1"
    else
        probe_str="${probe_str}0"
    fi
done

# === 非重启项：napcat WS 链路（登录态）===
link=0
if napcat_link_ok; then link=1; fi
if [ "$link" = "0" ]; then
    log "ACCOUNT-OFFLINE napcat 未与 langbot:2280 建立 WS，可能未登录（需人工扫码，重启无效）"
fi

# === 重启序列（顺序与超时遵循 container-restart-best-practices.md）===
restart_sequence() {
    local reason="$1"
    echo "$(date +%s)" > "$LOCK_FILE"
    rm -f "$FAIL_COUNT_FILE"
    log "threshold reached ($reason), restart: langbot-plugin → langbot → napcat"

    timeout 60 "$DOCKER" restart langbot-plugin >>"$LOG" 2>&1 || log "WARN restart langbot-plugin failed/timed out"
    sleep 3
    timeout 90 "$DOCKER" restart langbot >>"$LOG" 2>&1 || log "WARN restart langbot failed/timed out"

    local ready=0 i=0
    for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
        if timeout 8 "$DOCKER" exec langbot sh -c 'grep -q 08E8 /proc/net/tcp' 2>/dev/null; then
            ready=1
            break
        fi
        sleep 3
    done
    log "langbot port ready=$ready (waited ~$((i * 3))s)"

    timeout 60 "$DOCKER" restart napcat >>"$LOG" 2>&1 || log "WARN restart napcat failed/timed out"
    log "restart sequence complete"
}

# === 通道 A：LangRAG not found 扫描（保留 5 分钟时间窗）===
scan_container() {
    local c="$1" n=0
    if timeout 8 "$DOCKER" logs --since 5m --tail 500 "$c" > "$SCAN_FILE" 2>&1; then
        n=$(grep -c "Plugin.*not found" "$SCAN_FILE" 2>/dev/null || true)
    else
        log "WARN log-scan failed for $c"
    fi
    echo "${n:-0}"
}

not_found=$(( $(scan_container langbot-plugin) + $(scan_container langbot) ))
if [ "$not_found" -gt 0 ]; then
    restart_sequence "langrag-not-found x${not_found}"
    log "heartbeat probe=${probe_str} link=${link} restart=1"
    exit 0
fi

# === 判定与计数 ===
if [ "$probe_str" = "11111" ]; then
    rm -f "$FAIL_COUNT_FILE"
    log "heartbeat probe=${probe_str} link=${link} restart=0"
    exit 0
fi

fails=$(cat "$FAIL_COUNT_FILE" 2>/dev/null || echo 0)
case "$fails" in ''|*[!0-9]*) fails=0 ;; esac
fails=$((fails + 1))
echo "$fails" > "$FAIL_COUNT_FILE"
log "FAIL #${fails} probe=${probe_str}"

if [ "$fails" -ge "$FAIL_THRESHOLD" ]; then
    restart_sequence "probe=${probe_str} fails=${fails}"
    log "heartbeat probe=${probe_str} link=${link} restart=1"
    exit 0
fi

log "heartbeat probe=${probe_str} link=${link} restart=0"
