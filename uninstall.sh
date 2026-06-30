#!/bin/bash
# uninstall.sh — 从目标项目移除 ai-dev-flow-server
# 用法: bash uninstall.sh <项目路径> [选项]
set -euo pipefail

TARGET=""
MODE="full"
HOME_OVERRIDE=""
USER_OVERRIDE=""
SCHEDULER=""
DRY_RUN=false
FORCE=false

while [ $# -gt 0 ]; do
    case "$1" in
        --mode)      MODE="$2"; shift 2 ;;
        --home)      HOME_OVERRIDE="$2"; shift 2 ;;
        --user)      USER_OVERRIDE="$2"; shift 2 ;;
        --scheduler) SCHEDULER="$2"; shift 2 ;;
        --dry-run)   DRY_RUN=true; shift ;;
        --force)     FORCE=true; shift ;;
        --help)
            echo "用法: bash uninstall.sh <项目路径> [选项]"
            echo ""
            echo "选项:"
            echo "  --mode frontend|backend|full  仅移除指定模式的组件（默认 full）"
            echo "  --home <path>                覆盖 \$HOME"
            echo "  --user <name>                调度器运行用户"
            echo "  --scheduler systemd|cron     调度器类型（默认自动检测）"
            echo "  --dry-run                    预览模式"
            echo "  --force                      跳过确认提示"
            echo "  --help                       显示此帮助"
            exit 0 ;;
        *) TARGET="$1"; shift ;;
    esac
done

if [ -z "$TARGET" ]; then
    echo "❌ 需要指定目标项目路径"; echo "用法: bash uninstall.sh <项目路径> [选项]"; exit 1
fi

case "$MODE" in frontend|backend|full) ;; *)
    echo "❌ 无效 --mode: $MODE（可选: frontend, backend, full）"; exit 1 ;; esac

TARGET=$(realpath "$TARGET" 2>/dev/null || echo "$TARGET")
CLAUDE_HOME="${HOME_OVERRIDE:-$HOME}"
PROJECT=$(basename "$TARGET")

FRONTEND=false; BACKEND=false
case "$MODE" in
    frontend) FRONTEND=true ;;
    backend)  BACKEND=true ;;
    full)     FRONTEND=true; BACKEND=true ;;
esac

# 自动检测调度器
if [ -z "$SCHEDULER" ]; then
    if [ -f /.dockerenv ] || grep -q 'docker\|lxc' /proc/1/cgroup 2>/dev/null; then
        SCHEDULER="none"
    elif [ -d /run/systemd/system ]; then
        SCHEDULER="systemd"
    elif command -v crontab >/dev/null 2>&1; then
        SCHEDULER="cron"
    else
        SCHEDULER="none"
    fi
fi

dry_run() { if [ "$DRY_RUN" = true ]; then echo "  [DRY-RUN] $*"; else eval "$@"; fi; }

echo "⚠️  将从 $TARGET 移除 ai-dev-flow-server"
echo "   项目: $PROJECT"
echo "   模式: $MODE (frontend=$FRONTEND, backend=$BACKEND)"
[ "$DRY_RUN" = true ] && echo "  ⚠️  DRY-RUN 模式：只预览，不实际删除"

if [ "$DRY_RUN" = false ] && [ "$FORCE" != true ]; then
    echo ""
    read -rp "确认继续？(y/N) " CONFIRM
    [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ] && echo "已取消" && exit 0
fi

echo ""
echo "── 用户段清理 ──"

# 1. 移除 gate 脚本（frontend + full）
if [ "$FRONTEND" = true ]; then
    echo "1. 移除 gate 脚本..."
    for js in gate-1-grill gate-2-prd gate-3-issues gate-4-review gate-5-prep gate-6-afk; do
        f="$CLAUDE_HOME/.claude/workflows/${js}.js"
        if [ -f "$f" ]; then
            dry_run "rm -f $f"
            [ "$DRY_RUN" = false ] && rm -f "$f"
        fi
    done
    echo "  ✅ gate 脚本已移除"

    # 1b. 移除 CC skills（frontend + full）
    echo "1b. 移除 CC skills..."
    SKILLS_DIR="$CLAUDE_HOME/.claude/skills"
    KNOWN_SKILLS="caveman diagnose grill-me grill-with-docs handoff improve-codebase-architecture prototype review-cc-cli setup-matt-pocock-skills tdd to-issues to-prd triage write-a-skill zoom-out"
    if [ -d "$SKILLS_DIR" ]; then
        for s in $KNOWN_SKILLS; do
            if [ -d "$SKILLS_DIR/$s" ]; then
                dry_run "rm -rf $SKILLS_DIR/$s"
                [ "$DRY_RUN" = false ] && rm -rf "$SKILLS_DIR/$s"
            fi
        done
        echo "  ✅ CC skills 已移除"
    else
        echo "  ⚠️  skills/ 不存在"
    fi

    # 1c. 移除 CC config（settings + hooks）— frontend + full
    echo "1c. 移除 CC config..."
    # settings.local.json — 仅当含 devflow 占位符标记时删除（安全策略：不删用户自定义配置）
    SETTINGS_FILE="$CLAUDE_HOME/.claude/settings.local.json"
    if [ -f "$SETTINGS_FILE" ] && grep -q '"ai-dev-flow-server"' "$SETTINGS_FILE" 2>/dev/null; then
        dry_run "rm -f $SETTINGS_FILE"
        [ "$DRY_RUN" = false ] && rm -f "$SETTINGS_FILE"
        echo "  ✅ settings.local.json 已移除"
    elif [ -f "$SETTINGS_FILE" ]; then
        echo "  ⚠️  settings.local.json 含自定义配置，保留不删"
    fi
    # 4 个 hook
    for h in file-guard.sh bash-firewall.sh block-enter-worktree.sh audit-log.sh; do
        hf="$CLAUDE_HOME/.claude/hooks/$h"
        if [ -f "$hf" ]; then
            dry_run "rm -f $hf"
            [ "$DRY_RUN" = false ] && rm -f "$hf"
        fi
    done
    echo "  ✅ hooks 已移除"
