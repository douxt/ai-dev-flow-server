#!/bin/bash
# common.sh — 多层防御共享工具函数
# 被 bash-firewall.sh / file-guard.sh / audit-log.sh source

PROTECTED_REPOS=(
  "$HOME/projects/UMES3"
  "$HOME/projects/fa56-php"
  "$HOME/projects/CeLiangBen"
  "$HOME/projects/udimc_store"
  "$HOME/projects/claude-config"
  "$HOME/dev/MAF-Hub"
  "$HOME/cc-stack"
  "/mnt/d/Github/udimc_store"
  "/mnt/d/Github/fa56_mini_new"
)

get_repo_root() {
  local file="$1"
  [ -z "$file" ] && return 1
  git -C "$(dirname "$file")" rev-parse --show-toplevel 2>/dev/null || true
}

is_protected_repo() {
  local path="$1"
  local abs
  abs=$(realpath "$path" 2>/dev/null || echo "$path")
  for repo in "${PROTECTED_REPOS[@]}"; do
    case "$abs" in
      "$repo"|"$repo/"*) return 0 ;;
    esac
  done
  return 1
}

is_in_worktree() {
  local path="$1"
  local abs
  abs=$(realpath "$path" 2>/dev/null || echo "$path")
  case "$abs" in
    "$HOME/wt/"*) return 0 ;;
  esac
  case "$abs" in
    *"/.claude/worktrees/"*) return 0 ;;
  esac
  return 1
}

# 文档类目标豁免——口径镜像 file-guard.sh 的 *.md 豁免（2026-09-09 UMES3 反馈 P1-2：
# Edit 通道放行 RULES.md 而 Bash 重定向拦截，两通道豁免不一致）。
# 刻意只含 .md 不收 json/yaml/txt——file-guard 也只豁免 *.md，放宽会制造反向不对称
# （cat > package.json 放行而 Edit package.json 被拦）。改口径必须两处同步。
is_doc_target() {
  case "$1" in
    *.md) return 0 ;;
  esac
  return 1
}

BLOCK_LOG="$HOME/.claude/logs/blocked-writes.jsonl"

log_block() {
    local hook="$1" reason="$2" targets="$3" detail="${4:-}"
    local ts; ts=$(date -Iseconds)
    local dir; dir=$(dirname "$BLOCK_LOG")
    mkdir -p "$dir"
    printf '{"ts":"%s","hook":"%s","reason":"%s","targets":%s,"detail":"%s","cwd":"%s"}\n' \
        "$ts" "$hook" "$reason" \
        "$(echo "$targets" | jq -R -s -c 'split("\n") | map(select(length>0))')" \
        "$detail" "$PWD" >> "$BLOCK_LOG"
}

block_description() {
    local reason="$1" file="${2:-}"
    case "$reason" in
        main_repo)
            echo "当前在受保护仓库中直接操作文件。主仓库是唯一真实来源，直接修改有丢失风险。"
            echo ""
            echo "操作:"
            echo "  1. wt create <任务名>  创建隔离 worktree"
            echo "  2. cd ~/wt/<项目>/<任务>  进入已有 worktree"
            echo "  3. wt dev --path <目录>  指定任意 worktree 路径"
            ;;
        protected)
            echo "此文件是安全配置文件，受自保护，不可通过自动化工具修改。"
            echo "如需修改，请手动用编辑器操作。"
            ;;
        sensitive)
            echo "此文件为敏感文件（密钥/证书/凭证），禁止工具链操作。"
            echo "如需使用，确认路径无误后手动操作。"
            ;;
        *)
            echo "写入路径不在允许范围内。"
            echo "请使用 wt create 或 wt dev --path 在隔离环境中操作。"
            ;;
    esac
}

