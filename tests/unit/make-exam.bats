#!/usr/bin/env bats
# make_exam.py 三道关单测（toy 仓，python3 直跑无需 pytest）

setup() {
  TEST_TMP="$(mktemp -d)"
  REPO="$TEST_TMP/repo"
  mkdir -p "$REPO"
  git -C "$REPO" init -q
  git -C "$REPO" config user.email t@t && git -C "$REPO" config user.name t
  git -C "$REPO" config core.hooksPath .git/hooks   # 脱全局钩子，否则 fixture commit 被 v3.6 全局串联拦截
  printf 'VALUE = 0\n' > "$REPO/app.py"
  printf '# t9 修复计数错误\n把 VALUE 修正为 1\n' > "$REPO/ticket.md"
  git -C "$REPO" add -A && git -C "$REPO" commit -qm base
  echo "$(git -C "$REPO" rev-parse HEAD)" > "$TEST_TMP/base.sha"
  printf 'VALUE = 1\n' > "$REPO/app.py"
  mkdir "$REPO/tests"; printf 'from app import VALUE\nassert VALUE == 1\n' > "$REPO/tests/test_a.py"
  git -C "$REPO" add -A && git -C "$REPO" commit -qm fix
  echo "$(git -C "$REPO" rev-parse HEAD)" > "$TEST_TMP/fix.sha"
  EXAM="python3 $BATS_TEST_DIRNAME/../../scripts/make_exam.py"
}

teardown() { rm -rf "$TEST_TMP"; }

@test "关2 fail-to-pass 通过则封卷成功（clean 题面 → sealed）" {
  base=$(cat "$TEST_TMP/base.sha"); fix=$(cat "$TEST_TMP/fix.sha")
  run $EXAM --repo "$REPO" --ticket "$REPO/ticket.md" \
      --fix-commits "$fix..$fix" --test-cmd "PYTHONPATH=. python3 tests/test_a.py" \
      --out "$TEST_TMP/exams"
  [ "$status" -eq 0 ]
  grep -q "status: sealed" "$TEST_TMP/exams/"*/exam.yaml
  [ -f "$TEST_TMP/exams/"*/hidden/tests/test_a.py ]
}

@test "关1 历史剥离：快照仓只有一个提交且无 remote" {
  base=$(cat "$TEST_TMP/base.sha"); fix=$(cat "$TEST_TMP/fix.sha")
  $EXAM --repo "$REPO" --ticket "$REPO/ticket.md" \
      --fix-commits "$fix..$fix" --test-cmd "PYTHONPATH=. python3 tests/test_a.py" \
      --out "$TEST_TMP/exams"
  [ "$(git -C "$TEST_TMP/exams/"*/checkout rev-list --count HEAD)" = "1" ]
  run git -C "$TEST_TMP/exams/"*/checkout remote
  [ -z "$output" ]
  run git -C "$TEST_TMP/exams/"*/checkout log --oneline --all
  [[ ! "$output" == *fix* ]]
}

@test "关3 泄题题面命中正则 → needs-review 不封口" {
  base=$(cat "$TEST_TMP/base.sha"); fix=$(cat "$TEST_TMP/fix.sha")
  printf '# t9\n修复方案是把 VALUE 改成 `1`，patch 如下\n' > "$REPO/ticket2.md"
  run $EXAM --repo "$REPO" --ticket "$REPO/ticket2.md" \
      --fix-commits "$fix..$fix" --test-cmd "PYTHONPATH=. python3 tests/test_a.py" \
      --out "$TEST_TMP/exams2"
  [ "$status" -eq 0 ]
  grep -q "status: needs-review" "$TEST_TMP/exams2/"*/exam.yaml
}

@test "假题被拒：隐藏卷基线即通过 → 非零退出且不出卷" {
  base=$(cat "$TEST_TMP/base.sha")
  printf 'from app import VALUE\nassert VALUE in (0, 1)\n' > "$REPO/tests/test_a.py"
  git -C "$REPO" add -A && git -C "$REPO" commit -qm weakfix
  fix=$(git -C "$REPO" rev-parse HEAD)
  run $EXAM --repo "$REPO" --ticket "$REPO/ticket.md" \
      --fix-commits "$fix..$fix" --test-cmd "PYTHONPATH=. python3 tests/test_a.py" \
      --out "$TEST_TMP/exams3"
  [ "$status" -ne 0 ]
  [[ "$output" == *"关2失败"* ]]
  [ ! -f "$TEST_TMP/exams3/"*/exam.yaml ] || false
}

