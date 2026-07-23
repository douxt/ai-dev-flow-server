#!/bin/bash
# install.sh — ai-dev-flow-server 通用安装器
# 用法: bash install.sh <项目路径> [选项]
set -euo pipefail

# ── 默认值 ──
TARGET=""
TECH_STACK=""
TEST_CMD=""
LINT_CMD=""
PKG_MGR=""
UPDATE_MODE=false
MODE="full"
HOME_OVERRIDE=""
USER_OVERRIDE=""
SCHEDULER=""
NO_CONFIG=false
NO_SKILLS=false
SKIP_ROOT=false
DRY_RUN=false
FORCE=false
ROLE="agent-b"
ROLE_SET=false

# ── 函数定义 ──
dry_run() { if [ "$DRY_RUN" = true ]; then echo "  [DRY-RUN] $*"; else eval "$@"; fi; }

maybe_cp() {
    local src="$1" dst="$2"
    if [ "$DRY_RUN" = true ]; then echo "  [DRY-RUN] cp $(basename "$src") → $dst"; return 0; fi
    if [ -f "$dst" ] && [ "$FORCE" != true ]; then echo "  ⚠️  $dst 已存在，跳过（--force 可强制覆盖）"; return 0; fi
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst" && echo "  ✅ $(basename "$dst")"
}

maybe_cp_dir() {
    local src="$1" dstdir="$2"
    if [ "$DRY_RUN" = true ]; then echo "  [DRY-RUN] cp $src/* → $dstdir/"; return 0; fi
    mkdir -p "$dstdir"
    local copied=0
    for f in "$src"/*; do
        [ -f "$f" ] || continue
        local dst="$dstdir/$(basename "$f")"
        if [ -f "$dst" ] && [ "$FORCE" != true ]; then echo "  ⚠️  $(basename "$dst") 已存在，跳过"; continue; fi
        cp "$f" "$dst" && copied=$((copied + 1))
    done
    echo "  ✅ $dstdir/ ($copied files)"
}

maybe_mkdir() {
    if [ "$DRY_RUN" = true ]; then echo "  [DRY-RUN] mkdir -p $1"; return 0; fi
    [ -d "$1" ] && [ "$FORCE" != true ] && return 0
    mkdir -p "$1"
}

detect_environment() {
    IS_DOCKER=false; HAS_SYSTEMD=false; HAS_CRON=false
    if [ -f /.dockerenv ] || grep -q 'docker\|lxc' /proc/1/cgroup 2>/dev/null; then IS_DOCKER=true; fi
    if [ "$IS_DOCKER" = false ] && [ -d /run/systemd/system ]; then HAS_SYSTEMD=true; fi
    if command -v crontab >/dev/null 2>&1; then HAS_CRON=true; fi
}

merge_settings_local() {
    local existing="$CLAUDE_HOME/.claude/settings.local.json"
    local template="$SOURCE/config-templates/default/settings.json"
    local claude_dir="$CLAUDE_HOME/.claude"
    if [ ! -f "$existing" ]; then
        sed "s|__PKG_MGR__|$PKG_MGR|g; s|__TEST_CMD__|$TEST_CMD|g; s|__LINT_CMD__|$LINT_CMD|g; s|__WORKSPACE__|$WORKSPACE|g; s|__CLAUDE_HOME__|$claude_dir|g" "$template" > "$existing"
        return
    fi
    local processed
    processed=$(mktemp)
    sed "s|__PKG_MGR__|$PKG_MGR|g; s|__TEST_CMD__|$TEST_CMD|g; s|__LINT_CMD__|$LINT_CMD|g; s|__WORKSPACE__|$WORKSPACE|g; s|__CLAUDE_HOME__|$claude_dir|g" "$template" > "$processed"
    rm -f "$existing.bak"
    cp "$existing" "$existing.bak"
    local merged
    merged=$(mktemp)
    if jq -s '.[0] * .[1]' "$existing" "$processed" > "$merged" 2>/dev/null && jq . "$merged" > /dev/null 2>&1; then
        mv "$merged" "$existing"
        rm -f "$existing.bak" "$processed"
        echo "[update] settings.local.json merged"
    else
        echo "[update] settings.local.json merge FAILED — keeping original"
        mv "$existing.bak" "$existing"
        rm -f "$merged" "$processed"
    fi
}

# 确保 $2 是指向 $1 的正确 symlink（断链/普通文件/不存在 均自动修复）
ensure_symlink() {
    local src="$1" dst="$2"
    if [ ! -L "$dst" ] || [ "$(readlink -f "$dst" 2>/dev/null)" != "$src" ]; then
        mkdir -p "$(dirname "$dst")"
        ln -sf "$src" "$dst"
        echo "  ✅ $(basename "$dst") → 全局 symlink"
    fi
}

ensure_gitignore() {
    local gitignore="$TARGET/.gitignore"
    if [ ! -f "$gitignore" ]; then
        printf '# Project .gitignore\n.claude/\n' > "$gitignore"
        echo "  ✅ .gitignore 已创建（含 .claude/）"
    elif ! grep -qFx '.claude/' "$gitignore" 2>/dev/null; then
        echo '.claude/' >> "$gitignore"
        echo "  ✅ .gitignore 已追加 .claude/"
    fi
}

install_wt() {
    [ -x "$HOME/.local/bin/wt" ] && return 0
    local repo="https://raw.githubusercontent.com/douxt/wt/v1.1.1"
    local fallback="https://gitee.com/cybxcoder/wt/raw/v1.1.1"
    mkdir -p "$HOME/.local/bin"
    curl -fsSL "$repo/wt" -o "$HOME/.local/bin/wt" \
      || curl -fsSL "$fallback/wt" -o "$HOME/.local/bin/wt" \
      || { echo "  ⚠️ wt 下载失败，跳过（可用 git worktree 代替）"; return 1; }
    chmod +x "$HOME/.local/bin/wt"
    [ ! -f "$HOME/.wtconfig" ] && printf 'WT_ROOT=$HOME/wt\n' > "$HOME/.wtconfig"
    echo "  ✅ wt v1.1.1 安装完成"
}

# ── source guard（source 时到此为止，函数已全部定义）──
[[ "${BASH_SOURCE[0]}" == "${0}" ]] || return 0

# ── 参数解析 ──
while [ $# -gt 0 ]; do
    case "$1" in
        --tech-stack) TECH_STACK="$2"; shift 2 ;;
        --test-cmd)   TEST_CMD="$2"; shift 2 ;;
        --lint-cmd)   LINT_CMD="$2"; shift 2 ;;
        --pkg-mgr)    PKG_MGR="$2"; shift 2 ;;
        --mode)       MODE="$2"; shift 2 ;;
        --home)       HOME_OVERRIDE="$2"; shift 2 ;;
        --user)       USER_OVERRIDE="$2"; shift 2 ;;
        --scheduler)  SCHEDULER="$2"; shift 2 ;;
        --no-config)  NO_CONFIG=true; shift ;;
        --no-skills)  NO_SKILLS=true; shift ;;
        --skip-root)  SKIP_ROOT=true; shift ;;
        --dry-run)    DRY_RUN=true; shift ;;
        --force)      FORCE=true; shift ;;
        --update)     UPDATE_MODE=true; shift ;;
        --role)       ROLE="$2"; ROLE_SET=true; shift 2 ;;
        --help)
            echo "用法: bash install.sh <项目路径> [选项]"
            echo ""
            echo "必需:"
            echo "  <项目路径>                    目标项目路径"
            echo ""
            echo "模式:"
            echo "  --mode frontend|backend|full  部署模式（默认 full）"
            echo "  --role owner|developer|agent-b  角色级别（默认 agent-b）"
            echo "  --update                      增量更新（读取 .devflow/config.yaml mode）"
            echo ""
            echo "环境:"
            echo "  --home <path>                 覆盖 \$HOME（Docker 内 coder 路径）"
            echo "  --user <name>                 调度器运行用户（默认当前用户）"
            echo "  --scheduler systemd|cron|none|external  调度器类型（默认自动检测）"
            echo ""
            echo "技术栈:"
            echo "  --tech-stack node|python|go   技术栈（默认自动检测）"
            echo "  --test-cmd <cmd>              测试命令"
            echo "  --lint-cmd <cmd>              Lint 命令"
            echo "  --pkg-mgr <npm|yarn|pnpm|uv|pip|cargo>  包管理器"
            echo ""
            echo "控制:"
            echo "  --no-config                   跳过 settings + hooks + CLAUDE.md 安装"
            echo "  --no-skills                   跳过 CC skill 安装"
            echo "  --skip-root                   跳过 root 段输出"
            echo "  --dry-run                     预览模式，不实际写入"
            echo "  --force                       强制覆盖已有文件"
            echo "  --help                        显示此帮助"
            exit 0 ;;
        *)            TARGET="$1"; shift ;;
    esac
done

if [ -z "$TARGET" ]; then
    echo "❌ 需要指定目标项目路径"; echo "用法: bash install.sh <项目路径> [选项]"; exit 1
fi

# ── 模式校验 ──
case "$MODE" in frontend|backend|full) ;; *)
    echo "❌ 无效 --mode: $MODE（可选: frontend, backend, full）"; exit 1 ;; esac

# ── 调度器校验 ──
if [ -n "$SCHEDULER" ]; then
    case "$SCHEDULER" in systemd|cron|none|external) ;; *)
        echo "❌ 无效 --scheduler: $SCHEDULER（可选: systemd, cron, none, external）"; exit 1 ;; esac
fi

# ── 角色校验 ──
case "$ROLE" in owner|developer|agent-b) ;; *)
    echo "❌ 无效 --role: $ROLE（可选: owner, developer, agent-b）"; exit 1 ;; esac

TARGET=$(cd "$TARGET" && pwd -P 2>/dev/null || echo "$TARGET")
SOURCE=$(cd "$(dirname "$0")" && pwd)
CLAUDE_HOME="${HOME_OVERRIDE:-$HOME}"
PROJECT=$(basename "$TARGET")

detect_environment

# 自动调度器选择
if [ -z "$SCHEDULER" ]; then
    if [ "$IS_DOCKER" = true ]; then SCHEDULER="none"
    elif [ "$HAS_SYSTEMD" = true ]; then SCHEDULER="systemd"
    elif [ "$HAS_CRON" = true ]; then SCHEDULER="cron"
    else SCHEDULER="none"; fi
fi

# ── 模式组件开关 ──
FRONTEND=false; BACKEND=false
case "$MODE" in
    frontend) FRONTEND=true ;;
    backend)  BACKEND=true ;;
    full)     FRONTEND=true; BACKEND=true ;;
esac

# ── update 模式：读 config.yaml mode ──
if [ "$UPDATE_MODE" = true ]; then
    CONFIG_YAML="$TARGET/.devflow/config.yaml"
    if [ -f "$CONFIG_YAML" ]; then
        STORED_MODE=$(grep -E '^[[:space:]]*mode:[[:space:]]*[^[:space:]#]+' "$CONFIG_YAML" 2>/dev/null | head -1 | sed 's/^[[:space:]]*mode:[[:space:]]*//;s/[[:space:]]*#.*//;s/[[:space:]]*$//' || echo "")
        if [ -n "$STORED_MODE" ] && [ "$MODE" = "full" ]; then
            MODE="$STORED_MODE"
            FRONTEND=false; BACKEND=false
            case "$MODE" in
                frontend) FRONTEND=true ;; backend) BACKEND=true ;; full) FRONTEND=true; BACKEND=true ;;
            esac
            echo "ℹ️  从 config.yaml 读取 mode: $MODE"
        elif [ -z "$STORED_MODE" ]; then
            echo "⚠️  config.yaml 无 mode 字段，默认 full（可 --mode 显式指定）"
        fi
        # 读取 stored role
        STORED_ROLE=$(grep -E '^[[:space:]]*role:[[:space:]]*[^[:space:]#]+' "$CONFIG_YAML" 2>/dev/null | head -1 | sed 's/^[[:space:]]*role:[[:space:]]*//;s/[[:space:]]*#.*//;s/[[:space:]]*$//' || echo "")
        # 未显式传 --role 时从 config 读取
        if [ "$ROLE_SET" = false ] && [ -n "$STORED_ROLE" ]; then
            ROLE="$STORED_ROLE"
            echo "ℹ️  从 config.yaml 读取 role: $ROLE"
        fi
        # 若 --role 显式传了不同值，写回 config.yaml
        if [ "$ROLE_SET" = true ] && [ "$ROLE" != "$STORED_ROLE" ]; then
            sed -i "s/^[[:space:]]*role:.*/role: $ROLE/" "$CONFIG_YAML"
            echo "ℹ️  config.yaml role 更新为: $ROLE"
        fi
    fi
