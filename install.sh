#!/bin/bash
# install.sh — ai-dev-flow-server 一键安装到目标项目
# 用法: bash install.sh <项目路径> [--tech-stack <python|node|go>] [--test-cmd <cmd>] [--lint-cmd <cmd>] [--pkg-mgr <npm|yarn|pnpm|uv|pip|cargo>]
set -euo pipefail

# ── 参数 ──
TARGET=""
TECH_STACK=""
TEST_CMD=""
LINT_CMD=""
PKG_MGR=""
UPDATE_MODE=false
while [ $# -gt 0 ]; do
    case "$1" in
        --tech-stack) TECH_STACK="$2"; shift 2 ;;
        --test-cmd)   TEST_CMD="$2"; shift 2 ;;
        --lint-cmd)   LINT_CMD="$2"; shift 2 ;;
        --pkg-mgr)    PKG_MGR="$2"; shift 2 ;;
        --update)     UPDATE_MODE=true; shift ;;
        --help)
            echo "用法:"
            echo "  bash install.sh <项目路径> [--tech-stack node|python|go] [--test-cmd ...]"
            echo "  bash install.sh <项目路径> --update   # 仅更新 .devflow/ + workflows，保留 config 和 gate-state"
            exit 0 ;;
        *)            TARGET="$1"; shift ;;
    esac
done

if [ -z "$TARGET" ]; then
    echo "❌ 需要指定目标项目路径"; echo "用法: bash install.sh <项目路径> [--tech-stack node|python|go]"; exit 1
fi

TARGET=$(realpath "$TARGET" 2>/dev/null || echo "$TARGET")
SOURCE=$(cd "$(dirname "$0")" && pwd)

# ── update 模式 ──
if [ "$UPDATE_MODE" = true ]; then
    echo "── ai-dev-flow-server 更新模式 ──"
    echo "  源: $SOURCE"
    echo "  目标: $TARGET"
    if [ -d "$SOURCE/.git" ]; then
        echo "  git pull ..."
        cd "$SOURCE" && git pull --rebase --quiet 2>/dev/null || echo "  ⚠️  git pull 失败，继续用当前版本"
    fi

    deploy_file() {
        local src="$1" dst="$2"
        [ -f "$src" ] || { echo "  ❌ 源文件不存在: $src"; return 1; }
        mkdir -p "$(dirname "$dst")"
        cp -f "$src" "$dst" || { echo "  ❌ cp 失败: $dst"; return 1; }
        diff "$src" "$dst" >/dev/null || { echo "  ⚠️ diff 校验失败: $dst"; return 1; }
        return 0
    }

    echo "  更新 archon/ ..."
    deploy_file "$SOURCE/archon/dispatch.sh"           "$TARGET/.devflow/archon/dispatch.sh"
    deploy_file "$SOURCE/archon/reconciler.sh"         "$TARGET/.devflow/archon/reconciler.sh"
    deploy_file "$SOURCE/archon/auto-execute-afk.yaml" "$TARGET/.devflow/archon/auto-execute-afk.yaml"
    mkdir -p "$TARGET/.archon/workflows"
    deploy_file "$SOURCE/archon/auto-execute-afk.yaml" "$TARGET/.archon/workflows/auto-execute-afk.yaml"

    echo "  更新 scripts/ ..."
    deploy_file "$SOURCE/archon/status.sh"             "$TARGET/.devflow/scripts/status.sh"
    deploy_file "$SOURCE/scripts/check-layer.sh"       "$TARGET/.devflow/scripts/check-layer.sh"
    for py in "$SOURCE/scripts/"*.py; do
        [ -f "$py" ] && deploy_file "$py" "$TARGET/.devflow/scripts/$(basename "$py")"
    done

    echo "  更新 knowledge/ ..."
    for md in "$SOURCE/knowledge/"*.md; do
        [ -f "$md" ] && deploy_file "$md" "$TARGET/.devflow/knowledge/$(basename "$md")"
    done

    echo "  更新 workflows/ ..."
    mkdir -p "$HOME/.claude/workflows"
    for js in "$SOURCE/workflows/"*.js; do
        [ -f "$js" ] && deploy_file "$js" "$HOME/.claude/workflows/$(basename "$js")"
    done

    echo "  更新 issue 模板 ..."
    mkdir -p "$TARGET/issues"
    deploy_file "$SOURCE/templates/issue-template.md" "$TARGET/issues/TEMPLATE.md"

    echo "  设置可执行权限 ..."
    chmod +x "$TARGET/.devflow/archon/dispatch.sh" "$TARGET/.devflow/archon/reconciler.sh" 2>/dev/null || true
    chmod +x "$TARGET/.devflow/scripts/"*.sh 2>/dev/null || true

    echo "  确保 logs/ ..."
    mkdir -p "$TARGET/logs"

    echo "✅ 更新完成（config.yaml 和 .gate-state 不受影响）"
    exit 0
