#!/usr/bin/env python3
"""E1 自动审卷：静态/稳定性/变异/评审四段 → <exam>/review/verdicts.json 证据包。
方法依据 docs/references/exam-review-automation-survey.md（TB3 test_instruction_alignment 判据 +
CoHarden MPE 宽松率 + SWE-benchify N-run flake quarantine）。
人工闸改判：人只裁决 flagged 项并签字，derivation-review 字段仍由人改写，本脚本不碰 exam.yaml。
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import make_exam as ME
from run_driver import exam_meta, provider_env

OPS = ['symptom-suppression', 'incomplete-fix', 'input-specific-shortcut', 'behavior-substitution']
LAXITY_TAU = 0.20
LEAK_TOKEN_RUN = 8   # 题面与 fix diff 最长公共 token 连续段阈值（SWE-benchify 防火墙同族检查）

def head_repo(repo_path):
    if not Path(repo_path).is_dir():
        sys.exit(f'❌ 考卷来源仓不存在，无法复审: {repo_path}')
    return Path(repo_path)

def fix_diff(repo, base, last, impl_files):
    return ME.git(repo, 'diff', base, last, '--', *impl_files).stdout

def longest_common_run(a, b):
    from difflib import SequenceMatcher
    m = SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    return m.size

def toks(s):
    return re.findall(r'\S+', s)

def head_cc(claude_bin, model, prompt, workdir):
    """无头单问（隔离 CC 环境，同 run_driver 姿势）；返回 stdout"""
    env = dict(os.environ); env.update(provider_env(model))
    cc_home = Path(tempfile.mkdtemp(prefix='review-cc-'))
    env['CLAUDE_CONFIG_DIR'] = str(cc_home)
    r = subprocess.run([claude_bin, '-p', prompt, '--output-format', 'json',
                        '--dangerously-skip-permissions', '--max-turns', '5'],
                       cwd=workdir, env=env, capture_output=True, text=True, timeout=900)
    shutil.rmtree(cc_home, ignore_errors=True)
    try:
        return json.loads(r.stdout).get('result', '')
    except json.JSONDecodeError:
        return r.stdout

def extract_json(text):
    i, j = text.find('{'), text.rfind('}')
    if i < 0 or j <= i:
        raise ValueError('judge 输出无 JSON')
    return json.loads(text[i:j+1])

# ── S1 静态泄题（零 API）──
def s1_static(exam_dir, repo, meta):
    prompt = Path(exam_dir, 'prompt.md').read_text()
    base, last = meta['baseline-commit'], meta['fix-commits'].split('..')[1]
    changed = ME.need_git(repo, 'diff', '--name-only', base, last).splitlines()
    impl = [f for f in changed if not ME.is_test_file(f)]
    d = fix_diff(repo, base, last, impl) if impl else ''
    # diff 行首 +/- 剥离：否则 '+VALUE' 与题面 'VALUE' 对不上，泄漏段被格式切碎
    d_norm = '\n'.join(l[1:] if l[:1] in '+-' and not l.startswith(('+++', '---')) else l
                       for l in d.splitlines())
    runs = [longest_common_run(toks(prompt), toks(d_norm))]
    # 题面 vs 修复 commit messages 逐条
    log = ME.need_git(repo, 'log', f'{base}..{last}', '--format=%s%n%b')
    runs.append(longest_common_run(toks(prompt), toks(log)))
    return {'max_common_token_run': max(runs), 'threshold': LEAK_TOKEN_RUN,
            'flag': max(runs) >= LEAK_TOKEN_RUN}

# ── S2 隐藏卷稳定性：F2P 两端各重跑 N 次（make_exam 只跑 1 次）──
def s2_flake(exam_dir, repo, meta, n=3):
    base, last = meta['baseline-commit'], meta['fix-commits'].split('..')[1]
    changed = ME.need_git(repo, 'diff', '--name-only', base, last).splitlines()
    impl = [f for f in changed if not ME.is_test_file(f)]
    rc_f, rc_p = [], []
    for _ in range(n):
        t = Path(tempfile.mkdtemp(prefix='flake-'))
        try:
            a = t / 'a'; shutil.copytree(Path(exam_dir) / 'checkout', a)
            rc_f.append(ME.proof(a, Path(exam_dir) / 'hidden', meta['test-cmd']))
            b = t / 'b'; shutil.copytree(Path(exam_dir) / 'checkout', b)
            (b / '_impl.patch').write_text(fix_diff(repo, base, last, impl))
            subprocess.run(f'cd {b} && git apply -p1 _impl.patch && rm _impl.patch',
                           shell=True, capture_output=True)
            rc_p.append(ME.proof(b, Path(exam_dir) / 'hidden', meta['test-cmd']))
        finally:
            shutil.rmtree(t, ignore_errors=True)
    stable_f = all(x != 0 for x in rc_f); stable_p = all(x == 0 for x in rc_p)
    return {'baseline_rcs': rc_f, 'fixed_rcs': rc_p,
            'stable': stable_f and stable_p,
            'flag': not (stable_f and stable_p)}

# ── S3 变异宽松率：LLM 对原修复造 4 算子 plausible-but-wrong 变体 ──
MUTANT_PROTOCOL = 'MUTANT_PROTOCOL'
def s3_mutants(exam_dir, repo, meta, claude_bin, model, workdir):
    base, last = meta['baseline-commit'], meta['fix-commits'].split('..')[1]
    changed = ME.need_git(repo, 'diff', '--name-only', base, last).splitlines()
    impl = [f for f in changed if not ME.is_test_file(f)]
    patch = fix_diff(repo, base, last, impl)
    hidden_txt = {str(p.relative_to(Path(exam_dir) / 'hidden')): p.read_text()
                  for p in Path(exam_dir, 'hidden').rglob('*') if p.is_file()}
    prompt = (f'{MUTANT_PROTOCOL}\n你是基准质检员。下面是一个真实修复 patch 与它的隐藏验收测试。'
              f'为每个算子各造 1 个"看似合理但未真正修复问题"的变体 patch——目标是能骗过隐藏测试。\n'
              f'算子: {", ".join(OPS)}\n只输出 JSON：{{"mutants":[{{"op":"...","rationale":"...","patch":"<git diff 文本>"}}]}}\n'
              f'## 修复 patch\n{patch}\n## 隐藏测试\n'
              + '\n'.join(f'### {k}\n{v}' for k, v in hidden_txt.items()))
    raw = head_cc(claude_bin, model, prompt, workdir)
    try:
        mutants = extract_json(raw).get('mutants', [])
    except (ValueError, json.JSONDecodeError):
        return {'error': 'mutant 输出不可解析', 'admitted': 0, 'survivors': [], 'laxity': None}
    survivors = []
    for m in mutants:
        if not m.get('patch'):
            continue
        t = Path(tempfile.mkdtemp(prefix='mut-'))
        try:
            snap = t / 's'; shutil.copytree(Path(exam_dir) / 'checkout', snap)
            (snap / 'i.patch').write_text(patch); (snap / 'm.patch').write_text(m['patch'])
            ap = subprocess.run(f'cd {snap} && git apply -p1 i.patch && git apply -p1 m.patch',
                                shell=True, capture_output=True, text=True)
            if ap.returncode != 0:
                continue  # 不可应用=不计入 admitted（CoHarden admissibility）
            rc = ME.proof(snap, Path(exam_dir) / 'hidden', meta['test-cmd'])
            if rc == 0:
                survivors.append({'op': m.get('op'), 'rationale': m.get('rationale'),
                                  'patch-sha256': hashlib.sha256(m['patch'].encode()).hexdigest()})
        finally:
            shutil.rmtree(t, ignore_errors=True)
    admitted = len([m for m in mutants if m.get('patch')])
    return {'admitted': admitted, 'survivors': survivors,
            'laxity': (len(survivors) / admitted) if admitted else None}

# ── S4 评审 judge：TB3 双向对齐 + Senior 三层 + 泄题 + 存活变体是否违反题面 ──
JUDGE_PROTOCOL = 'JUDGE_PROTOCOL'
def s4_judge(exam_dir, meta, s3, claude_bin, model, workdir):
    prompt_md = Path(exam_dir, 'prompt.md').read_text()
    hidden_txt = '\n'.join(
        f'### {p.relative_to(Path(exam_dir) / "hidden")}\n{p.read_text()}'
        for p in sorted(Path(exam_dir, 'hidden').rglob('*')) if p.is_file())
    surv = json.dumps(s3.get('survivors', []), ensure_ascii=False)
    judge_in = (f'{JUDGE_PROTOCOL}\n你是考卷质检评审。只输出 JSON，逐判据 verdict=PASS/FAIL + evidence。\n'
                f'判据:\n'
                f'1 leak: 只读题面能否复述出具体实现/修法（FAIL=泄题）\n'
                f'2 alignment: 双向可追溯——每条测试断言可追溯到题面要求；每条题面要求有测试覆盖；'
                f'测试不得引入题面外的新需求\n'
                f'3 overconstraint: 测试只许覆盖①题面明示行为契约②仓库承重惯例③无可辩驳最佳实践，'
                f'超出即 gotcha（FAIL）\n'
                f'4 survivors: 对每个未违反题面的存活变体判 violates_prompt true/false\n'
                f'格式 {{"leak":{{"verdict":"","evidence":""}},"alignment":{{...}},'
                f'"overconstraint":{{...}},"survivors":[{{"op":"","violates_prompt":bool,"evidence":""}}]}}\n'
                f'## 题面\n{prompt_md}\n## 隐藏卷\n{hidden_txt}\n## 存活变体(骗过了隐藏卷的错误修复)\n{surv}')
    raw = head_cc(claude_bin, model, judge_in, workdir)
    return extract_json(raw)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exam', required=True)
    ap.add_argument('--claude-bin', default='claude')
    ap.add_argument('--judge-model', default='qwen3.8-max[1m]')
    ap.add_argument('--mutant-model', default='qwen3.8-max[1m]')
    ap.add_argument('--repo', default=None, help='默认取 exam.yaml 的 repo 字段')
    ap.add_argument('--skip-mutants', action='store_true', help='离线快审（S1+S2+judge 不带变异证据）')
    a = ap.parse_args()
    exam_dir = Path(a.exam).resolve()
    meta = exam_meta(exam_dir)
    repo = head_repo(a.repo or meta['repo'])

    # judge/mutant agent 工作目录=中立空临时目录——--dangerously-skip-permissions 下不给它任何源仓写面
    workdir = tempfile.mkdtemp(prefix='review-work-')
    try:
        r1 = s1_static(exam_dir, repo, meta)
        r2 = s2_flake(exam_dir, repo, meta)
        r3 = {'skipped': True} if a.skip_mutants else s3_mutants(exam_dir, repo, meta,
                                                                 a.claude_bin, a.mutant_model, workdir)
        r4 = s4_judge(exam_dir, meta, r3, a.claude_bin, a.judge_model, workdir)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    lax_flag = (r3.get('laxity') is not None and r3['laxity'] >= LAXITY_TAU)
    survivors_ok = any(not s.get('violates_prompt', True) for s in r4.get('survivors', []))
    fails = [k for k in ('leak', 'alignment', 'overconstraint')
             if r4.get(k, {}).get('verdict', 'FAIL').upper() == 'FAIL']
    flags = ([f'S1 泄题连续段 {r1["max_common_token_run"]} token' if r1['flag'] else None],
             [f'S2 隐藏卷不稳 {r2["baseline_rcs"]}/{r2["fixed_rcs"]}' if r2['flag'] else None],
             [f'S3 宽松率 {r3.get("laxity"):.2f}≥{LAXITY_TAU}' if lax_flag and survivors_ok else None],
             [f'S4 判据 FAIL: {f}' for f in fails])
    flags = [x for t in flags for x in t if x]
    verdict = {
        'exam-id': meta.get('exam-id'), 'ts': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'auto-verdict': 'flagged' if flags else 'auto-pass',
        'flags': flags,
        's1-static': r1, 's2-flake': r2, 's3-mutants': r3, 's4-judge': r4,
        'models': {'judge': a.judge_model, 'mutant': a.mutant_model},
        'prompt-sha256': meta.get('prompt-sha256'),
        'note': '本包只生成证据；derivation-review 由人裁决后手改 exam.yaml'}
    out = exam_dir / 'review'
    out.mkdir(exist_ok=True)
    (out / 'verdicts.json').write_text(json.dumps(verdict, ensure_ascii=False, indent=2))
    (out / 'judge-trace.log').write_text('')  # 预留：真实 head_cc 轨迹回捞时补
    print(f"{'🚩 flagged' if flags else '✅ auto-pass'}: {out/'verdicts.json'}")
    for f in flags:
        print('  -', f)

if __name__ == '__main__':
    main()
