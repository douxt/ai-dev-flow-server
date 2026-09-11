#!/bin/bash
# NAS 漂移对账 —— 比对 NAS 在版文件与仓库 main 分支内容（只读，无副作用）
#
# 用法：bash nas/check-drift.sh [user@host]        # 默认 root@nas
# 退出码：0=全部一致；1=存在漂移或 NAS 不可达
#
# 背景：2026-09-11 发现 NAS 在版 health-check.sh（3410B/83 行）与仓库版
# （1486B/46 行）完全不同，导致"照仓库修 = 修的不是线上那份"。
set -uo pipefail

NAS=${1:-root@nas}
REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
SSH_OPTS=(-nT -o BatchMode=yes -o ConnectTimeout=6)

# 仓库路径|NAS 路径|说明
PAIRS=(
    "nas/health-check.sh|/volume1/docker/langbot/health-check.sh|巡检脚本"
    "nas/clean-zombie-ssh.sh|/usr/local/bin/clean-zombie-ssh.sh|僵尸清理"
    "docs/references/nas-crontab-snapshot-20260911.txt|/etc/crontab|cron 快照"
)

drift=0
checked=0

echo "=== NAS 漂移对账（仓库 main ↔ $NAS）==="
for entry in "${PAIRS[@]}"; do
    IFS='|' read -r repo_file nas_file desc <<< "$entry"

    local_md5=$(git -C "$REPO_ROOT" show "main:$repo_file" 2>/dev/null | md5sum | awk '{print $1}')
    if [ -z "${local_md5:-}" ]; then
        local_md5=$(md5sum "$REPO_ROOT/$repo_file" 2>/dev/null | awk '{print $1}')
    fi

    remote_md5=$(timeout 20 ssh "${SSH_OPTS[@]}" "$NAS" \
        "md5sum '$nas_file' 2>/dev/null" | awk '{print $1}')
    remote_md5=${remote_md5:-}

    checked=$((checked + 1))
    if [ -n "$remote_md5" ] && [ "$local_md5" = "$remote_md5" ]; then
        echo "OK    [$desc] $nas_file"
    elif [ -z "$remote_md5" ]; then
        echo "DOWN  [$desc] $nas_file —— NAS 不可达或文件不存在"
        drift=1
    else
        echo "DRIFT [$desc] $nas_file"
        echo "        repo=$local_md5  nas=$remote_md5  ($repo_file)"
        drift=1
    fi
done

echo "=== 比对 $checked 项，结果：$([ "$drift" -eq 0 ] && echo '全部一致' || echo '存在漂移') ==="
[ "$drift" -eq 0 ] || echo "处置：把 NAS 在版文件回灌到仓库（nas/README.md 记录了基线流程），或在 README 基线表中更新 md5。"
exit "$drift"
