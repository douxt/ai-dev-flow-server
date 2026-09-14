#!/usr/bin/env python3
"""E1 自动审卷：静态/稳定性/变异/评审四段 → <exam>/review/verdicts.json 证据包。
方法依据 docs/references/exam-review-automation-survey.md（TB3 test_instruction_alignment 判据 +
CoHarden MPE 宽松率 + SWE-benchify N-run flake quarantine）。
人工闸改判：人只裁决 flagged 项并签字，derivation-review 字段仍由人改写，本脚本不碰 exam.yaml。
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path


def log(msg):
    print(f'[review {time.strftime("%H:%M:%S")}] {msg}', file=sys.stderr, flush=True)

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
import make_exam as ME
from run_driver import exam_meta

OPS = ['symptom-suppression', 'incomplete-fix', 'input-specific-shortcut', 'behavior-substitution']
LAXITY_TAU = 0.20
LEAK_TOKEN_RUN = 8   # 题面与 fix diff 最长公共 token 连续段阈值（SWE-benchify 防火墙同族检查）

def provider_env_named(model, provider):
    """按 provider 名(ali/deepseek)解析认证 env——二审用不同模型家族破自审偏差"""
    prov = Path(os.path.expanduser('~/.claude/review-providers.json'))
    if not prov.exists():
        return {}
    p = json.loads(prov.read_text())['providers'][provider]
    tok = Path(os.path.expanduser(p['token_file'])).read_text().strip()
    return {'ANTHROPIC_BASE_URL': p['base_url'], 'ANTHROPIC_AUTH_TOKEN': tok,
            'ANTHROPIC_MODEL': model, 'ANTHROPIC_DEFAULT_SONNET_MODEL': model,
            'ANTHROPIC_DEFAULT_OPUS_MODEL': model, 'ANTHROPIC_DEFAULT_HAIKU_MODEL': model}

def deselected_by_file(meta):
    """deselect 溯源行 → {文件相对路径: [函数名]}；judge/mutant 只看执行视图"""
    by = {}
    for ent in (meta.get('deselect') or '').split():
        if '::' in ent:
            f, fn = ent.split('::', 1)
            by.setdefault(f, []).append(fn)
    return by

def strip_funcs(text, names):
    """按顶层 def <name>( 剥离函数(含其前导装饰器)——测试文件函数皆列 0 缩进"""
    if not names:
        return text
    lines = text.split('\n'); out = []; i = 0
    while i < len(lines):
        dm = re.match(r'def (\w+)\(', lines[i])
        if dm and dm.group(1) in names:
            while out and out[-1].strip().startswith('@'):   # 回吞装饰器
                out.pop()
            i += 1
            while i < len(lines) and not re.match(r'(def |class |@)', lines[i]):
                i += 1
            continue
        out.append(lines[i]); i += 1
    return '\n'.join(out)

def hidden_view(exam_dir, meta):
    """执行视图：隐藏卷正文，剥离已 deselect 函数（避免 judge 误报不执行测试的钉死）"""
    desel = deselected_by_file(meta)
    view = {}; hid = Path(exam_dir) / 'hidden'
    for p in sorted(hid.rglob('*')):
        if not p.is_file():
            continue
        rel = str(p.relative_to(hid))
        view[rel] = strip_funcs(p.read_text(), desel.get(rel, [])) if p.suffix == '.py' else p.read_text()
    return view

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

def head_cc(claude_bin, model, provider, prompt, workdir, max_turns=5, timeout=900):
    """无头单问（隔离 CC 环境，同 run_driver 姿势）；返回 stdout"""
    env = dict(os.environ); env.update(provider_env_named(model, provider))
    cc_home = Path(tempfile.mkdtemp(prefix='review-cc-'))
    env['CLAUDE_CONFIG_DIR'] = str(cc_home)
    r = subprocess.run([claude_bin, '-p', prompt, '--output-format', 'json',
                        '--dangerously-skip-permissions', '--max-turns', str(max_turns)],
                       cwd=workdir, env=env, capture_output=True, text=True, timeout=timeout)
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
def s3_mutants(exam_dir, repo, meta, claude_bin, model, provider, workdir):
    base, last = meta['baseline-commit'], meta['fix-commits'].split('..')[1]
    changed = ME.need_git(repo, 'diff', '--name-only', base, last).splitlines()
    impl = [f for f in changed if not ME.is_test_file(f)]
    patch = fix_diff(repo, base, last, impl)
    hidden_txt = hidden_view(exam_dir, meta)   # 执行视图：不向不执行的 deselect 测试造变异
    prompt = (f'{MUTANT_PROTOCOL}\n你是基准质检员。下面是一个真实修复 patch 与它的隐藏验收测试。'
              f'为每个算子各造 1 个"看似合理但未真正修复问题"的变体 patch——目标是能骗过隐藏测试。\n'
              f'纯文本转换任务：禁止读取文件或调用任何工具，直接根据下文输出。\n'
              f'算子: {", ".join(OPS)}\n只输出 JSON：{{"mutants":[{{"op":"...","rationale":"...","patch":"<git diff 文本>"}}]}}\n'
              f'## 修复 patch\n{patch}\n## 隐藏测试\n'
              + '\n'.join(f'### {k}\n{v}' for k, v in hidden_txt.items()))
    raw = head_cc(claude_bin, model, provider, prompt, workdir, max_turns=2, timeout=1200)
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
def s4_judge(exam_dir, meta, s3, claude_bin, model, provider, workdir,
             second=False):
    prompt_md = Path(exam_dir, 'prompt.md').read_text()
    view = hidden_view(exam_dir, meta)
    sup = set((meta.get('supplement') or '').split())
    hidden_txt = '\n'.join(
        f'### {k}{" 〔出卷方补题〕" if k in sup else ""}\n{v}'
        for k, v in view.items())
    surv = json.dumps(s3.get('survivors', []), ensure_ascii=False)
    judge_in = (f'{JUDGE_PROTOCOL}\n你是考卷质检评审。逐判据输出 verdict=PASS/FAIL + evidence，'
                f'最终回复只含一个 JSON 对象。\n'
                f'背景：这是"真实工单→agent 解题→隐藏测试判分"的考卷。被测 agent 能同时看到'
                f'题面与工作仓（基线快照在 ./repo-baseline/，含 docs/契约/代码——可读取取证）。'
                f'判"可推导"的口径 = 题面 + 基线仓内已有文档；题面引用了仓内契约且契约明载，则算可推导。\n'
                f'判据:\n'
                f'1 leak: 只读题面能否复述出具体实现/修法（FAIL=泄题）\n'
                f'2 alignment: 双向可追溯——每条测试断言可追溯到题面或基线仓内被题面引用的文档要求；'
                f'每条题面要求有测试覆盖；测试不得引入二者之外的新需求\n'
                f'3 overconstraint: 测试只许覆盖①上述可推导行为契约②仓库承重惯例③无可辩驳最佳实践，'
                f'超出即 gotcha（FAIL）\n'
                f'4 survivors: 对每个存活变体判 violates_prompt true/false（结合题面+仓内文档）\n'
                + (f'5 supplement: 标〔出卷方补题〕的文件是出卷方为救票面 [auto] AC 覆盖而自研的测试——'
                   f'专判其断言是否**只测外部行为、忠实票面 AC、未夹带入卷方臆造的需求**；越界即 FAIL\n'
                   f'6 overtrim: 本卷已 deselect/剔除的测试见溯源——判是否**误删了本可推导的覆盖**（过裁致 P2 变钝）\n'
                   if second else '')
                + f'格式 {{"leak":{{"verdict":"","evidence":""}},"alignment":{{...}},'
                f'"overconstraint":{{...}},"survivors":[{{"op":"","violates_prompt":bool,"evidence":""}}]'
                + (',\"supplement\":{\"verdict\":\"\",\"evidence\":\"\"},\"overtrim\":{\"verdict\":\"\",\"evidence\":\"\"}' if second else '')
                + '}\n'
                f'## 题面\n{prompt_md}\n## 隐藏卷（执行视图）\n{hidden_txt}\n'
                f'## 溯源（已剔除/deselect）\n{meta.get("drop-tests","无")} | {meta.get("deselect","无")}\n'
                f'## 存活变体(骗过了隐藏卷的错误修复)\n{surv}')
    raw = head_cc(claude_bin, model, provider, judge_in, workdir, max_turns=30, timeout=1800)
    return extract_json(raw)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exam', required=True)
    ap.add_argument('--claude-bin', default='claude')
    ap.add_argument('--judge-model', default='qwen3.8-max[1m]')
    ap.add_argument('--judge-provider', default='ali')
    ap.add_argument('--mutant-model', default='qwen3.8-max[1m]')
    ap.add_argument('--second-model', default='deepseek-flash',
                    help='第二意见模型（异族破自审偏差），定位=警报器非终裁；deepseek 原生端点仅认 deepseek-flash/deepseek-v4-pro')
    ap.add_argument('--second-provider', default='deepseek')
    ap.add_argument('--no-second', action='store_true', help='关闭第二意见')
    ap.add_argument('--repo', default=None, help='默认取 exam.yaml 的 repo 字段')
    ap.add_argument('--skip-mutants', action='store_true', help='离线快审（S1+S2+judge 不带变异证据）')
    a = ap.parse_args()
    exam_dir = Path(a.exam).resolve()
    meta = exam_meta(exam_dir)
    repo = head_repo(a.repo or meta['repo'])
    # 残差 = 有补题或有剔除/deselect → 触发异族第二意见专审这些决策
    has_residual = bool(meta.get('supplement') or meta.get('drop-tests') or meta.get('deselect'))

    # judge/mutant agent 工作目录=中立空临时目录——--dangerously-skip-permissions 下不给它任何源仓写面
    workdir = tempfile.mkdtemp(prefix='review-work-')
    try:
        log('S1 静态泄题…')
        r1 = s1_static(exam_dir, repo, meta)
        log(f"S1 done: max_run={r1['max_common_token_run']} flag={r1['flag']}")
        log('S2 flake N=3（真实测试套件逐遍重跑）…')
        r2 = s2_flake(exam_dir, repo, meta)
        log(f"S2 done: stable={r2['stable']}")
        if a.skip_mutants:
            r3 = {'skipped': True}
        else:
            log('S3 变异生成+执行…')
            try:
                r3 = s3_mutants(exam_dir, repo, meta, a.claude_bin, a.mutant_model,
                                a.judge_provider, workdir)
            except Exception as e:
                r3 = {'error': f'S3 异常: {e}', 'admitted': 0, 'survivors': [], 'laxity': None}
            log(f"S3 done: admitted={r3.get('admitted')} survivors={len(r3.get('survivors', []))} {r3.get('error') or ''}")
        log('S4 judge（带仓基线可见性）…')
        shutil.copytree(exam_dir / 'checkout', Path(workdir) / 'repo-baseline', dirs_exist_ok=True)
        try:
            r4 = s4_judge(exam_dir, meta, r3, a.claude_bin, a.judge_model,
                          a.judge_provider, workdir)
        except Exception as e:
            r4 = {'error': str(e), 'leak': {'verdict': 'FAIL', 'evidence': 'judge 未出结论，保守记 FAIL'},
                  'alignment': {'verdict': 'FAIL', 'evidence': 'judge 未出结论'},
                  'overconstraint': {'verdict': 'FAIL', 'evidence': 'judge 未出结论'}}
        log('S4 done')
        r4b = {'skipped': True}
        if has_residual and not a.no_second:
            log(f'S4b 第二意见（{a.second_provider}/{a.second_model}，专审残差）…')
            try:
                r4b = s4_judge(exam_dir, meta, r3, a.claude_bin, a.second_model,
                               a.second_provider, workdir, second=True)
            except Exception as e:
                r4b = {'error': str(e), 'supplement': {'verdict': 'FAIL', 'evidence': '二审未出结论'},
                       'overtrim': {'verdict': 'FAIL', 'evidence': '二审未出结论'}}
            log('S4b done')
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    lax_flag = (r3.get('laxity') is not None and r3['laxity'] >= LAXITY_TAU)
    survivors_ok = any(not s.get('violates_prompt', True) for s in r4.get('survivors', []))
    fails = [k for k in ('leak', 'alignment', 'overconstraint')
             if r4.get(k, {}).get('verdict', 'FAIL').upper() == 'FAIL']
    s4b_call_failed = bool(r4b.get('error'))
    fails_b = ([] if s4b_call_failed else
               [k for k in ('supplement', 'overtrim')
                if r4b.get(k, {}).get('verdict', '').upper() == 'FAIL'])
    flags = ([f'S1 泄题连续段 {r1["max_common_token_run"]} token' if r1['flag'] else None],
             [f'S2 隐藏卷不稳 {r2["baseline_rcs"]}/{r2["fixed_rcs"]}' if r2['flag'] else None],
             [f'S3 宽松率 {r3.get("laxity"):.2f}≥{LAXITY_TAU}' if lax_flag and survivors_ok else None],
             [f'S4 判据 FAIL: {f}' for f in fails],
             ([f'S4b 二审调用失败: {r4b.get("error")}（未获独立意见，保守升人闸）']
              if s4b_call_failed and not r4b.get('skipped') else []),
             [f'S4b 二审 FAIL: {f}（{a.second_model} 独立警报，升人闸）' for f in fails_b])
    flags = [x for t in flags for x in t if x]
    verdict = {
        'exam-id': meta.get('exam-id'), 'ts': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'auto-verdict': 'flagged' if flags else 'auto-pass',
        'flags': flags,
        's1-static': r1, 's2-flake': r2, 's3-mutants': r3, 's4-judge': r4,
        's4b-second-opinion': r4b,
        'models': {'judge': a.judge_model, 'mutant': a.mutant_model,
                   'second': a.second_model if has_residual and not a.no_second else 'n/a'},
        'judge-repo-visibility': 'repo-baseline(考卷 checkout 副本)',
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
