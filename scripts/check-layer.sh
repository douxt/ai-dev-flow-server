#!/bin/bash
# 判定当前分支改动属于哪个层级
# 用法: bash check-layer.sh [git-range]  默认: main..HEAD
set -euo pipefail
RANGE="${1:-main..HEAD}"
PIPELINE=$(git diff "$RANGE" --name-only | grep -cE '^(\.devflow/|\.archon/|\.github/|workflows/|Dockerfile|systemd/)' || true)
TOTAL=$(git diff "$RANGE" --name-only | wc -l)
if [ "$PIPELINE" -eq 0 ]; then echo "APP"
elif [ "$PIPELINE" -eq "$TOTAL" ]; then echo "PIPELINE"
else echo "MIXED"; fi
