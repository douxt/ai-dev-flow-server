#!/bin/bash
# 手动验证 AGENTS.md 通用接入层（B 场景：安装传播）
# 场景: fresh 各 role / update 幂等 / 自定义不覆盖 / devflow 角色切换往返
set -euo pipefail

SRC="$(cd "$(dirname "$0")/../.." && pwd)"
TEST_DIR=$(mktemp -d)
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "  ✅ $1"; }
bad()  { FAIL=$((FAIL+1)); echo "  ❌ $1"; }

# ── 1. fresh owner: 通用版、无角色段 ──
echo "=== 1. fresh owner 安装 ==="
P1="$TEST_DIR/ownerproj"; mkdir -p "$P1"; git -C "$P1" init -q
bash "$SRC/install.sh" "$P1" --role owner >/dev/null 2>&1
[ -f "$P1/AGENTS.md" ] && grep -q "ai-dev-flow-server:AGENTS-START" "$P1/AGENTS.md" && ok "owner: AGENTS.md 生成且含通用标记" || bad "owner: AGENTS.md 缺失/无标记"
! grep -q "ai-dev-flow-server:AGENT-B-START" "$P1/AGENTS.md" 2>/dev/null && ok "owner: 无 Agent B 角色段" || bad "owner: 误含角色段"
! grep -q "__PROJECT__" "$P1/AGENTS.md" && ok "owner: __PROJECT__ 已替换" || bad "owner: __PROJECT__ 残留"

# ── 2. fresh agent-b: 通用版 + 角色段 ──
echo "=== 2. fresh agent-b 安装 ==="
P2="$TEST_DIR/bproj"; mkdir -p "$P2"; git -C "$P2" init -q
bash "$SRC/install.sh" "$P2" --role agent-b >/dev/null 2>&1
grep -q "ai-dev-flow-server:AGENT-B-START" "$P2/AGENTS.md" && ok "agent-b: 含角色段" || bad "agent-b: 缺角色段"
grep -q "Agent B" "$P2/AGENTS.md" && ok "agent-b: 含 Agent B 内容" || bad "agent-b: 缺 Agent B 内容"

# ── 3. update 幂等 ──
echo "=== 3. update 幂等 ==="
bash "$SRC/install.sh" "$P1" --update >/dev/null 2>&1
bash "$SRC/install.sh" "$P1" --update >/dev/null 2>&1
[ "$(grep -c 'ai-dev-flow-server:AGENTS-START' "$P1/AGENTS.md")" -eq 1 ] && ok "update 二次无重复" || bad "update 产生重复"

# ── 4. 用户自定义 AGENTS.md 不覆盖 ──
echo "=== 4. 自定义不覆盖 ==="
P4="$TEST_DIR/customproj"; mkdir -p "$P4"; git -C "$P4" init -q
bash "$SRC/install.sh" "$P4" --role owner >/dev/null 2>&1
rm -f "$P4/AGENTS.md"
echo "# 用户自定义内容" > "$P4/AGENTS.md"
bash "$SRC/install.sh" "$P4" --update >/dev/null 2>&1
grep -q "用户自定义内容" "$P4/AGENTS.md" && ! grep -q "AGENTS-START" "$P4/AGENTS.md" && ok "自定义保留且未注入" || bad "自定义被覆盖"

# ── 5. devflow 角色切换往返 ──
echo "=== 5. devflow 角色切换 ==="
export PATH="$P2/.devflow/scripts:$PATH"
# agent-b → owner: 通用版保留、角色段删除
devflow role switch owner >/dev/null 2>&1
[ -f "$P2/AGENTS.md" ] && grep -q "AGENTS-START" "$P2/AGENTS.md" && ok "切离 agent-b: 通用版保留" || bad "切离 agent-b: 通用版丢失"
! grep -q "AGENT-B-START" "$P2/AGENTS.md" && ok "切离 agent-b: 角色段已删" || bad "切离 agent-b: 角色段残留"
# owner → agent-b: 追加角色段不重复
devflow role switch agent-b >/dev/null 2>&1
[ "$(grep -c 'AGENT-B-START' "$P2/AGENTS.md")" -eq 1 ] && ok "切回 agent-b: 角色段追加且唯一" || bad "切回 agent-b: 角色段重复或缺失"