fi

echo "╔══════════════════════════════════════╗"
echo "║  ai-dev-flow-server 通用安装器      ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "  源: $SOURCE"
echo "  目标: $TARGET"
echo "  模式: $MODE (frontend=$FRONTEND, backend=$BACKEND)"
echo "  角色: $ROLE"
echo "  调度器: $SCHEDULER"
echo "  CLAUDE_HOME: $CLAUDE_HOME"
[ "$DRY_RUN" = true ] && echo "  ⚠️  DRY-RUN 模式：只预览，不写入"
[ "$FORCE" = true ] && echo "  ⚠️  FORCE 模式：强制覆盖已有文件"
echo ""

# ═══════════════════════════════════
# update 模式
# ═══════════════════════════════════
if [ "$UPDATE_MODE" = true ]; then
    echo "── 更新模式 ──"
    if [ -d "$SOURCE/.git" ]; then
        echo "  git pull ..."
        cd "$SOURCE" || exit 1
        if ! git pull --rebase origin main 2>&1; then
            echo "❌ git pull --rebase 失败，请手动解决冲突后重试"
            echo "   冲突文件: $(git diff --name-only --diff-filter=U 2>/dev/null | tr '\n' ' ')"
            exit 1
        fi
    fi

    install_wt
    deploy_file() {
        local src="$1" dst="$2"
        [ -f "$src" ] || { echo "  ❌ 源文件不存在: $src"; return 1; }
        if [ -L "$dst" ] && [ -e "$dst" ]; then
            echo "[update] skip $(basename "$dst") — managed by claude-config (symlink)"
            return 0
        fi
        dry_run "mkdir -p $(dirname "$dst")"
        dry_run "cp -f $src $dst"
        return 0
    }

    if [ "$BACKEND" = true ]; then
        echo "  更新 archon/ ..."
        deploy_file "$SOURCE/archon/dispatch.sh" "$TARGET/.devflow/archon/dispatch.sh"
        deploy_file "$SOURCE/archon/reconciler.sh" "$TARGET/.devflow/archon/reconciler.sh"
        deploy_file "$SOURCE/archon/auto-execute-afk.yaml" "$TARGET/.devflow/archon/auto-execute-afk.yaml"
        dry_run "mkdir -p $TARGET/.archon/workflows"
        deploy_file "$SOURCE/archon/auto-execute-afk.yaml" "$TARGET/.archon/workflows/auto-execute-afk.yaml"
        echo "  更新 scripts/ ..."
        deploy_file "$SOURCE/archon/status.sh" "$TARGET/.devflow/scripts/status.sh"
        deploy_file "$SOURCE/scripts/check-layer.sh" "$TARGET/.devflow/scripts/check-layer.sh"
        for py in "$SOURCE/scripts/"*.py; do
            [ -f "$py" ] && deploy_file "$py" "$TARGET/.devflow/scripts/$(basename "$py")"
        done
    fi

    echo "  更新 knowledge/ ..."
    for md in "$SOURCE/knowledge/"*.md; do
        [ -f "$md" ] && deploy_file "$md" "$TARGET/.devflow/knowledge/$(basename "$md")"
    done

    # 从 config.yaml 读取 tech_stack 参数（merge_settings_local 需要）
    if [ -f "$CONFIG_YAML" ]; then
        [ -z "$PKG_MGR" ] && PKG_MGR=$(grep -E '^[[:space:]]*package_manager:' "$CONFIG_YAML" 2>/dev/null | head -1 | sed 's/.*:[[:space:]]*//;s/[[:space:]]*$//' || echo "")
        [ -z "$TEST_CMD" ] && TEST_CMD=$(grep -E '^[[:space:]]*test_command:' "$CONFIG_YAML" 2>/dev/null | head -1 | sed 's/.*:[[:space:]]*//;s/[[:space:]]*$//' || echo "")
        [ -z "$LINT_CMD" ] && LINT_CMD=$(grep -E '^[[:space:]]*lint_command:' "$CONFIG_YAML" 2>/dev/null | head -1 | sed 's/.*:[[:space:]]*//;s/[[:space:]]*$//' || echo "")
    fi
    [ -z "$PKG_MGR" ] && PKG_MGR="npm"
    [ -z "$TEST_CMD" ] && TEST_CMD="npm test"
    [ -z "$LINT_CMD" ] && LINT_CMD="npm run lint"
    WORKSPACE="$TARGET"

    if [ "$FRONTEND" = true ]; then
        echo "  更新 workflows/ ..."
        dry_run "mkdir -p $CLAUDE_HOME/.claude/workflows"
        for js in "$SOURCE/workflows/"*.js; do
            [ -f "$js" ] && deploy_file "$js" "$CLAUDE_HOME/.claude/workflows/$(basename "$js")"
        done

        echo "  更新 CC config ..."
        if [ -f "$SOURCE/config-templates/default/settings.json" ]; then
            CLAUDE_DIR="$CLAUDE_HOME/.claude"
            dry_run "mkdir -p $CLAUDE_DIR/hooks"
            merge_settings_local
        fi
        ensure_gitignore
        # 项目级 settings.local.json symlink → 全局（保证 Claude Code 项目内可读到 env）
        if [ "$DRY_RUN" = false ]; then
            TGT_SETTINGS="$TARGET/.claude/settings.local.json"
            GLOBAL_SETTINGS="$CLAUDE_HOME/.claude/settings.local.json"
            ensure_symlink "$GLOBAL_SETTINGS" "$TGT_SETTINGS"
        fi
        deploy_file "$SOURCE/config-templates/default/CLAUDE.md" "$CLAUDE_HOME/.claude/CLAUDE.md"

        echo "  更新 CC skills ..."
        dry_run "mkdir -p $CLAUDE_HOME/.claude/skills"
        for skill_dir in "$SOURCE/skills-cache/"*/; do
            [ -d "$skill_dir" ] || continue
            skill_name=$(basename "$skill_dir")
            [[ "$skill_name" == .* ]] && continue
            dry_run "cp -rL $skill_dir $CLAUDE_HOME/.claude/skills/$skill_name"
        done

        echo "  更新 gate skills + checklists ..."
        for gs in "$SOURCE/skills/"*/; do
            [ -d "$gs" ] || continue
            gs_name=$(basename "$gs")
            [[ "$gs_name" == .* ]] && continue
            dry_run "cp -rL $gs $CLAUDE_HOME/.claude/skills/$gs_name"
        done
        for gc in "$SOURCE/gate-checklists/"*.md; do
            [ -f "$gc" ] && deploy_file "$gc" "$CLAUDE_HOME/.claude/gate-checklists/$(basename "$gc")"
        done
    fi

    echo "  更新 hooks ..."
    for hook in "$SOURCE/config-templates/default/hooks/"*.sh; do
        [ -f "$hook" ] && deploy_file "$hook" "$CLAUDE_HOME/.claude/hooks/$(basename "$hook")"
    done

    echo "  更新 issue 模板 ..."
    dry_run "mkdir -p $TARGET/issues"
    deploy_file "$SOURCE/templates/issue-template.md" "$TARGET/issues/TEMPLATE.md"

    for f in "$TARGET/.devflow/archon/dispatch.sh" "$TARGET/.devflow/archon/reconciler.sh"; do
        [ -f "$f" ] && dry_run "chmod +x $f"
    done
    for f in "$TARGET/.devflow/scripts/"*.sh; do
        [ -f "$f" ] && dry_run "chmod +x $f"
    done

    dry_run "mkdir -p $TARGET/logs"

    # 更新 devflow 脚本 + 角色模板
    echo "  更新 devflow 角色管理 ..."
    dry_run "mkdir -p $TARGET/.devflow/scripts $TARGET/.devflow/templates/roles/agent-b"
    deploy_file "$SOURCE/scripts/devflow" "$TARGET/.devflow/scripts/devflow"
    deploy_file "$SOURCE/templates/CLAUDE.md.base.append" "$TARGET/.devflow/templates/CLAUDE.md.base.append"
    deploy_file "$SOURCE/templates/roles/owner.append" "$TARGET/.devflow/templates/roles/owner.append"
    deploy_file "$SOURCE/templates/roles/developer.append" "$TARGET/.devflow/templates/roles/developer.append"
    deploy_file "$SOURCE/templates/roles/agent-b/CLAUDE.md.append" "$TARGET/.devflow/templates/roles/agent-b/CLAUDE.md.append"
    deploy_file "$SOURCE/templates/roles/agent-b/AGENTS.md" "$TARGET/.devflow/templates/roles/agent-b/AGENTS.md"
    dry_run "chmod +x $TARGET/.devflow/scripts/devflow"
    mkdir -p "$CLAUDE_HOME/.local/bin"
    ln -sf "$TARGET/.devflow/scripts/devflow" "$CLAUDE_HOME/.local/bin/devflow" 2>/dev/null || true

    # 更新 CLAUDE.md 角色段（role 变更时）
    CLAUDE_MD="$TARGET/.claude/CLAUDE.md"
    [ ! -f "$CLAUDE_MD" ] && CLAUDE_MD="$TARGET/CLAUDE.md"
    if [ -f "$CLAUDE_MD" ] && grep -q "ai-dev-flow-server" "$CLAUDE_MD" 2>/dev/null; then
        # 先规范化旧标记为新格式
        sed -i 's/<!-- ⚠️ 以下由 ai-dev-flow-server install.sh 自动追加 -->/<!-- ai-dev-flow-server -->/g' "$CLAUDE_MD"
        if [ "$ROLE" = "agent-b" ]; then
            ROLE_TMPL="$SOURCE/templates/roles/agent-b/CLAUDE.md.append"
        else
            ROLE_TMPL="$SOURCE/templates/roles/${ROLE}.append"
        fi
        BASE_TMPL="$SOURCE/templates/CLAUDE.md.base.append"
        if [ -f "$BASE_TMPL" ] && [ -f "$ROLE_TMPL" ]; then
            COMBINED_FILE="${CLAUDE_MD}.devflow-combined"
            cat "$BASE_TMPL" "$ROLE_TMPL" > "$COMBINED_FILE"
            sed -i "s/__PROJECT__/${PROJECT}/g" "$COMBINED_FILE"
            TMP_MD="${CLAUDE_MD}.devflow-tmp"
            sed '/<!-- ai-dev-flow-server -->/,/<!-- ai-dev-flow-server end -->/d' "$CLAUDE_MD" > "$TMP_MD"
            cat "$COMBINED_FILE" >> "$TMP_MD"
            rm -f "$COMBINED_FILE"
            mv "$TMP_MD" "$CLAUDE_MD"
            echo "  ✅ CLAUDE.md 角色段已更新为 $ROLE"
        fi
    fi

    echo "✅ 更新完成（config.yaml 和 .gate-state 不受影响）"
    exit 0
