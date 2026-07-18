#!/bin/bash
# 一键部署 silent-observer 到 NAS Docker
# 用法: ./deploy.sh           # 部署 + 烟雾测试
#       ./deploy.sh --no-test  # 只部署，不测试
set -euo pipefail

NAS="root@nas"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NAS_VOL="/volume1/docker/langbot/data/plugins/dou__langbot-silent-observer"
DOCKER="/volume1/@appstore/ContainerManager/usr/bin/docker"

echo "=== 1. 上传代码 ==="
scp "$SCRIPT_DIR/components/event_listener/default.py" "$NAS:$NAS_VOL/components/event_listener/"
scp "$SCRIPT_DIR/main.py" "$NAS:$NAS_VOL/"

echo "=== 2. 清除 __pycache__ ==="
ssh "$NAS" "\$DOCKER exec langbot-plugin sh -c 'find /app/data/plugins/dou__langbot-silent-observer -name __pycache__ -exec rm -rf {} +'"

echo "=== 3. 重启容器 ==="
ssh "$NAS" "\$DOCKER restart langbot-plugin && sleep 2 && \$DOCKER restart langbot"

echo "=== 4. 等待启动 ==="
sleep 8
ssh "$NAS" "\$DOCKER exec langbot-plugin cat /tmp/silent_init.log" | tail -3

if [ "${1:-}" != "--no-test" ]; then
    echo "=== 5. 烟雾测试 ==="
    bash "$SCRIPT_DIR/tests/run_smoke.sh"
fi

echo "✅ 部署完成"
