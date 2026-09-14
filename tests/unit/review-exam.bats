#!/usr/bin/env bats
# review_exam.py 四段自动审（claude 用 python stub 注入，全本地零 API）

setup() {
  T=$(mktemp -d); W="$BATS_TEST_DIRNAME/../.."
  R=$T/repo; mkdir -p "$R"
  git -C "$R" init -q; git -C "$R" config user.email t@t; git -C "$R" config user.name t
  git -C "$R" config core.hooksPath .git/hooks
  printf 'VALUE = 0\n' > "$R/app.py"
  printf '# t9\n把 VALUE 修正为 1\n' > "$R/ticket.md"
  git -C "$R" add -A && git -C "$R" commit -qm base
  printf 'VALUE = 1\n' > "$R/app.py"; mkdir "$R/tests"
  printf 'from app import VALUE\nassert VALUE == 1\n' > "$R/tests/test_a.py"
  git -C "$R" add -A && git -C "$R" commit -qm fix
  F=$(git -C "$R" rev-parse HEAD)
  python3 "$W/scripts/make_exam.py" --repo "$R" --ticket "$R/ticket.md" \
      --fix-commits "$F..$F" --test-cmd "PYTHONPATH=. python3 tests/test_a.py" \
      --out "$T/exams" >/dev/null
  # stub claude：按协议标记分发预置答案（RESP 文件由各用例写）
  cat > "$T/claude-stub" <<'STUB'
#!/usr/bin/env python3
import sys, os, json
p = sys.argv[sys.argv.index('-p') + 1]
R = json.load(open(os.environ['RESP']))
key = 'mutant' if 'MUTANT_PROTOCOL' in p else ('judge' if 'JUDGE_PROTOCOL' in p else 'other')
print(json.dumps({'result': json.dumps(R[key]), 'usage': {}}))
STUB
  chmod +x "$T/claude-stub"
  export T W R
}
teardown() { rm -rf "$T" /tmp/review-flake-state; }

clean_resp() {  # judge 全 PASS、mutant 造 4 个但 patch 全部不可应用（admitted=0）
  cat > "$T/resp.json" <<EOF
{"mutant": {"mutants": [{"op":"symptom-suppression","rationale":"r","patch":"GARBAGE-NOT-A-DIFF"},{"op":"incomplete-fix","rationale":"r","patch":"GARBAGE"},{"op":"input-specific-shortcut","rationale":"r","patch":"GARBAGE"},{"op":"behavior-substitution","rationale":"r","patch":"GARBAGE"}]},
 "judge": {"leak":{"verdict":"PASS","evidence":""},"alignment":{"verdict":"PASS","evidence":""},"overconstraint":{"verdict":"PASS","evidence":""},"survivors":[]}}
EOF
  export RESP=$T/resp.json
}

