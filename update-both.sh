#!/bin/bash
# update-both.sh — 一键同步 claude-config + deploy 两个目标
# 用法: bash update-both.sh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
set +e

echo "[update-both] sync claude-config..."
(cd ~/project/claude-config && git pull --rebase && bash install.sh) || \
(cd ~/projects/claude-config && git pull --rebase && bash install.sh)
echo "[update-both] claude-config: $([ $? -eq 0 ] && echo OK || echo FAIL)"

echo "[update-both] target A: ai-dev-flow-server"
cd "$SCRIPT_DIR" && bash install.sh . --update --mode frontend --role owner
result_a=$?

echo "[update-both] target B: MAF-Hub"
cd ~/project/MAF-Hub && bash "$SCRIPT_DIR/install.sh" . --update --mode frontend --role developer
result_b=$?

echo "[update-both] A=$([ $result_a -eq 0 ] && echo OK || echo FAIL) B=$([ $result_b -eq 0 ] && echo OK || echo FAIL)"
