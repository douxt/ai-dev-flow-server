#!/bin/bash
# bash-firewall.sh — PreToolUse 钩子，拦截 Bash 中的非 worktree 文件写入
# matcher: Bash，排在 rtk 之后
set -euo pipefail

# 同目录解析——symlink 部署落在 ~/.claude/hooks/，模板部署落在项目 hooks/，容器可测
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

# 一次性读取 stdin（$() 子 shell 会消耗 stdin，不能多次 jq）
INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || true)
[ -z "$CMD" ] && exit 0

# 真实 CC hook JSON 的 cwd 在顶层 .cwd（tool_input 无 cwd 字段）——旧取法恒空，
# 相对路径全部按钩子进程 PWD 判基准（2026-09-09 修复轮实测发现）
CWD=$(echo "$INPUT" | jq -r '.tool_input.cwd // .cwd // ""' 2>/dev/null || true)
[ -z "$CWD" ] && CWD="$PWD"

# 快速豁免：纯查询命令（无文件写入可能）
case "$CMD" in
  git\ status*|git\ log*|git\ diff*|git\ branch*|git\ stash\ list*|git\ remote*)
    exit 0 ;;
  git\ -C*|git\ add*|git\ commit*|git\ fetch*|git\ push*|git\ pull*|git\ merge*|git\ rebase*|git\ tag*)
    exit 0 ;;
  ls*|find*|grep*|head\ *|tail\ *|less*|wc*)
    exit 0 ;;
  cd*|pwd*|which*|type*|whoami*)
    exit 0 ;;
  docker\ ps*|docker\ images*|docker\ logs*)
    exit 0 ;;
  docker\ exec*)
    exit 0 ;;
  npm\ run\ dev*|npm\ test*)
    exit 0 ;;
  npm\ install*|npm\ i|npm\ i\ *|npm\ ci*|npm\ add*|npm\ update*|npm\ upgrade*|npm\ uninstall*)
    >&2 echo ""
    >&2 echo "╔══════════════════════════════════════════════════╗"
    >&2 echo "║  npm install 拦截 — node_modules 请用软链接       ║"
    >&2 echo "╠══════════════════════════════════════════════════╣"
    >&2 echo "║                                                  ║"
    >&2 echo "║  ln -s ~/projects/UMES3/react-scaffold/node_modules \\"
    >&2 echo "║        <worktree>/react-scaffold/node_modules    ║"
    >&2 echo "║                                                  ║"
    >&2 echo "║  或直接用 wt dev，自动软链接 + 端口隔离。         ║"
    >&2 echo "║                                                  ║"
    >&2 echo "║  如确实需要 npm install（新增依赖等），请确认。   ║"
    >&2 echo "╚══════════════════════════════════════════════════╝"
    exit 2 ;;
  kill*|killall*|pkill*)
    exit 0 ;;
  rm*|rmdir*)
    exit 0 ;;
  git\ checkout\ --\ *)
    >&2 echo ""
    >&2 echo "╔══════════════════════════════════════════════════╗"
    >&2 echo "║  git checkout -- 禁止 — 用 git stash 或 .bak 恢复 ║"
    >&2 echo "╠══════════════════════════════════════════════════╣"
    >&2 echo "║  CLAUDE.md 规则:                                 ║"
    >&2 echo "║  永不 git checkout -- <file>                     ║"
    >&2 echo "║  用 git stash 或 cp .bak 恢复                    ║"
    >&2 echo "╚══════════════════════════════════════════════════╝"
    exit 2 ;;
esac

# 提取目标文件
TARGETS=$(extract_target_files "$CMD")
[ -z "$TARGETS" ] && exit 0

BLOCKED=()
while IFS= read -r target; do
  [ -z "$target" ] && continue
  abs=$(resolve_relative_path "$target" "$CWD")

  # 豁免路径
  case "$abs" in
    /tmp/*|/dev/stdout|/dev/stderr|/dev/fd/*|/dev/*|/proc/*|/sys/*) continue ;;
    "$HOME/.claude/logs"*) continue ;;
    /run/*|/var/run/*) continue ;;
    */node_modules/*) continue ;;   # 依赖目录非源码资产（反馈案例：cp 借主仓 node_modules）
  esac

  # 文档类目标 → 与 file-guard Edit 通道同口径放行（P1-2，豁免口径单一事实源）
  is_doc_target "$abs" && continue

  if is_protected_repo "$abs" && ! is_in_worktree "$abs"; then
    BLOCKED+=("$abs")
  fi
done <<< "$TARGETS"

if [ ${#BLOCKED[@]} -gt 0 ]; then
  targets_nl=$(printf '%s\n' "${BLOCKED[@]}")
  log_block "bash-firewall" "main_repo" "$targets_nl" "cmd=${CMD:0:120}"

  >&2 echo ""
  >&2 echo "╔══════════════════════════════════════════════════╗"
  >&2 echo "║  主仓库保护 — 命令存在非 worktree 文件写入         ║"
  >&2 echo "╠══════════════════════════════════════════════════╣"
  >&2 echo "║  目标文件:"
  for f in "${BLOCKED[@]}"; do
    >&2 echo "║    ▸ $f"
  done
  >&2 echo "╠══════════════════════════════════════════════════╣"
  block_description "main_repo" "${BLOCKED[0]}" | while IFS= read -r l; do
    >&2 printf "║  %-46s ║\n" "$l"
  done
  >&2 echo "╚══════════════════════════════════════════════════╝"
  exit 2
fi

exit 0