fi

echo "╔══════════════════════════════════════╗"
echo "║  ai-dev-flow-server 安装器          ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "  源: $SOURCE"
echo "  目标: $TARGET"
echo ""

# ── 0. 预检 ──
echo "── 步骤 0: 预检 ──"
ERRORS=0

if [ ! -d "$TARGET/.git" ]; then
    echo "  ❌ 不是 git 仓库（缺少 .git/）"
    ERRORS=$((ERRORS + 1))
else
    echo "  ✅ git 仓库"
fi

if command -v gh >/dev/null 2>&1; then
    if gh auth status >/dev/null 2>&1; then
        echo "  ✅ gh CLI 已认证"
    else
        echo "  ⚠️  gh CLI 未认证，请运行: gh auth login"
    fi
else
    echo "  ⚠️  gh CLI 未安装，PR 创建功能需要 gh"
fi

if [ ! -f "$TARGET/.claude/CLAUDE.md" ] && [ ! -f "$TARGET/CLAUDE.md" ]; then
    echo "  ⚠️  缺少 CLAUDE.md（建议创建，说明技术栈和项目结构）"
else
    echo "  ✅ CLAUDE.md 存在"
fi

ISSUES_DIR="$TARGET/issues"
if [ ! -d "$ISSUES_DIR" ]; then
    echo "  ⚠️  issues/ 目录不存在，将自动创建"
    mkdir -p "$ISSUES_DIR"
    touch "$ISSUES_DIR/.gitkeep"
fi
echo "  ✅ issues/ 目录就绪"

# 推断技术栈
if [ -z "$TECH_STACK" ]; then
    if [ -f "$TARGET/package.json" ]; then
        TECH_STACK="node"
    elif [ -f "$TARGET/pyproject.toml" ] || [ -f "$TARGET/setup.py" ] || [ -f "$TARGET/requirements.txt" ]; then
        TECH_STACK="python"
    elif [ -f "$TARGET/go.mod" ]; then
        TECH_STACK="go"
    else
        TECH_STACK="node"  # 默认
        echo "  ℹ️  无法推断技术栈，默认使用 node"
    fi
fi
echo "  ℹ️  技术栈: $TECH_STACK"

# 技术栈默认值
case "$TECH_STACK" in
    node)
        [ -z "$PKG_MGR" ] && PKG_MGR="npm"
        [ -z "$TEST_CMD" ] && TEST_CMD="npm test"
        [ -z "$LINT_CMD" ] && LINT_CMD="npm run lint"
        ;;
    python)
        [ -z "$PKG_MGR" ] && PKG_MGR="uv"
        [ -z "$TEST_CMD" ] && TEST_CMD="uv run pytest"
        [ -z "$LINT_CMD" ] && LINT_CMD="uv run ruff check"
        ;;
    go)
        [ -z "$PKG_MGR" ] && PKG_MGR="go"
        [ -z "$TEST_CMD" ] && TEST_CMD="go test ./..."
        [ -z "$LINT_CMD" ] && LINT_CMD="go vet ./..."
        ;;
    *)
        echo "  ❌ 不支持的技术栈: $TECH_STACK"; exit 1
        ;;
esac

echo "  包管理: $PKG_MGR | 测试: $TEST_CMD | Lint: $LINT_CMD"

# 测试命令是否存在
if ! eval "cd \"$TARGET\" && command -v ${TEST_CMD%% *}" >/dev/null 2>&1; then
    echo "  ⚠️  测试命令 '${TEST_CMD%% *}' 不可用，请确认依赖已安装"
fi

if [ $ERRORS -gt 0 ]; then
    echo ""; echo "❌ 预检未通过（$ERRORS 项），请修正后重新运行"; exit 1
fi
echo ""

# ── 1. 生成 config.yaml ──
echo "── 步骤 1: 生成 .devflow/config.yaml ──"

