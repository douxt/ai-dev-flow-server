#!/bin/bash
# Silent Observer 健康巡检 — NAS cron 每 5 分钟执行
# 双通道检测：
#   A. LangRAG not found 扫描 → 立即重启（不等累计）
#   B. 烟雾测试 → 连续 3 次失败后重启
# 防重启风暴锁：10 分钟内不重复重启
set -e

DOCKER=/volume1/@appstore/ContainerManager/usr/bin/docker
LOCK=/tmp/health_lock
LOCK_TTL=600
FAIL_COUNT_FILE=/tmp/health_fail_count
LOG=/tmp/health_check.log
PROJECT_DIR=/volume1/docker/langbot

now=$(date +%s)

# === 防重启风暴 ===
if [ -f "$LOCK" ]; then
    last=$(cat "$LOCK")
    if [ $((now - last)) -lt $LOCK_TTL ]; then
        echo "[$(date)] locked (last restart: $(date -d @"$last" 2>/dev/null || date -r "$last" 2>/dev/null))" >> "$LOG"
        exit 0
    fi
fi

# ═══════════════════════════════════════════════════════════════
# 通道 A：LangRAG "not found" 扫描（5 分钟窗口）
# ═══════════════════════════════════════════════════════════════

NOT_FOUND_COUNT=$($DOCKER logs langbot-plugin --since 5m 2>&1 | grep -c "Plugin.*not found" || true)
NOT_FOUND_MAIN=$($DOCKER logs langbot --since 5m 2>&1 | grep -c "Plugin.*not found" || true)
NOT_FOUND_COUNT=$((NOT_FOUND_COUNT + NOT_FOUND_MAIN))

if [ "$NOT_FOUND_COUNT" -gt 0 ]; then
    echo "[$(date)] ⚠️ LangRAG not found × ${NOT_FOUND_COUNT}，触发立即重启" >> "$LOG"
    echo "$now" > "$LOCK"
    rm -f "$FAIL_COUNT_FILE"

    $DOCKER restart langbot >> "$LOG" 2>&1
    echo "[$(date)] langbot restarted, waiting 50s for healthy..." >> "$LOG"
    sleep 50

    $DOCKER restart langbot-plugin >> "$LOG" 2>&1
    echo "[$(date)] langbot-plugin restarted, waiting 15s..." >> "$LOG"
    sleep 15

    $DOCKER restart napcat >> "$LOG" 2>&1
    echo "[$(date)] napcat restarted, recovery complete" >> "$LOG"
    exit 0
fi

# ═══════════════════════════════════════════════════════════════
# 通道 B：烟雾测试（3 次累计失败 → 重启）
# ═══════════════════════════════════════════════════════════════

scp -q "$PROJECT_DIR/tests/test_smoke.py" /tmp/test_smoke.py 2>/dev/null || true
$DOCKER cp /tmp/test_smoke.py napcat:/tmp/ 2>/dev/null || true
timeout 90 $DOCKER exec napcat python3 /tmp/test_smoke.py >> "$LOG" 2>&1
exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo "[$(date)] OK" >> "$LOG"
    rm -f "$FAIL_COUNT_FILE"
else
    fails=$(cat "$FAIL_COUNT_FILE" 2>/dev/null || echo 0)
    fails=$((fails + 1))
    echo "$fails" > "$FAIL_COUNT_FILE"
    echo "[$(date)] FAIL #$fails (exit=$exit_code)" >> "$LOG"

    if [ "$fails" -ge 3 ]; then
        echo "[$(date)] threshold reached, restarting containers" >> "$LOG"
        echo "$now" > "$LOCK"
        rm -f "$FAIL_COUNT_FILE"

        $DOCKER restart langbot >> "$LOG" 2>&1
        sleep 50
        $DOCKER restart langbot-plugin >> "$LOG" 2>&1
        sleep 15
        $DOCKER restart napcat >> "$LOG" 2>&1
        echo "[$(date)] restart triggered" >> "$LOG"
    fi
fi
