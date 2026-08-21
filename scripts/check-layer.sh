#!/bin/bash
# 判定当前分支改动属于哪个层级
# 用法: bash check-layer.sh [git-range]  默认: main..HEAD
set -euo pipefail
RANGE="${1:-main..HEAD}"
PIPELINE=$(git diff "$RANGE" --name-only | grep -vE '^issues/' | grep -cE '^(\.devflow/|\.archon/|\.github/|workflows/|Dockerfile|systemd/)' || true)
# pipefail 下空 diff 时 grep -vE rc=1 使整个管道非零，set -e 直接退出——必须兜底
TOTAL=$(git diff "$RANGE" --name-only | grep -vE '^issues/' | wc -l || true)
if [ "$PIPELINE" -eq 0 ]; then echo "APP"
elif [ "$PIPELINE" -eq "$TOTAL" ]; then echo "PIPELINE"
else echo "MIXED"; fi
