#!/bin/bash
# audit-log.sh — 事后审计所有文件修改
# 由 ai-dev-flow-server install.sh 部署到 ~/.claude/hooks/

TOOL="$1"
FILE="$2"
AUDIT_LOG="$HOME/.claude/logs/file-audit.jsonl"

mkdir -p "$(dirname "$AUDIT_LOG")"
echo "{\"timestamp\":\"$(date -Iseconds)\",\"tool\":\"$TOOL\",\"file\":\"$FILE\",\"pwd\":\"$(pwd)\"}" >> "$AUDIT_LOG"
exit 0
