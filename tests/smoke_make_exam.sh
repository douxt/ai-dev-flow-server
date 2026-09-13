#!/usr/bin/env bash
# make_exam.py 冒烟（与 make-exam.bats 同场景；无 bats 环境用本脚本自检）
set -u
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
M="$(cd "$(dirname "$0")/.." && pwd)/scripts/make_exam.py"
R=$T/repo; mkdir -p "$R"
git -C "$R" init -q; git -C "$R" config user.email t@t; git -C "$R" config user.name t
git -C "$R" config core.hooksPath .git/hooks   # 脱全局钩子（同 make_exam 内注释）
printf 'VALUE = 0\n' > "$R/app.py"
printf '# t9 修复计数错误\n把 VALUE 修正为 1\n' > "$R/ticket.md"
git -C "$R" add -A; git -C "$R" commit -qm base; B=$(git -C "$R" rev-parse HEAD)
printf 'VALUE = 1\n' > "$R/app.py"
mkdir "$R/tests"; printf 'from app import VALUE\nassert VALUE == 1\n' > "$R/tests/test_a.py"
git -C "$R" add -A; git -C "$R" commit -qm fix; F=$(git -C "$R" rev-parse HEAD)
fail=0

echo "== 用例1 happy path"
python3 "$M" --repo "$R" --ticket "$R/ticket.md" --fix-commits "$F..$F" \
  --test-cmd "PYTHONPATH=. python3 tests/test_a.py" --out "$T/exams" || fail=1
grep -q "status: sealed" "$T"/exams/*/exam.yaml || { echo "✗ 未 sealed"; fail=1; }

echo "== 关1 历史剥离断言"
[ "$(git -C "$T"/exams/*/checkout rev-list --count HEAD)" = 1 ] || { echo "✗ 提交数≠1"; fail=1; }
[ -z "$(git -C "$T"/exams/*/checkout remote)" ] || { echo "✗ 有 remote"; fail=1; }
git -C "$T"/exams/*/checkout log --oneline --all | grep -q fix && { echo "✗ 未来历史泄漏"; fail=1; }

echo "== 关3 泄题题面"
printf '# t9\n修复方案是把 VALUE 改成 `1`，patch 如下\n' > "$R/t2.md"
python3 "$M" --repo "$R" --ticket "$R/t2.md" --fix-commits "$F..$F" \
  --test-cmd "PYTHONPATH=. python3 tests/test_a.py" --out "$T/exams2" >/dev/null || fail=1
grep -q "status: needs-review" "$T"/exams2/*/exam.yaml || { echo "✗ 未标 needs-review"; fail=1; }

echo "== 关2 假题拒绝（预期非零退出）"
printf 'from app import VALUE\nassert VALUE in (0, 1)\n' > "$R/tests/test_a.py"
git -C "$R" commit -qam weakfix; W=$(git -C "$R" rev-parse HEAD)
out=$(python3 "$M" --repo "$R" --ticket "$R/ticket.md" --fix-commits "$W..$W" \
  --test-cmd "PYTHONPATH=. python3 tests/test_a.py" --out "$T/exams3" 2>&1); rc=$?
[ $rc -ne 0 ] || { echo "✗ 弱题未被拒"; fail=1; }
echo "$out" | grep -q "关2失败" || { echo "✗ 拒绝原因缺失"; fail=1; }

[ $fail -eq 0 ] && echo "✅ smoke 全过" || echo "❌ smoke 有失败"
exit $fail