@test "S1 静态：题面复制 fix diff 长 token 段 → flagged" {
  # 给票面追加与实现 diff 逐字相同的 ≥8 token 段（make_exam 的 LEAK_RE 不拦这种，正补盲区）
  printf 'CONFIG 调整如下 VALUE = 1 XXX_AAA BBB_CCC DDD_EEE FFF_GGG HHH\n' >> "$T/exams/"*/prompt.md
  sed -i 's/^VALUE = 1$/VALUE = 1 XXX_AAA BBB_CCC DDD_EEE FFF_GGG HHH/' "$R/app.py"
  git -C "$R" commit -qam fix2 && F2=$(git -C "$R" rev-parse HEAD)
  sed -i "s/fix-commits: .*/fix-commits: $F2..$F2/" "$T/exams/"*/exam.yaml
  clean_resp
  run python3 "$W/scripts/e1/review_exam.py" --exam $(ls -d "$T"/exams/*) \
      --claude-bin "$T/claude-stub" --skip-mutants
  [ "$status" -eq 0 ]
  grep -q '"auto-verdict": "flagged"' "$T"/exams/*/review/verdicts.json
  grep -q 'S1' "$T"/exams/*/review/verdicts.json
}

@test "S2 稳定性：隐藏卷时过时挂 → flagged（N-run flake quarantine）" {
  cat > "$T/exams/"*"/hidden/tests/test_a.py" <<'PY'
import os
n = 0
if os.path.exists('/tmp/review-flake-state'):
    n = len(open('/tmp/review-flake-state').read())
open('/tmp/review-flake-state', 'a').write('x')
from app import VALUE
assert VALUE == 1 and n % 2 == 0
PY
  clean_resp
  run python3 "$W/scripts/e1/review_exam.py" --exam $(ls -d "$T"/exams/*) \
      --claude-bin "$T/claude-stub" --skip-mutants
  grep -q '"auto-verdict": "flagged"' "$T"/exams/*/review/verdicts.json
  grep -q 'S2' "$T"/exams/*/review/verdicts.json
}

@test "S3+S4 宽松率：存活变体且不违反题面 → flagged Lax" {
  # 弱隐藏卷：!=0 即可（F2P 仍成立，但 -1 变体存活）
  printf 'from app import VALUE\nassert VALUE != 0\n' > "$T/exams/"*/hidden/tests/test_a.py
  cat > "$T/resp.json" <<'EOF'
{"mutant": {"mutants": [
   {"op":"behavior-substitution","rationale":"取负也非零","patch":"diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-VALUE = 1\n+VALUE = -1\n"},
   {"op":"symptom-suppression","rationale":"garbage","patch":"GARBAGE"},
   {"op":"incomplete-fix","rationale":"garbage","patch":"GARBAGE"},
   {"op":"input-specific-shortcut","rationale":"garbage","patch":"GARBAGE"}]},
 "judge": {"leak":{"verdict":"PASS","evidence":""},"alignment":{"verdict":"FAIL","evidence":"题面要求=1，测试只要求非零"},"overconstraint":{"verdict":"PASS","evidence":""},"survivors":[{"op":"behavior-substitution","violates_prompt":false,"evidence":"-1 也满足 !=0 但题面明说修正为 1"}]}}
EOF
  export RESP=$T/resp.json
  run python3 "$W/scripts/e1/review_exam.py" --exam $(ls -d "$T"/exams/*) \
      --claude-bin "$T/claude-stub"
  [ "$status" -eq 0 ]
  grep -q '"auto-verdict": "flagged"' "$T"/exams/*/review/verdicts.json
  grep -q '"laxity": 0.25' "$T"/exams/*/review/verdicts.json
  grep -q 'S3 宽松率' "$T"/exams/*/review/verdicts.json
  grep -q 'S4 共识废: alignment' "$T"/exams/*/review/verdicts.json
}

@test "干净卷四段全绿 → auto-pass，且 exam.yaml 未被触碰" {
  clean_resp
  before=$(sha256sum "$T"/exams/*/exam.yaml)
  run python3 "$W/scripts/e1/review_exam.py" --exam $(ls -d "$T"/exams/*) \
      --claude-bin "$T/claude-stub"
  [ "$status" -eq 0 ]
  grep -q '"auto-verdict": "auto-pass-need-human-sign"' "$T"/exams/*/review/verdicts.json
  [ "$before" = "$(sha256sum "$T"/exams/*/exam.yaml)" ]
}

@test "补题卷：二审 supplement FAIL 升级为 flagged" {
  exam=$(ls -d "$T"/exams/*)
  printf 'supplement: tests/test_sup.py\n' >> "$exam/exam.yaml"
  printf 'from app import VALUE\nassert VALUE == 1\n' > "$exam/hidden/tests/test_sup.py"
  python3 - "$T/resp2.json" <<'PYJSON'
import json, sys
json.dump({"mutant": {"mutants": []}, "judge": {
  "leak":{"verdict":"PASS","evidence":""},"alignment":{"verdict":"PASS","evidence":""},
  "overconstraint":{"verdict":"PASS","evidence":""},
  "supplement":{"verdict":"FAIL","evidence":"断言测了票面未载的内部字段"},"survivors":[]}},
  open(sys.argv[1],"w"))
PYJSON
  export RESP=$T/resp2.json
  run python3 "$W/scripts/e1/review_exam.py" --exam "$exam" \
      --claude-bin "$T/claude-stub" --skip-mutants
  grep -q '"auto-verdict": "flagged"' "$exam/review/verdicts.json"
  grep -q 'S4 共识废: supplement' "$exam/review/verdicts.json"
}

@test "deselect 盲区：被剔函数不进 judge 视图（probe 现场核验）" {
  exam=$(ls -d "$T"/exams/*)
  cat > "$exam/hidden/tests/test_a.py" <<'PY'
from app import VALUE
def test_visible():
    assert VALUE == 1
def _internal_dropped():
    MARKER_INTERNAL_XYZ = 1
PY
  printf 'deselect: tests/test_a.py::_internal_dropped\n' >> "$exam/exam.yaml"
  cat > "$T/judge-probe" <<'STUB'
#!/usr/bin/env python3
import sys, json
p = sys.argv[sys.argv.index('-p') + 1]
if 'JUDGE_PROTOCOL' in p:
    leaked = 'MARKER_INTERNAL_XYZ' in p
    out = {"leak":{"verdict":"PASS"},
           "alignment":{"verdict":"FAIL" if leaked else "PASS",
             "evidence":"prompt leaked deselected func" if leaked else "clean"},
           "overconstraint":{"verdict":"PASS"},"survivors":[]}
    print(json.dumps({"result": json.dumps(out), "usage": {}}))
else:
    print(json.dumps({"result": json.dumps({"mutants": []}), "usage": {}}))
STUB
  chmod +x "$T/judge-probe"
  printf '{"mutant":{"mutants":[]},"judge":{}}\n' > "$T/resp.json"; export RESP=$T/resp.json
  run python3 "$W/scripts/e1/review_exam.py" --exam "$exam" \
      --claude-bin "$T/judge-probe" --skip-mutants --no-second
  ! grep -q 'S4 共识废: alignment' "$exam/review/verdicts.json"
}

@test "三态仲裁·分歧：主审 PASS 二审 FAIL → 升人（非共识废非共识绿）" {
  exam=$(ls -d "$T"/exams/*)
  cat > "$T/probe2" <<'STUB'
#!/usr/bin/env python3
import sys, os, json
p = sys.argv[sys.argv.index('-p') + 1]
model = sys.argv[sys.argv.index('--model')+1] if '--model' in sys.argv else ''
if 'JUDGE_PROTOCOL' in p:
    # 主审(非 deepseek)判 PASS；二审(deepseek)判 leak FAIL → 分歧
    v = "FAIL" if 'deepseek' in model else "PASS"
    out = {"leak":{"verdict":v,"evidence":""},
           "alignment":{"verdict":"PASS"},"overconstraint":{"verdict":"PASS"},"survivors":[]}
    print(json.dumps({"result": json.dumps(out), "usage": {}}))
else:
    print(json.dumps({"result": json.dumps({"mutants": []}), "usage": {}}))
STUB
  chmod +x "$T/probe2"
  printf '{"mutant":{"mutants":[]},"judge":{}}\n' > "$T/resp.json"; export RESP=$T/resp.json
  run python3 "$W/scripts/e1/review_exam.py" --exam "$exam" \
      --claude-bin "$T/probe2" --skip-mutants
  python3 -c "import json,sys; v=json.load(open('$exam/review/verdicts.json')); a=v['arbitration']; sys.exit(0 if a['leak']=='disagreement' and 'auto-pass-need' not in v['auto-verdict'] else 1)"
  grep -q 'S4 分歧: leak' "$exam/review/verdicts.json"
}