fi

# ═══════════════════════════════════
# 0. 预检
# ═══════════════════════════════════
echo "── 步骤 0: 预检 ──"
ERRORS=0

if [ ! -d "$TARGET/.git" ]; then
    echo "  ❌ 不是 git 仓库（缺少 .git/）"
    if [ "$DRY_RUN" = true ]; then echo "  [DRY-RUN] 跳过致命错误"; else ERRORS=$((ERRORS + 1)); fi
else
    echo "  ✅ git 仓库"
fi

if command -v gh >/dev/null 2>&1; then
    if gh auth status >/dev/null 2>&1; then echo "  ✅ gh CLI 已认证"
    else echo "  ⚠️  gh CLI 未认证，请运行: gh auth login"; fi
else
    echo "  ⚠️  gh CLI 未安装，PR 创建功能需要 gh"
fi

if command -v claude >/dev/null 2>&1; then echo "  ✅ claude CLI 可用"
else echo "  ⚠️  claude CLI 未安装，CC skill 将无法使用"; fi

if [ ! -f "$TARGET/.claude/CLAUDE.md" ] && [ ! -f "$TARGET/CLAUDE.md" ]; then
    echo "  ⚠️  缺少 CLAUDE.md（建议创建，说明技术栈和项目结构）"
else echo "  ✅ CLAUDE.md 存在"; fi