resolve_relative_path() {
  local path="$1" cwd="${2:-$PWD}"
  # 包含 & 后跟数字或 - 的不是合法文件路径（fd 复制残留）
  case "$path" in
    *'&'[0-9]* | *'&-'*) return 1 ;;
  esac
  case "$path" in
    /*) echo "$path" ;;
    ~*) echo "${HOME}${path:1}" ;;
    *) echo "${cwd%/}/${path}" ;;
  esac
}

# 校验候选路径是否为合法文件系统路径，返回 0=合法，1=丢弃
sanitize_path() {
    local raw="$1"
    [[ -z "$raw" ]] && return 1
    # 1. strip 首尾引号
    local clean; clean=$(echo "$raw" | sed -e 's/^["'\'']//' -e 's/["'\'']$//')
    [[ -z "$clean" ]] && return 1
    # 2. 必须以 / 或 ~ 开头
    [[ "$clean" =~ ^(/|~) ]] || return 1
    # 3. 不含控制字符和特殊符号
    [[ "$clean" =~ [\<\>\"\'[:cntrl:]] ]] && return 1
    [[ "$clean" =~ \\[tnr] ]] && return 1
    # 4. 不含中文
    echo "$clean" | grep -qP '[\x{4e00}-\x{9fff}]' 2>/dev/null && return 1
    # 5. 不含 :// (URL/data URI)
    [[ "$clean" == *'://'* ]] && return 1
    # 6. 不含 @ (email/commit 模板)
    [[ "$clean" == *'@'* ]] && return 1
    echo "$clean"
    return 0
}

# 从 Bash 命令中提取目标文件路径（启发式）
# 返回换行分隔的路径列表
extract_target_files() {
  local cmd="$1"
  local results=()

  # 先清掉 fd 复制/关闭（2>&1、>&2、2>&-），这些不涉及文件
  local clean_cmd
  clean_cmd=$(echo "$cmd" | sed -E 's/[12]?>&[0-9]+//g; s/[12]?>&-//g')
  # 重定向 > file, >> file, &> file, 1> file, 2> file
  # 用 grep -o 提取 > 后的第一个非空白 token
  local redirects
  redirects=$(echo "$clean_cmd" | grep -oP '[12&]?>>?(?:\s*\S+)' 2>/dev/null || true)
  if [ -n "$redirects" ]; then
    while IFS= read -r token; do
      local file
      file=$(echo "$token" | sed -E 's/^[12&]?>>?\s*//; s/\s.*$//')
      # 防御：如果剥离后仍残留 fd 引用（&N、&-），跳过
      case "$file" in
        '&'[0-9]* | '&-') continue ;;
      esac
      [ -n "$file" ] && results+=("$file")
    done <<< "$redirects"
  fi

  # tee file, tee -a file
  local tee_targets
  tee_targets=$(echo "$cmd" | grep -oP '\btee\s+(?:-a\s+)?(\S+)' 2>/dev/null || true)
  if [ -n "$tee_targets" ]; then
    while IFS= read -r token; do
      local file
      file=$(echo "$token" | sed -E 's/^tee\s+(-a\s+)?//; s/\s.*$//')
      [ -n "$file" ] && [ "$file" != "|" ] && results+=("$file")
    done <<< "$tee_targets"
  fi

  # sed -i file, awk -i inplace file, perl -i file
  local inplace
  inplace=$(echo "$cmd" | grep -oP '\b(?:sed|awk|perl)\s+.*-i[^;|&]*\s+(\S+)' 2>/dev/null || true)
  if [ -n "$inplace" ]; then
    local file
    file=$(echo "$inplace" | awk '{print $NF}')
    [ -n "$file" ] && results+=("$file")
  fi

  # cp src dst, mv src dst → 提取最后一个参数
  if echo "$cmd" | grep -qP '(?:^|[|;&])\s*cp\s'; then
    local dst
    dst=$(echo "$cmd" | awk '{print $NF}')
    [ -n "$dst" ] && results+=("$dst")
  fi
  if echo "$cmd" | grep -qP '(?:^|[|;&])\s*mv\s'; then
    local dst
    dst=$(echo "$cmd" | awk '{print $NF}')
    [ -n "$dst" ] && results+=("$dst")
  fi

  # dd of=file
  local dd_targets
  dd_targets=$(echo "$cmd" | grep -oP '\bdd\s+.*of=(\S+)' 2>/dev/null || true)
  if [ -n "$dd_targets" ]; then
    local file
    file=$(echo "$dd_targets" | sed -E 's/.*of=//; s/\s.*$//')
    [ -n "$file" ] && results+=("$file")
  fi

  # 过滤：只保留合法路径
  local filtered=()
  for f in "${results[@]}"; do
    local clean; clean=$(sanitize_path "$f" 2>/dev/null || true)
    [[ -n "$clean" ]] && filtered+=("$clean")
  done
  printf '%s\n' "${filtered[@]}"
}