fi

# 2. 移除 .devflow/（按 mode 部分删）
echo "2. 移除 .devflow/ ..."
if [ -d "$TARGET/.devflow" ]; then
    if [ "$BACKEND" = true ] && [ "$FRONTEND" = true ]; then
        # full — 整个删
        dry_run "rm -rf $TARGET/.devflow"
        [ "$DRY_RUN" = false ] && rm -rf "$TARGET/.devflow"
        echo "  ✅ .devflow/ 已删除"
    elif [ "$BACKEND" = true ]; then
        # backend only — 保留 knowledge/
        dry_run "rm -rf $TARGET/.devflow/archon $TARGET/.devflow/scripts"
        [ "$DRY_RUN" = false ] && rm -rf "$TARGET/.devflow/archon" "$TARGET/.devflow/scripts" 2>/dev/null || true
        echo "  ✅ .devflow/archon + scripts 已删除（knowledge/ 保留）"
    elif [ "$FRONTEND" = true ]; then
        # frontend only — 保留 archon/ + scripts/
        dry_run "rm -rf $TARGET/.devflow/knowledge"
        [ "$DRY_RUN" = false ] && rm -rf "$TARGET/.devflow/knowledge" 2>/dev/null || true
        echo "  ✅ .devflow/knowledge 已删除（archon/ + scripts/ 保留）"
    fi
else
    echo "  ⚠️  .devflow/ 不存在"
fi

# 3. 移除 .gate-state（frontend + full）
if [ "$FRONTEND" = true ]; then
    echo "3. 移除 .gate-state..."
    if [ -f "$TARGET/.gate-state" ]; then
        dry_run "rm -f $TARGET/.gate-state"
        [ "$DRY_RUN" = false ] && rm -f "$TARGET/.gate-state"
        echo "  ✅ .gate-state 已删除"
    else
        echo "  ⚠️  .gate-state 不存在"
    fi
fi

# 4. 清理 CLAUDE.md
echo "4. 清理 CLAUDE.md..."
for md in "$TARGET/.claude/CLAUDE.md" "$TARGET/CLAUDE.md"; do
    if [ -f "$md" ] && grep -q "ai-dev-flow-server" "$md" 2>/dev/null; then
        dry_run "sed -i '/<!-- ⚠️ 以下由 ai-dev-flow-server/,/<!-- ai-dev-flow-server end -->/d' $md"
        if [ "$DRY_RUN" = false ]; then
            sed -i '/<!-- ⚠️ 以下由 ai-dev-flow-server/,/<!-- ai-dev-flow-server end -->/d' "$md"
            echo "  ✅ $md 已清理"
        fi
    fi
done

# 5. 移除 .archon/workflows/（backend + full）
if [ "$BACKEND" = true ]; then
    echo "5. 移除 .archon/workflows/ ..."
    if [ -d "$TARGET/.archon/workflows" ]; then
        dry_run "rm -rf $TARGET/.archon/workflows"
        [ "$DRY_RUN" = false ] && rm -rf "$TARGET/.archon/workflows"
        echo "  ✅ .archon/workflows/ 已删除"
    fi
    # 清理空 .archon/
    if [ -d "$TARGET/.archon" ]; then
        [ "$DRY_RUN" = false ] && rmdir "$TARGET/.archon" 2>/dev/null || true
    fi

    echo "5b. 移除 logs/ ..."
    if [ -d "$TARGET/logs" ]; then
        dry_run "rm -rf $TARGET/logs"
        [ "$DRY_RUN" = false ] && rm -rf "$TARGET/logs"
        echo "  ✅ logs/ 已删除"
    fi
fi

echo ""
echo "── root 段（请以 root 身份执行）──"
echo ""

case "$SCHEDULER" in
    systemd)
        echo "# 停止并移除 systemd timer"
        echo "systemctl stop dispatch-${PROJECT}.timer reconcile-${PROJECT}.timer 2>/dev/null || true"
        echo "systemctl disable dispatch-${PROJECT}.timer reconcile-${PROJECT}.timer 2>/dev/null || true"
        echo "rm -f /etc/systemd/system/dispatch-${PROJECT}.service /etc/systemd/system/dispatch-${PROJECT}.timer"
        echo "rm -f /etc/systemd/system/reconcile-${PROJECT}.service /etc/systemd/system/reconcile-${PROJECT}.timer"
        echo "systemctl daemon-reload"
        ;;
    cron)
        CRON_USER="${USER_OVERRIDE:-$(whoami)}"
        echo "# 移除 crontab 条目"
        echo "crontab -u ${CRON_USER} -l 2>/dev/null | grep -v 'dispatch.sh\|reconciler.sh' | crontab -u ${CRON_USER} -"
        echo "echo '✅ crontab 已清理'"
        ;;
    external)
        echo "# 请在宿主机移除调度器配置"
        echo "# 删除 docker exec 定时任务（dispatch + reconcile）"
        ;;
    none)
        echo "# 无调度器需清理"
        ;;
esac

echo ""
echo "══════════════════════════════════════"
echo "用户段清理完成。执行 root 段后彻底移除。"
echo "══════════════════════════════════════"