ISSUES_DIR="$TARGET/issues"
if [ ! -d "$ISSUES_DIR" ]; then
    echo "  ⚠️  issues/ 目录不存在，将自动创建"
    dry_run "mkdir -p $ISSUES_DIR"
    dry_run "touch $ISSUES_DIR/.gitkeep"
fi
echo "  ✅ issues/ 目录就绪"

# Docker 持久化：symlink ~/.claude → ~/.config/claude
if [ "$IS_DOCKER" = true ]; then
    CLAUDE_DIR="$CLAUDE_HOME/.claude"
    CONFIG_CLAUDE="$CLAUDE_HOME/.config/claude"
    if [ "$DRY_RUN" = true ]; then
        echo "  [DRY-RUN] Docker 持久化：ln -sfn ~/.config/claude ~/.claude"
    elif [ -d "$CLAUDE_DIR" ] && [ ! -L "$CLAUDE_DIR" ] && [ "$CLAUDE_DIR" != "/" ]; then
        if [ "$(ls -A "$CLAUDE_DIR" 2>/dev/null)" ]; then
            echo "  ℹ️  Docker 持久化：mv ~/.claude → ~/.config/claude"
            mkdir -p "$CONFIG_CLAUDE"
            (shopt -s dotglob 2>/dev/null; cp -r "$CLAUDE_DIR"/* "$CONFIG_CLAUDE/" 2>/dev/null || true)
            rm -rf "$CLAUDE_DIR"
        else rm -rf "$CLAUDE_DIR"; fi
    fi
    if [ ! -e "$CLAUDE_DIR" ]; then
        mkdir -p "$CONFIG_CLAUDE"
        ln -sfn "$CONFIG_CLAUDE" "$CLAUDE_DIR"
        echo "  ✅ ~/.claude → ~/.config/claude symlink 已创建（Docker 持久化）"
    fi
fi

# 推断技术栈
if [ -z "$TECH_STACK" ]; then
    if [ -f "$TARGET/package.json" ]; then TECH_STACK="node"
    elif [ -f "$TARGET/pyproject.toml" ] || [ -f "$TARGET/setup.py" ] || [ -f "$TARGET/requirements.txt" ]; then TECH_STACK="python"
    elif [ -f "$TARGET/go.mod" ]; then TECH_STACK="go"
    else TECH_STACK="node"; echo "  ℹ️  无法推断技术栈，默认使用 node"; fi
fi
echo "  ℹ️  技术栈: $TECH_STACK"

case "$TECH_STACK" in
    node)
        [ -z "$PKG_MGR" ] && PKG_MGR="npm"
        [ -z "$TEST_CMD" ] && TEST_CMD="npm test"
        [ -z "$LINT_CMD" ] && LINT_CMD="npm run lint" ;;
    python)
        [ -z "$PKG_MGR" ] && PKG_MGR="uv"
        [ -z "$TEST_CMD" ] && TEST_CMD="uv run pytest"
        [ -z "$LINT_CMD" ] && LINT_CMD="uv run ruff check" ;;
    go)
        [ -z "$PKG_MGR" ] && PKG_MGR="go"
        [ -z "$TEST_CMD" ] && TEST_CMD="go test ./..."
        [ -z "$LINT_CMD" ] && LINT_CMD="go vet ./..." ;;
    *) echo "  ❌ 不支持的技术栈: $TECH_STACK"; exit 1 ;;
esac
echo "  包管理: $PKG_MGR | 测试: $TEST_CMD | Lint: $LINT_CMD"

if [ "$DRY_RUN" = false ]; then
    if ! eval "cd \"$TARGET\" && command -v ${TEST_CMD%% *}" >/dev/null 2>&1; then
        echo "  ⚠️  测试命令 '${TEST_CMD%% *}' 不可用，请确认依赖已安装"
    fi
fi

if [ $ERRORS -gt 0 ]; then echo ""; echo "❌ 预检未通过（$ERRORS 项），请修正后重新运行"; exit 1; fi
echo ""

# ═══════════════════════════════════
# 1. 生成 config.yaml
# ═══════════════════════════════════
echo "── 步骤 1: 生成 .devflow/config.yaml ──"
REPO_URL=$(cd "$TARGET" 2>/dev/null && git remote get-url origin 2>/dev/null || echo "git@github.com:user/${PROJECT}.git")

maybe_mkdir "$TARGET/.devflow"

if [ "$DRY_RUN" = true ]; then
    echo "  [DRY-RUN] 写入 .devflow/config.yaml"
elif [ -f "$TARGET/.devflow/config.yaml" ] && [ "$FORCE" != true ]; then
    echo "  ⚠️  .devflow/config.yaml 已存在，跳过（--force 可强制覆盖）"
else
    cat > "$TARGET/.devflow/config.yaml" << DEVCONFIG
# .devflow/config.yaml — 由 ai-dev-flow-server install.sh 生成
project:
  name: ${PROJECT}
  repo_url: ${REPO_URL}
  workspace: ${TARGET}

mode: ${MODE}
role: ${ROLE}

tech_stack:
  language: ${TECH_STACK}
  package_manager: ${PKG_MGR}
  test_command: ${TEST_CMD}
  lint_command: ${LINT_CMD}
DEVCONFIG
    if [ "$BACKEND" = true ]; then
        cat >> "$TARGET/.devflow/config.yaml" << DEVCONFIG

dispatch:
  branch_prefix: ai/
  max_retries: 3
  poll_interval_min: 5

review:
  cross_review: false
  constitution_check: true

notify:
  telegram_chat_id: "<从项目 config/telegram.json 复制>"
  telegram_bot_token: "<同上>"
DEVCONFIG
    fi
    echo "  ✅ .devflow/config.yaml 已生成（请手动填写 telegram 配置）"
fi
echo ""

install_wt

# ═══════════════════════════════════
# A. 安装 config（frontend + full）
# ═══════════════════════════════════
if [ "$FRONTEND" = true ] && [ "$NO_CONFIG" = false ]; then
    echo "── 步骤 A: 安装 CC 配置（settings + hooks + CLAUDE.md）──"

    CLAUDE_DIR="$CLAUDE_HOME/.claude"
    dry_run "mkdir -p $CLAUDE_DIR/hooks"

    # settings.json
    SETTINGS_SRC="$SOURCE/config-templates/default/settings.json"
    SETTINGS_DST="$CLAUDE_DIR/settings.local.json"
    if [ "$DRY_RUN" = true ]; then
        echo "  [DRY-RUN] 生成 $SETTINGS_DST（替换 __VAR__ 占位符）"
    elif [ -f "$SETTINGS_DST" ] && [ "$FORCE" != true ]; then
        echo "  ⚠️  settings.local.json 已存在，跳过（--force 可强制覆盖）"
    elif [ -f "$SETTINGS_SRC" ]; then
        sed -e "s|__PKG_MGR__|${PKG_MGR}|g" \
            -e "s|__TEST_CMD__|${TEST_CMD}|g" \
            -e "s|__LINT_CMD__|${LINT_CMD}|g" \
            -e "s|__WORKSPACE__|${TARGET}|g" \
            -e "s|__CLAUDE_HOME__|${CLAUDE_DIR}|g" \
            "$SETTINGS_SRC" > "$SETTINGS_DST"
        if command -v jq >/dev/null 2>&1; then
            if jq . "$SETTINGS_DST" >/dev/null 2>&1; then
                echo "  ✅ settings.local.json（占位符已替换）"
            else
                echo "  ❌ settings.local.json JSON 语法错误，已回滚"
                cp "$SETTINGS_SRC" "$SETTINGS_DST.bak" 2>/dev/null || true
                rm -f "$SETTINGS_DST"
            fi
        else
            echo "  ⚠️  jq 未安装，跳过 JSON 校验；settings.local.json 已写入"
        fi
    else
        echo "  ⚠️  config-templates/default/settings.json 不存在，跳过"
    fi

    ensure_gitignore
    # 项目级 settings.local.json symlink → 全局（保证 Claude Code 项目内可读到 env）
    if [ "$DRY_RUN" = false ]; then
        TGT_SETTINGS="$TARGET/.claude/settings.local.json"
        GLOBAL_SETTINGS="$CLAUDE_DIR/settings.local.json"
        ensure_symlink "$GLOBAL_SETTINGS" "$TGT_SETTINGS"
    fi

    # CLAUDE.md 全局规则
    CLAUDE_MD_SRC="$SOURCE/config-templates/default/CLAUDE.md"
    CLAUDE_MD_DST="$CLAUDE_DIR/CLAUDE.md"
    if [ "$DRY_RUN" = true ]; then
        echo "  [DRY-RUN] 安装 ~/.claude/CLAUDE.md"
    elif [ -f "$CLAUDE_MD_DST" ] && [ "$FORCE" != true ]; then
        echo "  ⚠️  ~/.claude/CLAUDE.md 已存在，跳过（--force 可强制覆盖）"
    elif [ -f "$CLAUDE_MD_SRC" ]; then
        cp "$CLAUDE_MD_SRC" "$CLAUDE_MD_DST"
        echo "  ✅ ~/.claude/CLAUDE.md（全局 worktree 规则）"
    fi

    echo ""
fi

# 4 个 hook（安全基础设施，所有 mode 都部署）
if [ "$NO_CONFIG" = false ]; then
    if [ -d "$SOURCE/config-templates/default/hooks" ]; then
        for hook in "$SOURCE/config-templates/default/hooks/"*.sh; do
            [ -f "$hook" ] || continue
            hook_name=$(basename "$hook")
            hook_dst="$CLAUDE_HOME/.claude/hooks/$hook_name"
            if [ "$DRY_RUN" = true ]; then
                echo "  [DRY-RUN] cp $hook_name → $hook_dst"
            elif [ -f "$hook_dst" ] && [ "$FORCE" != true ]; then
                echo "  ⚠️  hook/$hook_name 已存在，跳过"
            else
                cp "$hook" "$hook_dst"
                chmod +x "$hook_dst" 2>/dev/null || true
                echo "  ✅ hook/$hook_name"
            fi
        done
    fi
    echo ""
fi

# ═══════════════════════════════════
# B. 安装 CC skills（frontend + full）
# ═══════════════════════════════════
if [ "$FRONTEND" = true ] && [ "$NO_SKILLS" = false ]; then
    echo "── 步骤 B: 安装 CC skills ──"

    SKILLS_SRC="$SOURCE/skills-cache"
    SKILLS_DST="$CLAUDE_HOME/.claude/skills"

    if [ ! -d "$SKILLS_SRC" ]; then
        echo "  ⚠️  skills-cache/ 不存在，跳过"
    else
        # CC 版本兼容性检查
        if [ -f "$SKILLS_SRC/.version" ] && [ "$DRY_RUN" = false ]; then
            CACHED_CC=$(jq -r '.cc_version' "$SKILLS_SRC/.version" 2>/dev/null || echo "")
            LOCAL_CC=$(claude --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "")
            if [ -n "$CACHED_CC" ] && [ -n "$LOCAL_CC" ]; then
                CACHED_MAJOR="${CACHED_CC%%.*}"; LOCAL_MAJOR="${LOCAL_CC%%.*}"
                if [ "$CACHED_MAJOR" != "$LOCAL_MAJOR" ]; then
                    echo "  ⚠️  skills-cache CC 版本 ($CACHED_CC) 与本地 ($LOCAL_CC) 大版本不同，可能不兼容"
                fi
            fi
        fi

        dry_run "mkdir -p $SKILLS_DST"
        for skill_dir in "$SKILLS_SRC"/*/; do
            [ -d "$skill_dir" ] || continue
            skill_name=$(basename "$skill_dir")
            [[ "$skill_name" == .* ]] && continue
            skill_dst="$SKILLS_DST/$skill_name"
            if [ "$DRY_RUN" = true ]; then
                echo "  [DRY-RUN] cp -r $skill_name/ → $skill_dst"
            elif [ -d "$skill_dst" ] && [ "$FORCE" != true ]; then
                echo "  ⚠️  skill/$skill_name 已存在，跳过"
            else
                [ "$FORCE" = true ] && rm -rf "$skill_dst"
                cp -rL "$skill_dir" "$skill_dst"
                echo "  ✅ skill/$skill_name"
            fi
        done
    fi
    echo ""
fi

# ═══════════════════════════════════
# 2. 复制 workflows（frontend + full）
# ═══════════════════════════════════
if [ "$FRONTEND" = true ]; then
    echo "── 步骤 2: 复制 gate 脚本到 ~/.claude/workflows/ ──"
    dry_run "mkdir -p $CLAUDE_HOME/.claude/workflows"
    if [ "$DRY_RUN" = true ]; then
        echo "  [DRY-RUN] cp workflows/*.js → $CLAUDE_HOME/.claude/workflows/"
    else
        count=0
        for js in "$SOURCE/workflows/"*.js; do
            [ -f "$js" ] || continue
            dst="$CLAUDE_HOME/.claude/workflows/$(basename "$js")"
            if [ -f "$dst" ] && [ "$FORCE" != true ]; then
                echo "  ⚠️  $(basename "$js") 已存在，跳过"; continue
            fi
            cp "$js" "$dst" && count=$((count + 1))
        done
        echo "  ✅ $count 个 gate 脚本已安装"
    fi

    # gate-checklists
    echo "── 步骤 2b: 复制 gate-checklists/ ──"
    maybe_cp_dir "$SOURCE/gate-checklists" "$CLAUDE_HOME/.claude/gate-checklists"

    # gate skills（skills/ 下 gate skill，v3.0 起已退役，此目录仅保留兼容）
    echo "── 步骤 2c: 安装 gate skills ──"
    if [ -d "$SOURCE/skills" ]; then
        dry_run "mkdir -p $CLAUDE_HOME/.claude/skills"
        for skill_dir in "$SOURCE/skills/"*/; do
            [ -d "$skill_dir" ] || continue
            skill_name=$(basename "$skill_dir")
            [[ "$skill_name" == .* ]] && continue
            skill_dst="$CLAUDE_HOME/.claude/skills/$skill_name"
            if [ "$DRY_RUN" = true ]; then
                echo "  [DRY-RUN] cp -r $skill_name/ → $skill_dst"
            elif [ -d "$skill_dst" ] && [ "$FORCE" != true ]; then
                echo "  ⚠️  gate-skill/$skill_name 已存在，跳过"
            else
                [ "$FORCE" = true ] && rm -rf "$skill_dst"
                cp -rL "$skill_dir" "$skill_dst"
                echo "  ✅ gate-skill/$skill_name"
            fi
        done
    fi
    echo ""
fi

# ═══════════════════════════════════
# 3. 复制 .gate-state（frontend + full）
# ═══════════════════════════════════
if [ "$FRONTEND" = true ]; then
    echo "── 步骤 3: 复制 .gate-state ──"
    GATE_STATE="$TARGET/.gate-state"
    if [ -f "$GATE_STATE" ]; then
        echo "  ⚠️  .gate-state 已存在，跳过（永不覆盖，防止进度丢失）"
    else
        dry_run "cp $SOURCE/templates/gate-state.yml $GATE_STATE"
        [ "$DRY_RUN" = false ] && cp "$SOURCE/templates/gate-state.yml" "$GATE_STATE" && echo "  ✅ .gate-state 已创建"
    fi
    echo ""
fi

# ═══════════════════════════════════
# 4. 追加 CLAUDE.md（所有 mode，按 role 拼接）
# ═══════════════════════════════════
echo "── 步骤 4: 追加 CLAUDE.md 片段（幂等，role=$ROLE）──"
CLAUDE_MD="$TARGET/.claude/CLAUDE.md"
if [ ! -f "$CLAUDE_MD" ]; then CLAUDE_MD="$TARGET/CLAUDE.md"; fi
if [ ! -f "$CLAUDE_MD" ]; then
    dry_run "mkdir -p $TARGET/.claude"
    CLAUDE_MD="$TARGET/.claude/CLAUDE.md"
    [ "$DRY_RUN" = false ] && { mkdir -p "$TARGET/.claude"; touch "$CLAUDE_MD"; }
fi

if grep -q "ai-dev-flow-server" "$CLAUDE_MD" 2>/dev/null; then
    echo "  ⚠️  CLAUDE.md 已含 ai-dev-flow-server 标记，跳过追加"
else
    # 拼接 base + role 模板
    BASE_APPEND="$SOURCE/templates/CLAUDE.md.base.append"
    if [ "$ROLE" = "agent-b" ]; then
        ROLE_APPEND="$SOURCE/templates/roles/agent-b/CLAUDE.md.append"
    else
        ROLE_APPEND="$SOURCE/templates/roles/${ROLE}.append"
    fi
    dry_run "cat $BASE_APPEND $ROLE_APPEND >> $CLAUDE_MD"
    if [ "$DRY_RUN" = false ]; then
        cat "$BASE_APPEND" "$ROLE_APPEND" >> "$CLAUDE_MD"
        sed -i "s/__PROJECT__/${PROJECT}/g" "$CLAUDE_MD"
        echo "  ✅ CLAUDE.md 片段已追加（role=$ROLE）"
    fi
fi
echo ""

# ═══════════════════════════════════
# 5. 复制 devflow 文件（按 mode）
# ═══════════════════════════════════
echo "── 步骤 5: 复制 .devflow/ 文件 ──"
dry_run "mkdir -p $TARGET/.devflow/knowledge"

# knowledge/ — 所有 mode
maybe_cp_dir "$SOURCE/knowledge" "$TARGET/.devflow/knowledge"

# archon/ + scripts/ — backend + full
if [ "$BACKEND" = true ]; then
    dry_run "mkdir -p $TARGET/.devflow/archon $TARGET/.devflow/scripts"
    maybe_cp "$SOURCE/archon/dispatch.sh" "$TARGET/.devflow/archon/dispatch.sh"
    maybe_cp "$SOURCE/archon/reconciler.sh" "$TARGET/.devflow/archon/reconciler.sh"
    maybe_cp "$SOURCE/archon/auto-execute-afk.yaml" "$TARGET/.devflow/archon/auto-execute-afk.yaml"
    [ "$DRY_RUN" = false ] && chmod +x "$TARGET/.devflow/archon/dispatch.sh" "$TARGET/.devflow/archon/reconciler.sh" 2>/dev/null || true

    # scripts/
    maybe_cp "$SOURCE/scripts/check_constitution.py" "$TARGET/.devflow/scripts/check_constitution.py"
    maybe_cp "$SOURCE/scripts/cost_tracker.py" "$TARGET/.devflow/scripts/cost_tracker.py"
    maybe_cp "$SOURCE/scripts/notify.py" "$TARGET/.devflow/scripts/notify.py"
    maybe_cp "$SOURCE/archon/status.sh" "$TARGET/.devflow/scripts/status.sh"
    maybe_cp "$SOURCE/scripts/check-layer.sh" "$TARGET/.devflow/scripts/check-layer.sh"
    [ "$DRY_RUN" = false ] && { for f in "$TARGET/.devflow/scripts/"*.py "$TARGET/.devflow/scripts/status.sh" "$TARGET/.devflow/scripts/check-layer.sh"; do [ -f "$f" ] && chmod +x "$f" 2>/dev/null; done; true; }

    # .archon/workflows/
    echo "── 步骤 5b: 注册 Archon workflow ──"
    dry_run "mkdir -p $TARGET/.archon/workflows"
    maybe_cp "$SOURCE/archon/auto-execute-afk.yaml" "$TARGET/.archon/workflows/auto-execute-afk.yaml"

    # logs/
    echo "── 步骤 5c: 创建日志目录 ──"
    dry_run "mkdir -p $TARGET/logs"
    if [ "$DRY_RUN" = false ] && [ -n "${USER_OVERRIDE:-}" ] && command -v chown >/dev/null 2>&1; then
        chown -R "${USER_OVERRIDE}:${USER_OVERRIDE}" "$TARGET/logs" 2>/dev/null || \
            echo "  ⚠️  无法 chown logs/，请手动: chown ${USER_OVERRIDE} $TARGET/logs"
    fi
fi

# devflow 脚本 + 模板 — 所有 mode
echo "── 步骤 5f: 部署 devflow 角色管理 ──"
dry_run "mkdir -p $TARGET/.devflow/scripts $TARGET/.devflow/templates/roles/agent-b"
maybe_cp "$SOURCE/scripts/devflow" "$TARGET/.devflow/scripts/devflow"
maybe_cp "$SOURCE/templates/CLAUDE.md.base.append" "$TARGET/.devflow/templates/CLAUDE.md.base.append"
maybe_cp "$SOURCE/templates/roles/owner.append" "$TARGET/.devflow/templates/roles/owner.append"
maybe_cp "$SOURCE/templates/roles/developer.append" "$TARGET/.devflow/templates/roles/developer.append"
maybe_cp "$SOURCE/templates/roles/agent-b/CLAUDE.md.append" "$TARGET/.devflow/templates/roles/agent-b/CLAUDE.md.append"
maybe_cp "$SOURCE/templates/roles/agent-b/AGENTS.md" "$TARGET/.devflow/templates/roles/agent-b/AGENTS.md"
[ "$DRY_RUN" = false ] && chmod +x "$TARGET/.devflow/scripts/devflow" 2>/dev/null || true

# symlink devflow 到 ~/.local/bin/
if [ "$DRY_RUN" = false ]; then
    mkdir -p "$CLAUDE_HOME/.local/bin"
    ln -sf "$TARGET/.devflow/scripts/devflow" "$CLAUDE_HOME/.local/bin/devflow" 2>/dev/null || true
    echo "  ✅ devflow → ~/.local/bin/devflow"
else
    echo "  [DRY-RUN] ln -s .devflow/scripts/devflow ~/.local/bin/devflow"
fi

echo "  ✅ .devflow/ 文件已复制"
echo ""

# ═══════════════════════════════════
# 5d. git upstream 检查
# ═══════════════════════════════════
echo "── 步骤 5d: 检查 git upstream ──"
CURRENT_BRANCH=$(cd "$TARGET" && git branch --show-current 2>/dev/null || echo "")
if [ -n "$CURRENT_BRANCH" ] && [ "$DRY_RUN" = false ]; then
    if cd "$TARGET" && git rev-parse --abbrev-ref "${CURRENT_BRANCH}@{upstream}" >/dev/null 2>&1; then
        echo "  ✅ upstream 已设置"
    else
        cd "$TARGET" && git push --set-upstream origin "$CURRENT_BRANCH" 2>/dev/null || \
            echo "  ⚠️  无法自动设置 upstream，请手动: git push --set-upstream origin $CURRENT_BRANCH"
    fi
else
    [ "$DRY_RUN" = true ] && echo "  [DRY-RUN] 检查 git upstream"
    [ "$DRY_RUN" = false ] && echo "  ⚠️  无法检测当前分支"
fi
echo ""

# ═══════════════════════════════════
# 6. issue 模板
# ═══════════════════════════════════
echo "── 步骤 6: 复制 issue 模板 ──"
maybe_cp "$SOURCE/templates/issue-template.md" "$TARGET/issues/TEMPLATE.md"
echo ""

# ═══════════════════════════════════
# 7. _handoff/（仅 agent-b）
# ═══════════════════════════════════
if [ "$ROLE" = "agent-b" ]; then
echo "── 步骤 7: 创建 _handoff/ Agent 协作目录 ──"
HANDOFF_DIR="$TARGET/_handoff"
if [ -d "$HANDOFF_DIR" ] && [ "$FORCE" != true ]; then
    echo "  ⚠️  _handoff/ 已存在，跳过"
else
    dry_run "mkdir -p $HANDOFF_DIR/outbox/agent-b $HANDOFF_DIR/inbox/agent-b $HANDOFF_DIR/archive"
    if [ "$DRY_RUN" = false ]; then
        mkdir -p "$HANDOFF_DIR/outbox/agent-b" "$HANDOFF_DIR/inbox/agent-b" "$HANDOFF_DIR/archive"
        [ -f "$SOURCE/templates/_handoff/README.md" ] && cp "$SOURCE/templates/_handoff/README.md" "$HANDOFF_DIR/"
        [ -f "$SOURCE/templates/_handoff/TEMPLATE.md" ] && cp "$SOURCE/templates/_handoff/TEMPLATE.md" "$HANDOFF_DIR/"
        echo "  ✅ _handoff/{outbox/agent-b,inbox/agent-b,archive}/ 已创建"
    else
        echo "  [DRY-RUN] _handoff/{outbox/agent-b,inbox/agent-b,archive}/"
    fi
fi
echo ""
else
    echo "── 步骤 7: _handoff/ 跳过（role=$ROLE，无需 Agent 协作通道）──"
    echo ""
fi

# ═══════════════════════════════════
# 8. AGENTS.md（仅 agent-b）
# ═══════════════════════════════════
if [ "$ROLE" = "agent-b" ]; then
echo "── 步骤 8: 生成 AGENTS.md ──"
AGENTS_MD="$TARGET/AGENTS.md"
if [ -f "$AGENTS_MD" ] && [ "$FORCE" != true ]; then
    echo "  ⚠️  AGENTS.md 已存在，跳过"
else
    if [ "$DRY_RUN" = true ]; then
        echo "  [DRY-RUN] 生成 AGENTS.md"
    else
        cp "$SOURCE/templates/roles/agent-b/AGENTS.md" "$AGENTS_MD"
        sed -i "s/__PROJECT__/${PROJECT}/g" "$AGENTS_MD"
        echo "  ✅ AGENTS.md 已生成"
    fi
fi
echo ""
else
    echo "── 步骤 8: AGENTS.md 跳过（role=$ROLE）──"
    echo ""
fi

# ═══════════════════════════════════
# 9. git hooks
# ═══════════════════════════════════
echo "── 步骤 9: 部署 git hooks ──"
HOOKS_DIR="$TARGET/.git/hooks"
dry_run "mkdir -p $HOOKS_DIR"
maybe_cp "$SOURCE/templates/pre-commit" "$HOOKS_DIR/pre-commit"
maybe_cp "$SOURCE/templates/pre-push" "$HOOKS_DIR/pre-push"
[ "$DRY_RUN" = false ] && chmod +x "$HOOKS_DIR/pre-commit" "$HOOKS_DIR/pre-push" 2>/dev/null || true
echo ""

# ═══════════════════════════════════
# 10. 用户段检查清单
# ═══════════════════════════════════
echo "╔══════════════════════════════════════╗"
echo "║  用户段安装完成                      ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "📋 检查清单："
echo "  [ ] .devflow/config.yaml — 填写 telegram_chat_id 和 telegram_bot_token"
if [ "$BACKEND" = true ]; then
    echo "  [ ] .devflow/archon/ — dispatch.sh + reconciler.sh + auto-execute-afk.yaml"
    echo "  [ ] .archon/workflows/ — auto-execute-afk.yaml（archon 可发现）"
    echo "  [ ] .devflow/scripts/ — check_constitution.py + cost_tracker.py + notify.py"
fi
echo "  [ ] .devflow/knowledge/ — 7 份知识文档"
if [ "$FRONTEND" = true ]; then
    echo "  [ ] .gate-state — Gate 状态追踪"
    echo "  [ ] ~/.claude/skills/ — 15 个 CC skill（gate skill v3.0 起已退役）"
    echo "  [ ] ~/.claude/gate-checklists/ — 6 个 gate 清单"
    echo "  [ ] ~/.claude/workflows/ — 6 个 gate 脚本"
fi
if [ "$BACKEND" = true ]; then
    echo "  [ ] logs/ — 确保属主正确"
fi
echo "  [ ] _handoff/ — Agent 协作收件箱（outbox/agent-b + inbox/agent-b + archive）"
echo "  [ ] AGENTS.md — Agent 身份 + 壁垒声明"
echo "  [ ] .git/hooks/pre-commit — 拦截修改受保护文件"
echo "  [ ] .git/hooks/pre-push — 拦截直推 master"
echo ""

# ═══════════════════════════════════
# 11. root 段（按 scheduler）
# ═══════════════════════════════════
if [ "$SKIP_ROOT" = false ] && [ "$BACKEND" = true ]; then
    echo "╔══════════════════════════════════════╗"
    echo "║  root 段（请以 root 身份执行）       ║"
    echo "╚══════════════════════════════════════╝"
    echo ""

    case "$SCHEDULER" in
        systemd)
            SVC_USER="${USER_OVERRIDE:-www}"
            echo "# 0. 创建 /etc/devflow/${PROJECT}.env（API 密钥文件）"
            cat << ENVFILE_STEP
