#!/bin/bash
# 本地入口 → ssh NAS → docker cp 烟雾测试 → 执行 → 回报结果
set -euo pipefail
NAS="root@nas"
TEST_FILE="$(dirname "$0")/test_deploy_smoke.py"

echo "=== 上传烟雾测试 ==="
scp "$TEST_FILE" "$NAS:/tmp/test_deploy_smoke.py"
ssh "$NAS" "docker cp /tmp/test_deploy_smoke.py napcat:/tmp/test_deploy_smoke.py"

echo "=== 执行烟雾测试 ==="
ssh "$NAS" "docker exec napcat python3 /tmp/test_deploy_smoke.py"
EXIT=$?

if [ $EXIT -eq 0 ]; then
    echo "✅ 烟雾测试全部通过"
else
    echo "❌ 烟雾测试失败 (exit=$EXIT)"
    exit $EXIT
fi