# ── 6. gate 命令可执行（A 场景，Go 栈 mock）──
echo "=== 6. gate 命令可执行 ==="
G="$TEST_DIR/goproj"; mkdir -p "$G/backend/pkg"; git -C "$G" init -q
cat > "$G/backend/go.mod" << 'EOF'
module test/backend

go 1.21
EOF
cat > "$G/backend/pkg/x.go" << 'EOF'
package pkg

func IsOK() bool { return true }
EOF
cat > "$G/backend/pkg/x_test.go" << 'EOF'
package pkg

import "testing"

func TestIsOK(t *testing.T) {
	if !IsOK() {
		t.Fatal("IsOK() = false")
	}
}
EOF
# mock 仓库先做初始 commit（BYPASS_WT_CHECK: 宿主全局 pre-commit 拦截；install.sh 之后还会部署仓库级 hook）
git -C "$G" add -A && BYPASS_WT_CHECK=1 git -C "$G" -c user.email=test@test -c user.name=test commit -qm "init"
# 部署 scripts（模拟 --update 已装）
bash "$SRC/install.sh" "$G" --role owner >/dev/null 2>&1
export PATH="$HOME/.local/go/bin:$PATH"  # Go 在 ~/.local/go/bin
cd "$G"
MBR=$(git -C "$G" symbolic-ref --short HEAD)  # master 或 main

bash .devflow/scripts/test-gate.sh >/dev/null 2>&1 && ok "test-gate.sh 跑通（exit 0）" || bad "test-gate.sh 失败 rc=$?"
bash .devflow/scripts/green-gate.sh >/dev/null 2>&1 && ok "green-gate.sh 跑通" || bad "green-gate.sh 失败 rc=$?"
bash .devflow/scripts/check-layer.sh "$MBR..HEAD" >/dev/null 2>&1 && ok "check-layer.sh 跑通" || bad "check-layer.sh 失败 rc=$?"
bash .devflow/scripts/trace.sh test-event k=v >/dev/null 2>&1 && [ -f .devflow/trace.jsonl ] && ok "trace.sh 写事件" || bad "trace.sh 失败"
.devflow/scripts/devflow role list >/dev/null 2>&1 && ok "devflow role list 跑通" || bad "devflow role list 失败"

# stage-verify 冒号全名 vs 裸名
bash .devflow/scripts/stage-verify.sh implement >/dev/null 2>&1 && ok "stage-verify 裸名不报错（静默 SKIP 语义）" || bad "stage-verify 裸名异常"
OUT=$(bash .devflow/scripts/stage-verify.sh spec:done 2>&1 | head -1) || true
[ -n "$OUT" ] && ok "stage-verify spec:done 有输出（验证器工作）" || bad "stage-verify spec:done 无输出"

# check_constitution 依赖（python-frontmatter）
PY=""
if python3 -c "import frontmatter" 2>/dev/null; then PY="python3"
elif [ -x "$HOME/.local/bin/python3.11" ] && "$HOME/.local/bin/python3.11" -c "import frontmatter" 2>/dev/null; then PY="$HOME/.local/bin/python3.11"
fi
if [ -n "$PY" ]; then
    $PY .devflow/scripts/check_constitution.py "$G/issues/TEMPLATE.md" >/dev/null 2>&1 && ok "check_constitution 跑通" || bad "check_constitution 失败"
else
    echo "  ⚠️  python-frontmatter 未装，跳过 check_constitution（需 pip install python-frontmatter）"
fi

# g0-inject 真实闭环（自闭环：注入→测试 RED→恢复→全绿，断言其输出）
cd "$G"
if command -v go >/dev/null 2>&1; then
    go -C backend test ./... >/dev/null 2>&1 && ok "g0 前置: 测试全绿" || bad "g0 前置: go test 失败"
    G0_OUT=$(bash .devflow/scripts/g0-inject.sh backend/pkg/x.go TestIsOK 2>&1)
    echo "$G0_OUT" | grep -q "故障注入后确实有测试失败" && ok "g0: 注入后测试 RED" || bad "g0: 注入未致测试失败"
    echo "$G0_OUT" | grep -q "恢复后测试全部通过" && ok "g0: 恢复后全绿" || bad "g0: 恢复未验证通过"
else
    echo "  ⚠️  go 不在 PATH，跳过 g0-inject 闭环"
fi

echo ""
echo "结果: $PASS 通过 / $FAIL 失败"
[ "$FAIL" -eq 0 ]
