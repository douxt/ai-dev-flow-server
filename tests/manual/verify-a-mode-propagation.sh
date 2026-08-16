#!/bin/bash
# 手动验证 A 模式传播通道修复：
#   1. RULES.md 注入 sed 从标题删到 END（修复标题重复残留）
#   2. base.append 的 A 模式小节经 --update 到达项目级 .claude/CLAUDE.md
set -euo pipefail

SRC="$(cd "$(dirname "$0")/../.." && pwd)"
TEST_DIR=$(mktemp -d)
cd "$TEST_DIR"
echo "测试目录: $TEST_DIR"

# ── 1. RULES.md 重复标题修复 ──
echo ""
echo "=== 1: RULES.md 旧区块删除（含标题）==="
cat > RULES.md << 'EOF'
# RULES.md

## 数据字段
- some rule

## DevFlow 测试质量规则

> 以下规则由 ai-dev-flow-server 自动部署（`--update` 时同步）。手动修改会被下次 `--update` 覆盖。

<!-- DEVLOW:TEST-QUALITY-START -->

### C0 提交前秒检

- 旧内容

<!-- DEVLOW:TEST-QUALITY-END -->
EOF

sed -i '/^## DevFlow 测试质量规则$/,/<!-- DEVLOW:TEST-QUALITY-END -->/d' RULES.md

if grep -q "DevFlow 测试质量规则\|TEST-QUALITY" RULES.md; then
    echo "❌ 旧区块残留"; grep -n "DevFlow\|TEST-QUALITY" RULES.md; exit 1
fi
echo "✅ 旧区块（含标题）删除干净"

# 模拟追加新模板 → 应只有一份标题
cat "$SRC/templates/RULES.md.test-quality" >> RULES.md
count=$(grep -c "^## DevFlow 测试质量规则$" RULES.md || true)
[ "$count" -eq 1 ] || { echo "❌ 标题重复: $count 份"; exit 1; }
echo "✅ 追加后标题唯一"

# ── 2. A 模式经 --update 到达项目级 CLAUDE.md ──
echo ""
echo "=== 2: base.append A 模式传播 ==="
MOCK="$TEST_DIR/mockproj"
mkdir -p "$MOCK/.claude" "$MOCK/.devflow"
# 模拟已安装项目的 CLAUDE.md（含旧角色段）
cat > "$MOCK/.claude/CLAUDE.md" << 'EOF'
# 项目 CLAUDE.md

项目自定义内容

<!-- ai-dev-flow-server v3.2 -->
## AI Dev Flow v3.2

旧角色段内容
<!-- ai-dev-flow-server end -->
EOF
cat > "$MOCK/.devflow/config.yaml" << 'EOF'
mode: frontend
role: owner
EOF

bash "$SRC/install.sh" "$MOCK" --update >/dev/null 2>&1

if ! grep -q "多票依赖链（A 模式）" "$MOCK/.claude/CLAUDE.md"; then
    echo "❌ A 模式未传播到项目级 CLAUDE.md"; exit 1
fi
# 幂等：再跑一次不应重复
bash "$SRC/install.sh" "$MOCK" --update >/dev/null 2>&1
count=$(grep -c "多票依赖链（A 模式）" "$MOCK/.claude/CLAUDE.md" || true)
[ "$count" -eq 1 ] || { echo "❌ 二次 update A 模式重复: $count 份"; exit 1; }
echo "✅ A 模式已传播且幂等"

echo ""
echo "全部通过"