mkdir -p /etc/devflow
API_KEY=\$(python3 -c "
import json, os
p = '/home/${SVC_USER}/.claude/settings.local.json'
if os.path.exists(p):
    with open(p) as f:
        d = json.load(f)
    print(d.get('env',{}).get('ANTHROPIC_API_KEY','MISSING'))
else:
    print('MISSING')
")
if [ "\$API_KEY" != "MISSING" ]; then
  cat > /etc/devflow/${PROJECT}.env << INNER
ANTHROPIC_API_KEY=\$API_KEY
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
INNER
  chmod 640 /etc/devflow/${PROJECT}.env
  chown root:${SVC_USER} /etc/devflow/${PROJECT}.env
  echo "  ✓ /etc/devflow/${PROJECT}.env (chmod 640)"
else
  echo "  ⚠ /home/${SVC_USER}/.claude/settings.local.json 未找到，跳过 .env 创建"
fi
ENVFILE_STEP

            echo ""
            echo "# 1. 创建 dispatch-${PROJECT}.service"
            cat << DISPATCH_SVC
cat > /etc/systemd/system/dispatch-${PROJECT}.service << 'EOF'
[Unit]
Description=DevFlow AFK Dispatch — ${PROJECT}
After=network.target

[Service]
Type=oneshot
User=${SVC_USER}
WorkingDirectory=${TARGET}
EnvironmentFile=/etc/devflow/${PROJECT}.env
ExecStart=/bin/bash ${TARGET}/.devflow/archon/dispatch.sh ${TARGET}
StandardOutput=append:${TARGET}/logs/dispatch.log
StandardError=append:${TARGET}/logs/dispatch.log
EOF
DISPATCH_SVC

            echo ""
            echo "# 2. 创建 dispatch-${PROJECT}.timer（每 5 分钟）"
            cat << DISPATCH_TIMER
cat > /etc/systemd/system/dispatch-${PROJECT}.timer << 'EOF'
[Unit]
Description=DevFlow AFK Dispatch Timer — ${PROJECT}

[Timer]
OnCalendar=*:0/5
Persistent=true

[Install]
WantedBy=timers.target
EOF
DISPATCH_TIMER

            echo ""
            echo "# 3. 创建 reconcile-${PROJECT}.service"
            cat << RECONCILE_SVC
cat > /etc/systemd/system/reconcile-${PROJECT}.service << 'EOF'
[Unit]
Description=DevFlow AFK Reconcile — ${PROJECT}
After=network.target

[Service]
Type=oneshot
User=${SVC_USER}
WorkingDirectory=${TARGET}
EnvironmentFile=/etc/devflow/${PROJECT}.env
ExecStart=/bin/bash ${TARGET}/.devflow/archon/reconciler.sh ${TARGET}
StandardOutput=append:${TARGET}/logs/reconcile.log
StandardError=append:${TARGET}/logs/reconcile.log
EOF
RECONCILE_SVC

            echo ""
            echo "# 4. 创建 reconcile-${PROJECT}.timer（每 15 分钟）"
            cat << RECONCILE_TIMER
cat > /etc/systemd/system/reconcile-${PROJECT}.timer << 'EOF'
[Unit]
Description=DevFlow AFK Reconcile Timer — ${PROJECT}

[Timer]
OnCalendar=*:0/15
Persistent=true

[Install]
WantedBy=timers.target
EOF
RECONCILE_TIMER

            echo ""
            echo "# 5. 激活 timer"
            echo "systemctl daemon-reload"
            echo "systemctl enable --now dispatch-${PROJECT}.timer reconcile-${PROJECT}.timer"
            echo "systemctl status dispatch-${PROJECT}.timer reconcile-${PROJECT}.timer"
            ;;

        cron)
            CRON_USER="${USER_OVERRIDE:-$(whoami)}"
            echo "# 创建 crontab 条目（以 ${CRON_USER} 用户运行）"
            echo ""
            echo "crontab -u ${CRON_USER} -l 2>/dev/null | grep -v 'dispatch.sh\|reconciler.sh' > /tmp/cron.\$\$"
            echo "cat >> /tmp/cron.\$\$ << 'CRONEOF'"
            echo "*/5 * * * * cd ${TARGET} && bash ${TARGET}/.devflow/archon/dispatch.sh ${TARGET} >> ${TARGET}/logs/dispatch.log 2>&1"
            echo "*/15 * * * * cd ${TARGET} && bash ${TARGET}/.devflow/archon/reconciler.sh ${TARGET} >> ${TARGET}/logs/reconcile.log 2>&1"
            echo "CRONEOF"
            echo "crontab -u ${CRON_USER} /tmp/cron.\$\$"
            echo "rm /tmp/cron.\$\$"
            echo "echo '✅ crontab 已安装'"
            ;;

        external)
            echo "# 请在宿主机配置调度器，定期触发以下命令："
            echo ""
            echo "# dispatch（每 5 分钟）:"
            echo "docker exec <容器名> bash ${TARGET}/.devflow/archon/dispatch.sh ${TARGET}"
            echo ""
            echo "# reconcile（每 15 分钟）:"
            echo "docker exec <容器名> bash ${TARGET}/.devflow/archon/reconciler.sh ${TARGET}"
            ;;

        none)
            echo "# --scheduler none：不安装调度器"
            echo "# 如需手动触发："
            echo "#   bash ${TARGET}/.devflow/archon/dispatch.sh ${TARGET}"
            echo "#   bash ${TARGET}/.devflow/archon/reconciler.sh ${TARGET}"
            ;;
    esac
    echo ""
fi

echo "══════════════════════════════════════"
echo "安装完成。"
if [ "$FRONTEND" = true ]; then
    echo "  Gate 流程：/grill-with-docs → /to-spec → /to-tickets → /implement → AFK 自动消化"
fi
if [ "$BACKEND" = true ]; then
    echo "  后端管线：dispatch.sh + reconciler.sh 通过 $SCHEDULER 调度"
fi
echo "══════════════════════════════════════"