@test "声明过滤：票 test_files 未列的测试文件被剔出隐藏卷" {
  R2=$TEST_TMP/r2; mkdir -p "$R2/tests"
  git -C "$R2" init -q; git -C "$R2" config user.email t@t; git -C "$R2" config user.name t
  git -C "$R2" config core.hooksPath .git/hooks
  printf 'VALUE = 0\n' > "$R2/app.py"
  printf -- '---\ntest_files: ["tests/test_a.py"]\n---\n# t9\n把 VALUE 修正为 1\n' > "$R2/ticket.md"
  git -C "$R2" add -A && git -C "$R2" commit -qm base
  printf 'VALUE = 1\n' > "$R2/app.py"
  printf 'from app import VALUE\nassert VALUE == 1\n' > "$R2/tests/test_a.py"
  printf 'from app import VALUE\nassert VALUE in (0, 1)\n' > "$R2/tests/test_other.py"
  git -C "$R2" add -A && git -C "$R2" commit -qm fix
  F=$(git -C "$R2" rev-parse HEAD)
  run $EXAM --repo "$R2" --ticket "$R2/ticket.md" --fix-commits "$F..$F" \
      --test-cmd "PYTHONPATH=. python3 tests/test_a.py" --out "$TEST_TMP/e-d"
  [ "$status" -eq 0 ]
  [[ "$output" == *"声明过滤剔除"*test_other.py* ]]
  [ ! -f "$TEST_TMP/e-d/"*/hidden/tests/test_other.py ]
  [ -f "$TEST_TMP/e-d/"*/hidden/tests/test_a.py ]
}

@test "--ticket-at：题面取历史无附注版，当前票版仅供声明过滤" {
  R2=$TEST_TMP/r3; mkdir -p "$R2/tests"
  git -C "$R2" init -q; git -C "$R2" config user.email t@t; git -C "$R2" config user.name t
  git -C "$R2" config core.hooksPath .git/hooks
  printf 'VALUE = 0\n' > "$R2/app.py"
  printf 'test_files: ["tests/test_a.py"]\n# t9\n把 VALUE 修正为 1\n' > "$R2/ticket.md"
  git -C "$R2" add -A && git -C "$R2" commit -qm base
  printf 'VALUE = 1\n' > "$R2/app.py"
  printf 'from app import VALUE\nassert VALUE == 1\n' > "$R2/tests/test_a.py"
  git -C "$R2" add -A && git -C "$R2" commit -qm fix
  FIX=$(git -C "$R2" rev-parse HEAD)
  printf 'test_files: ["tests/test_a.py"]\n# t9\n把 VALUE 修正为 1\n\n## 实现期附注\n修法是改成 `VALUE = 1` 字面量\n' > "$R2/ticket.md"
  git -C "$R2" add -A && git -C "$R2" commit -qm leaky-note
  run $EXAM --repo "$R2" --ticket "$R2/ticket.md" --fix-commits "$FIX..$FIX" \
      --ticket-at "$FIX" --test-cmd "PYTHONPATH=. python3 tests/test_a.py" --out "$TEST_TMP/e-t2"
  [ "$status" -eq 0 ]
  grep -q "实现期附注" "$TEST_TMP/e-t2/"*/prompt.md && return 1   # 题面必须是 fix 时点的无附注版
  grep -q "ticket-at: $FIX" "$TEST_TMP/e-t2/"*/exam.yaml
  grep -q "status: sealed" "$TEST_TMP/e-t2/"*/exam.yaml   # 无附注版不命中 LEAK_RE
  # 对照：不传 --ticket-at 时当前票版含泄题词 → needs-review
  run $EXAM --repo "$R2" --ticket "$R2/ticket.md" --fix-commits "$FIX..$FIX" \
      --test-cmd "PYTHONPATH=. python3 tests/test_a.py" --exam-id alt --out "$TEST_TMP/e-t3"
  grep -q "status: needs-review" "$TEST_TMP/e-t3/alt/exam.yaml"
}

@test "--deselect 记入 test-cmd 与 exam.yaml 溯源行" {
  base=$(cat "$TEST_TMP/base.sha"); fix=$(cat "$TEST_TMP/fix.sha")
  run $EXAM --repo "$REPO" --ticket "$REPO/ticket.md" --fix-commits "$fix..$fix" \
      --deselect "tests/test_a.py::nope" --test-cmd "PYTHONPATH=. python3 tests/test_a.py" \
      --out "$TEST_TMP/e-x"
  [ "$status" -eq 0 ]   # toy 测试忽略额外 argv，F2P 不受影响
  grep -q -- "--deselect tests/test_a.py::nope" "$TEST_TMP/e-x/"*/exam.yaml
  grep -q "deselect: tests/test_a.py::nope" "$TEST_TMP/e-x/"*/exam.yaml
}
