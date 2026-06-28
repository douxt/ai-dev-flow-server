#!/bin/bash
# status.sh — AFK 管线统一仪表盘
# 用法: bash .devflow/scripts/status.sh [--watch]
set -euo pipefail

WORKSPACE="$(cd "$(dirname "$0")/../.." && pwd)"
GATE_FILE="$WORKSPACE/.gate-state"
ISSUES_DIR="$WORKSPACE/issues"
DISPATCH_LOG="$WORKSPACE/logs/dispatch.log"
RECONCILE_LOG="$WORKSPACE/logs/reconcile.log"

BOLD="\033[1m"
GREEN="\033[32m"
RED="\033[31m"
YELLOW="\033[33m"
CYAN="\033[36m"
RESET="\033[0m"

icon() {
    case "$1" in
        passed|done|active)   echo -e "${GREEN}✅${RESET}" ;;
        failed|inactive)       echo -e "${RED}❌${RESET}" ;;
        in_progress|in_review) echo -e "${YELLOW}🔄${RESET}" ;;
        pending|backlog)       echo -e "${CYAN}⬜${RESET}" ;;
        *)                     echo -e "${CYAN}⬜${RESET}" ;;
    esac
}

# ── Header ──
echo -e "${BOLD}┌─ Pipeline Status $(date '+%Y-%m-%d %H:%M') ─────────────────┐${RESET}"

# ── Timers ──
PROJECT=$(grep -oP 'project:\s*\K\w+' "$WORKSPACE/.devflow/config.yaml" 2>/dev/null || echo "")
if [ -n "$PROJECT" ]; then
    DISPATCH_TIMER=$(systemctl is-active "dispatch-${PROJECT}.timer" 2>/dev/null || echo "inactive")
    RECONCILE_TIMER=$(systemctl is-active "reconcile-${PROJECT}.timer" 2>/dev/null || echo "inactive")
else
    DISPATCH_TIMER=$(systemctl list-units --type=timer --all --no-legend 2>/dev/null | grep -oP 'dispatch-\S+\.timer' | head -1 | xargs systemctl is-active 2>/dev/null || echo "inactive")
    RECONCILE_TIMER=$(systemctl list-units --type=timer --all --no-legend 2>/dev/null | grep -oP 'reconcile-\S+\.timer' | head -1 | xargs systemctl is-active 2>/dev/null || echo "inactive")
fi
echo -e "│ Timers: dispatch $(icon $DISPATCH_TIMER)  reconcile $(icon $RECONCILE_TIMER)                   │"

# ── Gates ──
GATES=""
for g in gate-1 gate-2 gate-3 gate-4 gate-5 gate-6; do
    STATUS=$(grep "$g:" "$GATE_FILE" 2>/dev/null | grep -oP 'status:\s*\K\w+' || echo "pending")
    GATES="$GATES $g$(icon $STATUS)"
done
echo -e "│ Gates: $GATES                                   │"

# ── Issues ──
echo -e "├─ Issues ───────────────────────────────────────────────┤"
for f in "$ISSUES_DIR"/0*.md; do
    [ -f "$f" ] || continue
    BASENAME=$(basename "$f")
    NUM=$(echo "$BASENAME" | cut -d- -f1)
    STATUS=$(grep "^status:" "$f" | awk '{print $2}')
    TYPE=$(grep "^type:" "$f" | awk '{print $2}')
    ESTIMATE=$(grep "^estimate:" "$f" | awk '{print $2}')
    BLOCKED=$(grep "^blocked_by:" "$f" | grep -oP '\[.*?\]' | tr -d '[]' | sed 's/"//g' || echo "")

    # Check blocked status
    BLOCK_ICON=""
    if [ -n "$BLOCKED" ] && [ "$BLOCKED" != " " ]; then
        ALL_DONE=true
        for dep in $(echo "$BLOCKED" | tr ',' ' '); do
            [ -z "$dep" ] && continue
            DEP_FILE=$(find "$ISSUES_DIR" -name "${dep}-*.md" -exec grep -l "^status: done$" {} \; 2>/dev/null | head -1)
            [ -z "$DEP_FILE" ] && ALL_DONE=false && break
        done
        if [ "$ALL_DONE" = true ]; then
            BLOCK_ICON=" ${GREEN}→auto-ready${RESET}"
        fi
    fi

    printf "│ ${BOLD}#%-4s${RESET} %-10s %-4s %-5s %s${BLOCK_ICON}\n" \
        "$NUM" "$(icon $STATUS) $STATUS" "$TYPE" "$ESTIMATE" ""
done

# ── Recent Activity ──
echo -e "├─ Recent Dispatch ──────────────────────────────────────┤"
tail -4 "$DISPATCH_LOG" 2>/dev/null | grep -v "^$" | while IFS= read -r line; do
    echo "│ $(echo "$line" | cut -c 1-52)"
done

echo -e "├─ Recent Reconcile ─────────────────────────────────────┤"
tail -2 "$RECONCILE_LOG" 2>/dev/null | grep -v "^$" | while IFS= read -r line; do
    echo "│ $(echo "$line" | cut -c 1-52)"
done

# ── Git ──
echo -e "├─ Git ──────────────────────────────────────────────────┤"
git -C "$WORKSPACE" log --oneline -5 2>/dev/null | while IFS= read -r line; do
    echo "│ $(echo "$line" | cut -c 1-52)"
done

echo -e "${BOLD}└────────────────────────────────────────────────────────┘${RESET}"
