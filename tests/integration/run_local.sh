#!/bin/bash
# run_local.sh — 本地运行 Phase 4 集成测试（无需 Docker）
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
export REPO_ROOT

# 自动检测 npm 全局 bin 路径（兼容 nvm）
NPM_BIN=$(npm config get prefix 2>/dev/null)/bin
[ -d "$NPM_BIN" ] && export PATH="$NPM_BIN:$PATH"

echo "=== Phase 4 集成测试 ==="
echo "Repo: $REPO_ROOT"
echo ""

# 运行测试
bats --print-output-on-failure \
    "$SCRIPT_DIR/routing.bats" \
    "$SCRIPT_DIR/hook-chain.bats" \
    "$SCRIPT_DIR/migration.bats" \
    "$SCRIPT_DIR/escape.bats" \
    "$SCRIPT_DIR/rollback.bats" \
    "$@" 2>&1

echo ""
echo "=== 完成 ==="
