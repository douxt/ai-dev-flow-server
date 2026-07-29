#!/bin/bash
# 一键部署 silent-observer 到 NAS Docker
# 用法: ./deploy.sh              # 部署 + 烟雾测试
#       ./deploy.sh --no-test     # 只部署，不测试
#       ./deploy.sh --verify      # 部署 + 自动验证（含 LTM）
#       ./deploy.sh --verify-ltm  # 部署 + 仅 LTM 验证
set -euo pipefail

NAS="root@nas"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NAS_VOL="/volume1/docker/langbot/data/plugins/dou__langbot-silent-observer"
DOCKER="/volume1/@appstore/ContainerManager/usr/bin/docker"

echo "=== 1. 上传代码 ==="
# 打包上传完整插件目录，NAS 端解压（保留目录结构）
tar -czf /tmp/so-deploy.tar.gz \
  -C "$SCRIPT_DIR" \
  main.py manifest.yaml \
  components/ store/ service/ util/
scp /tmp/so-deploy.tar.gz "$NAS:/tmp/"
ssh "$NAS" "tar -xzf /tmp/so-deploy.tar.gz -C $NAS_VOL && rm /tmp/so-deploy.tar.gz"
rm -f /tmp/so-deploy.tar.gz

echo "=== 2. 清除 __pycache__ ==="
ssh "$NAS" "$DOCKER exec langbot-plugin sh -c 'find /app/data/plugins/dou__langbot-silent-observer -name __pycache__ -exec rm -rf {} +'"

echo "=== 3. 重启容器 ==="
ssh "$NAS" "$DOCKER restart langbot-plugin && sleep 2 && $DOCKER restart langbot"

echo "=== 4. 等待启动 ==="
sleep 15
ssh "$NAS" "$DOCKER exec langbot-plugin cat /tmp/silent_init.log" | tail -3

if [ "${1:-}" == "--verify" ]; then
    echo "=== 5. 自动验证（全场景） ==="
    bash "$SCRIPT_DIR/scripts/verify-fix.sh"
elif [ "${1:-}" == "--verify-ltm" ]; then
    echo "=== 5. 自动验证（LTM 专项） ==="
    bash "$SCRIPT_DIR/scripts/verify-fix.sh --ltm"
elif [ "${1:-}" == "--verify-quick" ]; then
    echo "=== 5. 自动验证（快速） ==="
    bash "$SCRIPT_DIR/scripts/verify-fix.sh --quick"
elif [ "${1:-}" != "--no-test" ]; then
    echo "=== 5. 烟雾测试 ==="
    bash "$SCRIPT_DIR/tests/run_smoke.sh"
fi

echo "✅ 部署完成"
