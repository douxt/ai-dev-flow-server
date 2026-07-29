#!/bin/bash
# ===========================================================================
# watch-logs.sh — Silent Observer 实时日志监控，不用手动 SSH + grep
#
# 用法:
#   bash scripts/watch-logs.sh              # 实时 tail gate.log
#   bash scripts/watch-logs.sh --errors     # 只看 ERROR/WARNING
#   bash scripts/watch-logs.sh --metrics    # 统计：hit/miss/vision suc/fail
#   bash scripts/watch-logs.sh --inject     # 只看 memory_injector 相关（LTM 调试）
#   bash scripts/watch-logs.sh --last 50    # 查看最近 N 行（不 follow）
# ===========================================================================
set -euo pipefail

NAS="root@nas"
DOCKER="/volume1/@appstore/ContainerManager/usr/bin/docker"
GATE_LOG="/tmp/silent_gate.log"
EVENT_LOG="/tmp/silent_event.log"

RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ── 参数解析 ──────────────────────────────────────────────────
MODE="tail"
LAST_N=""
FILTER=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --errors)
            MODE="tail"
            FILTER="ERROR\|WARNING\|error\|warning\|fail\|exception"
            shift ;;
        --metrics)
            MODE="metrics"
            shift ;;
        --inject)
            MODE="tail"
            FILTER="memory_injector\|inject"
            shift ;;
        --last)
            MODE="last"
            LAST_N="$2"
            shift 2 ;;
        *)
            echo "用法: bash scripts/watch-logs.sh [--errors|--metrics|--inject|--last N]"
            exit 1 ;;
    esac
done

# ── 执行 ──────────────────────────────────────────────────────
case "$MODE" in
    metrics)
        echo -e "${CYAN}=== Gate 统计 ===${NC}"
        ssh "$NAS" "$DOCKER exec langbot-plugin sh -c \"
            total=\$(grep -c 'gate:' $GATE_LOG 2>/dev/null || echo 0)
            hit=\$(grep -c 'gate:.*hit' $GATE_LOG 2>/dev/null || echo 0)
            miss=\$(grep -c 'gate:.*miss' $GATE_LOG 2>/dev/null || echo 0)
            allowed=\$(grep -c 'gate: allowed' $GATE_LOG 2>/dev/null || echo 0)
            prevented=\$(grep -c 'gate: prevented' $GATE_LOG 2>/dev/null || echo 0)
            echo \\\"  gate 事件: \$total (hit: \$hit, miss: \$miss)\\\"
            echo \\\"  放行: \$allowed  拦截: \$prevented\\\"
        \""

        echo ""
        echo -e "${CYAN}=== Inject 统计 ===${NC}"
        ssh "$NAS" "$DOCKER exec langbot-plugin sh -c \"
            inject_start=\$(grep -c 'inject START' $GATE_LOG 2>/dev/null || echo 0)
            inject_done=\$(grep -c 'inject DONE' $GATE_LOG 2>/dev/null || echo 0)
            inject_error=\$(grep -c 'inject ERROR\|inject.*error' $GATE_LOG 2>/dev/null || echo 0)
            echo \\\"  inject 触发: \$inject_start, 完成: \$inject_done, 错误: \$inject_error\\\"
        \""

        echo ""
        echo -e "${CYAN}=== Vision 统计 ===${NC}"
        ssh "$NAS" "$DOCKER exec langbot-plugin sh -c \"
            vis_ok=\$(grep -c 'vision: done' $GATE_LOG 2>/dev/null || echo 0)
            vis_fail=\$(grep -c 'vision: fail' $GATE_LOG 2>/dev/null || echo 0)
            echo \\\"  vision 成功: \$vis_ok, 失败: \$vis_fail\\\"
        \""

        echo ""
        echo -e "${CYAN}=== LTM 统计 ===${NC}"
        ssh "$NAS" "$DOCKER exec langbot-plugin sh -c \"
            ltm=\$(grep -c 'memory_injector' $GATE_LOG 2>/dev/null || echo 0)
            echo \\\"  memory_injector 触发: \$ltm\\\"
        \""

        echo ""
        echo -e "${CYAN}=== Event 统计 ===${NC}"
        ssh "$NAS" "$DOCKER exec langbot-plugin sh -c \"
            events=\$(grep -c 'event:' $EVENT_LOG 2>/dev/null || echo 0)
            echo \\\"  事件总数: \$events\\\"
        \""
        ;;
    last)
        N="${LAST_N:-50}"
        echo -e "${CYAN}=== Gate Log (最近 $N 行) ===${NC}"
        if [[ -n "$FILTER" ]]; then
            ssh "$NAS" "$DOCKER exec langbot-plugin sh -c \"tail -n $N $GATE_LOG | grep -i '$FILTER' || echo '(无匹配)'\""
        else
            ssh "$NAS" "$DOCKER exec langbot-plugin tail -n "$N" "$GATE_LOG"
        fi
        ;;
    tail)
        echo -e "${YELLOW}实时监控中... Ctrl+C 退出${NC}"
        if [[ -n "$FILTER" ]]; then
            ssh "$NAS" "$DOCKER exec langbot-plugin sh -c \"tail -f $GATE_LOG\" 2>&1" | grep --color=always -i "$FILTER" || true
        else
            ssh "$NAS" "$DOCKER exec langbot-plugin tail -f "$GATE_LOG"
        fi
        ;;
esac