PROJECT_NAME=$(basename "$TARGET")
REPO_URL=$(cd "$TARGET" && git remote get-url origin 2>/dev/null || echo "git@github.com:user/${PROJECT_NAME}.git")

mkdir -p "$TARGET/.devflow"
cat > "$TARGET/.devflow/config.yaml" << DEVCONFIG
# .devflow/config.yaml — 由 ai-dev-flow-server install.sh 生成
project:
  name: ${PROJECT_NAME}
  repo_url: ${REPO_URL}
  workspace: ${TARGET}

tech_stack:
  language: ${TECH_STACK}
  package_manager: ${PKG_MGR}
  test_command: ${TEST_CMD}
  lint_command: ${LINT_CMD}

dispatch:
  branch_prefix: ai/
  max_retries: 3
  poll_interval_min: 5

review:
  cross_review: false
  constitution_check: true

notify:
  telegram_chat_id: "<从 MAF-Hub config/telegram.json 复制>"
  telegram_bot_token: "<同上>"
DEVCONFIG

echo "  ✅ .devflow/config.yaml 已生成（请手动填写 telegram_chat_id 和 telegram_bot_token）"
echo ""

# ── 2. 复制 workflows ──
echo "── 步骤 2: 复制 gate 脚本到 ~/.claude/workflows/ ──"
mkdir -p "$HOME/.claude/workflows"
cp "$SOURCE/workflows/"*.js "$HOME/.claude/workflows/"
echo "  ✅ 6 个 gate 脚本已安装"
echo ""

# ── 3. 复制 .gate-state ──
echo "── 步骤 3: 复制 .gate-state ──"
if [ -f "$TARGET/.gate-state" ]; then
    echo "  ⚠️  .gate-state 已存在，跳过（保留现有）"
else
    cp "$SOURCE/templates/gate-state.yml" "$TARGET/.gate-state"
    echo "  ✅ .gate-state 已创建"
fi
echo ""

# ── 4. 追加 CLAUDE.md ──
echo "── 步骤 4: 追加 CLAUDE.md 片段（幂等）──"
CLAUDE_MD="$TARGET/.claude/CLAUDE.md"
if [ ! -f "$CLAUDE_MD" ]; then
    CLAUDE_MD="$TARGET/CLAUDE.md"
fi
if [ ! -f "$CLAUDE_MD" ]; then
    mkdir -p "$TARGET/.claude"
    CLAUDE_MD="$TARGET/.claude/CLAUDE.md"
    touch "$CLAUDE_MD"
fi

if grep -q "ai-dev-flow-server" "$CLAUDE_MD" 2>/dev/null; then
    echo "  ⚠️  CLAUDE.md 已含 ai-dev-flow-server 标记，跳过追加"
else
    cat "$SOURCE/templates/CLAUDE.md.append" >> "$CLAUDE_MD"
    echo "  ✅ CLAUDE.md 片段已追加"
fi
echo ""

# ── 5. 复制 devflow 文件 ──
echo "── 步骤 5: 复制 .devflow/ 文件 ──"
mkdir -p "$TARGET/.devflow/archon" "$TARGET/.devflow/scripts" "$TARGET/.devflow/knowledge"

# archon/（含 dispatch.sh, reconciler.sh, auto-execute-afk.yaml）
cp "$SOURCE/archon/dispatch.sh" "$TARGET/.devflow/archon/"
cp "$SOURCE/archon/reconciler.sh" "$TARGET/.devflow/archon/"
cp "$SOURCE/archon/auto-execute-afk.yaml" "$TARGET/.devflow/archon/"
chmod +x "$TARGET/.devflow/archon/dispatch.sh" "$TARGET/.devflow/archon/reconciler.sh"

# scripts/
cp "$SOURCE/scripts/check_constitution.py" "$TARGET/.devflow/scripts/"
cp "$SOURCE/scripts/cost_tracker.py" "$TARGET/.devflow/scripts/"
cp "$SOURCE/scripts/notify.py" "$TARGET/.devflow/scripts/"
cp "$SOURCE/archon/status.sh" "$TARGET/.devflow/scripts/"
cp "$SOURCE/scripts/check-layer.sh" "$TARGET/.devflow/scripts/"
chmod +x "$TARGET/.devflow/scripts/"*.py "$TARGET/.devflow/scripts/status.sh" "$TARGET/.devflow/scripts/check-layer.sh"

# knowledge/
cp "$SOURCE/knowledge/"*.md "$TARGET/.devflow/knowledge/"

