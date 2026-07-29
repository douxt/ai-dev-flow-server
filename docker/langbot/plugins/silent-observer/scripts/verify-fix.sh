#!/bin/bash
# ===========================================================================
# verify-fix.sh — Silent Observer 一键验证，修完代码 30s 知道结果
#
# 用法:
#   bash scripts/verify-fix.sh              # 全部场景
#   bash scripts/verify-fix.sh --quick      # 仅 L1+L2 快速确认
#   bash scripts/verify-fix.sh --ltm        # 仅 LTM 专项
#   bash scripts/verify-fix.sh --scene face # 跑单个场景
# ===========================================================================
set -euo pipefail

NAS="root@nas"
DOCKER="/volume1/@appstore/ContainerManager/usr/bin/docker"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VERIFY_PY="$SCRIPT_DIR/../tests/verify_core.py"
PARSE_PY="$SCRIPT_DIR/_parse_result.py"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[verify]${NC} $*"; }
warn() { echo -e "${YELLOW}[verify]${NC} $*"; }
err()  { echo -e "${RED}[verify]${NC} $*"; }

# ── 参数解析 ──────────────────────────────────────────────────
SCENE_ARGS=""
VERIFY_MODE="all"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --quick)
            SCENE_ARGS="--scene connectivity --scene core"
            VERIFY_MODE="quick"
            shift ;;
        --ltm)
            SCENE_ARGS="--scene ltm"
            VERIFY_MODE="ltm"
            shift ;;
        --scene)
            SCENE_ARGS="--scene $2"
            VERIFY_MODE="$2"
            shift 2 ;;
        --all)
            SCENE_ARGS=""
            VERIFY_MODE="all"
            shift ;;
        *)
            err "未知参数: $1"
            echo "用法: bash scripts/verify-fix.sh [--quick|--ltm|--scene <name>|--all]"
            exit 1 ;;
    esac
done

# ── 容器就绪探测 ──────────────────────────────────────────────
log "容器就绪探测..."
PROBE_START=$(date +%s)
PROBE_TIMEOUT=60
READY=false

while true; do
    ELAPSED=$(( $(date +%s) - PROBE_START ))
    if [[ $ELAPSED -ge $PROBE_TIMEOUT ]]; then
        break
    fi

    PROBE_CMD="$DOCKER exec napcat curl -s -o /dev/null -w '%{http_code}' http://langbot:5300/ --connect-timeout 3 --max-time 5"
    STATUS=$(ssh "$NAS" "$PROBE_CMD 2>/dev/null" || echo 000)

    if [[ "$STATUS" != "000" ]]; then
        READY=true
        break
    fi
    sleep 2
done

if [[ "$READY" != "true" ]]; then
    err "容器未就绪（${PROBE_TIMEOUT}s 超时），请检查 langbot 状态"
    exit 1
fi
log "容器就绪 (${STATUS})"

# ── 上传并执行验证脚本 ────────────────────────────────────────
log "上传 verify_core.py 到 langbot-plugin 容器..."
if ! scp -q "$VERIFY_PY" "$NAS:/tmp/verify_core_tmp.py"; then
    err "上传失败"
    exit 1
fi
if ! ssh "$NAS" "$DOCKER cp /tmp/verify_core_tmp.py langbot-plugin:/tmp/verify_core.py"; then
    err "docker cp 失败"
    exit 1
fi

log "执行验证 (mode=$VERIFY_MODE)..."
echo ""

# 在 langbot-plugin 容器内执行（可访问 langbot:5300 + 可读 gate log）
RESULT=$(ssh "$NAS" "$DOCKER exec langbot-plugin python3 /tmp/verify_core.py --json $SCENE_ARGS 2>&1") || true

# ── 解析结果 ──────────────────────────────────────────────────
if echo "$RESULT" | python3 "$PARSE_PY" check 2>/dev/null; then
    PASSED=$(echo "$RESULT" | python3 "$PARSE_PY" passed)
    TOTAL=$(echo "$RESULT" | python3 "$PARSE_PY" total)
    ELAPSED=$(echo "$RESULT" | python3 "$PARSE_PY" elapsed)
    echo ""
    log "✅ ${PASSED}/${TOTAL} 通过 (${ELAPSED}s)"
    exit 0
else
    echo "$RESULT" | python3 "$PARSE_PY" summary 2>/dev/null || echo "$RESULT"
    exit 1
fi
