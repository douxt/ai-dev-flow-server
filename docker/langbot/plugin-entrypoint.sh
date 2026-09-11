#!/bin/bash
# 等待 LangBot 完全就绪再启动插件运行时
# 解决两个问题：
# 1. NAS 重启后 Docker 同时启动容器，无视 compose 依赖顺序
# 2. 端口监听 ≠ DB 就绪——LangBot 端口 open 后 DB 迁移可能还在跑

MAX_WAIT=120
INTERVAL=2
POST_READY_DELAY=10  # 端口就绪后额外等待，确保 DB 迁移完成
ELAPSED=0

echo "[plugin-entrypoint] Waiting for LangBot API (http://langbot:5300)..."

while true; do
    if echo >/dev/tcp/langbot/5300 2>/dev/null; then
        echo "[plugin-entrypoint] LangBot API port ready after ${ELAPSED}s, waiting ${POST_READY_DELAY}s for DB init..."
        sleep $POST_READY_DELAY
        echo "[plugin-entrypoint] Starting plugin runtime..."
        break
    fi
    if [ $ELAPSED -ge $MAX_WAIT ]; then
        echo "[plugin-entrypoint] WARNING: LangBot not ready after ${MAX_WAIT}s, starting anyway..."
        break
    fi
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

exec "$@"