echo "  ✅ .devflow/ 文件已复制"
echo ""

# ── 5b. 复制 Archon workflow 到 .archon/workflows/ ──
echo "── 步骤 5b: 注册 Archon workflow ──"
mkdir -p "$TARGET/.archon/workflows"
cp "$SOURCE/archon/auto-execute-afk.yaml" "$TARGET/.archon/workflows/"
echo "  ✅ auto-execute-afk.yaml → .archon/workflows/"
echo ""

# ── 5c. 创建日志目录并设权限 ──
echo "── 步骤 5c: 创建日志目录 ──"
mkdir -p "$TARGET/logs"
if command -v chown >/dev/null 2>&1; then
    chown -R www:www "$TARGET/logs" 2>/dev/null || \
        echo "  ⚠️  无法 chown logs/，请手动: chown www:www $TARGET/logs"
fi
echo "  ✅ logs/ 已创建"
echo ""

# ── 5d. 确保 git upstream 已设置 ──
echo "── 步骤 5d: 检查 git upstream ──"
CURRENT_BRANCH=$(cd "$TARGET" && git branch --show-current 2>/dev/null || echo "")
if [ -n "$CURRENT_BRANCH" ]; then
    if cd "$TARGET" && git rev-parse --abbrev-ref "${CURRENT_BRANCH}@{upstream}" >/dev/null 2>&1; then
        echo "  ✅ upstream 已设置"
    else
        cd "$TARGET" && git push --set-upstream origin "$CURRENT_BRANCH" 2>/dev/null || \
            echo "  ⚠️  无法自动设置 upstream，请手动: git push --set-upstream origin $CURRENT_BRANCH"
    fi
else
    echo "  ⚠️  无法检测当前分支"
fi
echo ""

# ── 6. 复制 issue 模板 ──
echo "── 步骤 6: 复制 issue 模板 ──"
if [ -f "$TARGET/issues/TEMPLATE.md" ]; then
    echo "  ⚠️  issues/TEMPLATE.md 已存在，跳过"
else
    cp "$SOURCE/templates/issue-template.md" "$TARGET/issues/TEMPLATE.md"
    echo "  ✅ issues/TEMPLATE.md 已创建"
fi
echo ""

# ── 7. 创建 _handoff/ 协作目录 ──
echo "── 步骤 7: 创建 _handoff/ Agent 协作目录 ──"
HANDOFF_DIR="$TARGET/_handoff"
if [ -d "$HANDOFF_DIR" ]; then
    echo "  ⚠️  _handoff/ 已存在，跳过"
else
    mkdir -p "$HANDOFF_DIR/outbox/agent-b"
    mkdir -p "$HANDOFF_DIR/inbox/agent-b"
    mkdir -p "$HANDOFF_DIR/archive"
    cp "$SOURCE/templates/_handoff/README.md" "$HANDOFF_DIR/"
    cp "$SOURCE/templates/_handoff/TEMPLATE.md" "$HANDOFF_DIR/"
    echo "  ✅ _handoff/{outbox/agent-b,inbox/agent-b,archive}/ 已创建"
fi
echo ""

# ── 8. 生成 AGENTS.md ──
echo "── 步骤 8: 生成 AGENTS.md ──"
AGENTS_MD="$TARGET/AGENTS.md"
if [ -f "$AGENTS_MD" ]; then
    echo "  ⚠️  AGENTS.md 已存在，跳过"
else
    cat > "$AGENTS_MD" << 'AGENTSEOF'
# AGENTS.md — PROJECT_NAME_PLACEHOLDER

## 本 Agent 身份
- 角色: Agent B
- 项目: PROJECT_NAME_PLACEHOLDER
- 全限定名: PROJECT_NAME_PLACEHOLDER/agent-b
- 能力: gate 流程、功能代码（src/ 内）、需求→PRD→Issue、问题发现
- 壁垒: 无 shell、无部署权限、无合并权限 → 遇阻写 _handoff/outbox/agent-b/

## 项目壁垒（不可修改，见 CLAUDE.md 完整列表）
- 禁止修改：.devflow/、CI/CD 配置、Dockerfile、系统配置
- 禁止操作：systemctl、docker、合并 master
- 代码只能写在 ai/ 分支，合并由 dev-machine/agent-a 完成

