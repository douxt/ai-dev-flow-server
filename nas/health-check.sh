#!/bin/bash
# Silent Observer 健康巡检 — NAS cron 每 5 分钟执行
# 调用 test_smoke.py，连续 3 次失败后重启容器，10 分钟防重启风暴锁
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

# === 部署并运行冒烟 ===
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
        $DOCKER restart langbot langbot-plugin napcat
        echo "[$(date)] restart triggered" >> "$LOG"
    fi
fi
