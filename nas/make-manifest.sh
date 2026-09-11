#!/bin/bash
# 生成 NAS 期望 md5 清单（部署后在开发机运行）
#   读 nas/manifest.tsv（格式：仓库路径|NAS路径|说明）→ 算 md5 → 输出 "<md5>\t<NAS路径>\t<说明>"
#   产物默认 /tmp/expected.md5；MM_DEPLOY=1 时 scp 到 NAS state/expected.md5
# 用途：让 NAS 能在本地比对"在版文件是否被改动"（NAS 24/7，无需仓库与外网）。
set -uo pipefail
REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
TSV="$REPO_ROOT/nas/manifest.tsv"
NAS_HOST=${MM_NAS:-root@nas}
OUT=${MM_OUT:-/tmp/expected.md5}
DEPLOY=${MM_DEPLOY:-0}

: > "$OUT"
while IFS='|' read -r repo_file nas_path desc; do
    case "$repo_file" in ''|\#*) continue ;; esac
    md5=$(md5sum "$REPO_ROOT/$repo_file" 2>/dev/null | awk '{print $1}')
    if [ -z "$md5" ]; then
        echo "MISSING $repo_file" >&2
        continue
    fi
    printf '%s\t%s\t%s\n' "$md5" "$nas_path" "$desc" >> "$OUT"
done < "$TSV"

echo "生成 $OUT（$(wc -l < "$OUT") 项）"
if [ "$DEPLOY" = "1" ]; then
    timeout 25 scp -q "$OUT" "$NAS_HOST:/volume1/docker/langbot/state/expected.md5" \
        && echo "已部署到 NAS state/expected.md5"
fi