## 协作通道
- 写委托: _handoff/outbox/agent-b/
- 读回复: _handoff/inbox/agent-b/
- 消息模板: _handoff/TEMPLATE.md
AGENTSEOF
    sed -i "s/PROJECT_NAME_PLACEHOLDER/${PROJECT_NAME}/g" "$AGENTS_MD"
    echo "  ✅ AGENTS.md 已生成"
fi
echo ""

# ── 9. 部署 git hooks ──
echo "── 步骤 9: 部署 git hooks ──"
HOOKS_DIR="$TARGET/.git/hooks"
mkdir -p "$HOOKS_DIR"
cp "$SOURCE/templates/pre-commit" "$HOOKS_DIR/pre-commit"
cp "$SOURCE/templates/pre-push" "$HOOKS_DIR/pre-push"
chmod +x "$HOOKS_DIR/pre-commit" "$HOOKS_DIR/pre-push"
echo "  ✅ pre-commit + pre-push hook 已部署"
echo ""

# ── 10. 输出检查清单 ──
echo "╔══════════════════════════════════════╗"
echo "║  用户段安装完成                      ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "📋 检查清单："
echo "  [ ] .devflow/config.yaml — 填写 telegram_chat_id 和 telegram_bot_token"
echo "  [ ] .devflow/archon/ — dispatch.sh + reconciler.sh + auto-execute-afk.yaml"
echo "  [ ] .archon/workflows/ — auto-execute-afk.yaml（archon 可发现）"
echo "  [ ] .devflow/scripts/ — check_constitution.py + cost_tracker.py + notify.py"
echo "  [ ] .devflow/knowledge/ — 7 份知识文档"
echo "  [ ] .gate-state — Gate 状态追踪"
echo "  [ ] ~/.claude/skills/ — 7 个 gate skill"
echo "  [ ] logs/ — 确保属主 www（sudo chown www:www logs/）"
echo "  [ ] _handoff/ — Agent 协作收件箱（outbox/agent-b + inbox/agent-b + archive）"
echo "  [ ] AGENTS.md — Agent 身份 + 壁垒声明"
echo "  [ ] .git/hooks/pre-commit — 拦截修改受保护文件"
echo "  [ ] .git/hooks/pre-push — 拦截直推 master"
echo ""

# ── 11. 输出 root 段 ──
PROJECT=$(basename "$TARGET")

echo "╔══════════════════════════════════════╗"
echo "║  root 段（请以 root 身份执行）       ║"
echo "╚══════════════════════════════════════╝"
echo ""

# 生成 service 文件（从模板替换变量）
DISPATCH_SERVICE="/etc/systemd/system/dispatch-${PROJECT}.service"
RECONCILE_SERVICE="/etc/systemd/system/reconcile-${PROJECT}.service"

echo "# 0. 创建 /etc/devflow/${PROJECT}.env（API 密钥文件）"
cat << 'ENVFILE_STEP'
mkdir -p /etc/devflow
API_KEY=$(python3 -c "
import json, os
p = '/home/www/.claude/settings.local.json'
if os.path.exists(p):
    with open(p) as f:
        d = json.load(f)
    print(d.get('env',{}).get('ANTHROPIC_API_KEY','MISSING'))
else:
    print('MISSING')
")
if [ "$API_KEY" != "MISSING" ]; then
  cat > /etc/devflow/${PROJECT}.env << INNER
ANTHROPIC_API_KEY=$API_KEY
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
INNER
  chmod 640 /etc/devflow/${PROJECT}.env
  chown root:www /etc/devflow/${PROJECT}.env
  echo "  ✓ /etc/devflow/${PROJECT}.env (chmod 640)"
else
  echo "  ⚠ /home/www/.claude/settings.local.json 未找到，跳过 .env 创建"
fi
ENVFILE_STEP

echo "# 1. 创建 dispatch-${PROJECT}.service"
cat << DISPATCH_SVC
cat > $DISPATCH_SERVICE << 'EOF'
[Unit]
Description=DevFlow AFK Dispatch — ${PROJECT}
After=network.target

[Service]
Type=oneshot
User=www
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
cat > $RECONCILE_SERVICE << 'EOF'
[Unit]
Description=DevFlow AFK Reconcile — ${PROJECT}
After=network.target

[Service]
Type=oneshot
User=www
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

echo ""
echo "══════════════════════════════════════"
echo "安装完成。执行 root 段后，在 OpenLobby 中开始走 gate 流程："
echo "  /gate-1-grill → /gate-2-prd → /gate-3-issues → AFK 自动消化"
echo "══════════════════════════════════════"
