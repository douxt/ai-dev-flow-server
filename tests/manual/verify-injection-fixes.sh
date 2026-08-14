#!/bin/bash
# 手动验证三个注入 bug 修复（幂等性模拟）
set -euo pipefail

WT="$(cd "$(dirname "$0")/../.." && pwd)"
TEST_DIR=$(mktemp -d)
cd "$TEST_DIR"
echo "测试目录: $TEST_DIR"

# ── Bug 1 验证: sed 版本通配 ──
echo ""
echo "=== Bug 1: 版本标记删除 ==="
cat > test1.md << 'EOF'
# Header
some content
<!-- ai-dev-flow-server v3.2 -->
block content line 1
block content line 2
<!-- ai-dev-flow-server end -->
trailing content
EOF
echo "--- 新格式 (v3.2) 删除后 ---"
sed '/<!-- ai-dev-flow-server\( v[0-9.]*\)\? -->/,/<!-- ai-dev-flow-server end -->/d' test1.md

cat > test1b.md << 'EOF'
<!-- ai-dev-flow-server -->
old block
<!-- ai-dev-flow-server end -->
EOF
echo "--- 旧格式（无版本）删除后（应为空）---"
sed '/<!-- ai-dev-flow-server\( v[0-9.]*\)\? -->/,/<!-- ai-dev-flow-server end -->/d' test1b.md
echo "[END]"

# ── Bug 2 验证: RULES.md 幂等性 ──
echo ""
echo "=== Bug 2: RULES.md 5 次 update 幂等性 ==="
cat > rules.md << 'EOF'
# My Rules
some content
<!-- DEVLOW:TEST-QUALITY-START -->
old content
<!-- DEVLOW:TEST-QUALITY-END -->
trailing
EOF
cp "$WT/templates/RULES.md.test-quality" tmpl.md
for i in 1 2 3 4 5; do
  if grep -q "TEST-QUALITY-START" rules.md; then
    sed -i '/<!-- DEVLOW:TEST-QUALITY-START -->/,/<!-- DEVLOW:TEST-QUALITY-END -->/d' rules.md
  fi
  cat tmpl.md >> rules.md
  echo "第${i}次: START=$(grep -c 'TEST-QUALITY-START' rules.md) END=$(grep -c 'TEST-QUALITY-END' rules.md) trailing=$(grep -c '^trailing' rules.md)"
done

echo ""
echo "=== Bug 2: 腐败状态（3 START 1 END）恢复 ==="
cat > corrupt.md << 'EOF'
# Rules
<!-- DEVLOW:TEST-QUALITY-START -->
<!-- DEVLOW:TEST-QUALITY-START -->
<!-- DEVLOW:TEST-QUALITY-START -->
<!-- DEVLOW:TEST-QUALITY-END -->
trailing
EOF
sed -i '/<!-- DEVLOW:TEST-QUALITY-START -->/,/<!-- DEVLOW:TEST-QUALITY-END -->/d' corrupt.md
cat tmpl.md >> corrupt.md
echo "修复后: START=$(grep -c 'TEST-QUALITY-START' corrupt.md) END=$(grep -c 'TEST-QUALITY-END' corrupt.md) trailing=$(grep -c '^trailing' corrupt.md)"

# ── Bug 3 验证: merge-settings.py 去重 ──
echo ""
echo "=== Bug 3: 重复 matcher 组聚合去重 ==="
mkdir -p proj
# 模拟已有 settings：suggest-rules 注册 3 次（历史 bug 产物）
cat > proj/settings.json << 'EOF'
{
  "hooks": {
    "PostToolUse": [
      {"matcher": "Edit|Write|Bash", "hooks": [
        {"type": "command", "command": "/home/x/.claude/hooks/audit-log.sh"}
      ]},
      {"matcher": "Edit|Write", "hooks": [
        {"type": "command", "command": "/home/x/.claude/hooks/suggest-rules.sh"}
      ]},
      {"matcher": "Edit|Write", "hooks": [
        {"type": "command", "command": "/home/x/.claude/hooks/suggest-rules.sh"}
      ]},
      {"matcher": "Edit|Write", "hooks": [
        {"type": "command", "command": "/home/x/.claude/hooks/suggest-rules.sh"}
      ]}
    ]
  }
}
EOF
# 模板
cat > tmpl-settings.json << 'EOF'
{
  "hooks": {
    "PostToolUse": [
      {"matcher": "Edit|Write", "hooks": [
        {"type": "command", "command": "__CLAUDE_HOME__/hooks/suggest-rules.sh"}
      ]}
    ]
  }
}
EOF
python3 "$WT/scripts/merge-settings.py" proj/settings.json tmpl-settings.json proj/merged.json
echo "合并后 suggest-rules 注册次数: $(grep -c 'suggest-rules' proj/merged.json)"
echo "合并后 Edit|Write 组数: $(python3 -c "import json; d=json.load(open('proj/merged.json')); print(len([g for g in d['hooks']['PostToolUse'] if g['matcher']=='Edit|Write']))")"
echo "audit-log 保留: $(grep -c 'audit-log' proj/merged.json)"

echo ""
echo "=== 全部验证完成 ==="
rm -rf "$TEST_DIR"
