#!/usr/bin/env python3
"""E1 run-driver：三臂沙箱构建 + 无头 runner + 独立判分 + 台账 + Williams 排程。
协议：docs/plans/2026-09-13-e1-protocol-preregistration.md（三臂定义见 §3，隔离见 §5）

子命令：
  sandbox   构建单 run 沙箱（臂挂载，零 API）
  run       sandbox + claude -p 无头执行 + 判分 + 台账
  score     对已完成的沙箱独立判分（可见/隐藏卷）
  schedule  生成 Williams 轮转排程（跨票交错）
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLATFORM = HERE.parent.parent  # 平台仓根（取 config-templates 原版 hook）
# 臂差异仅此三项（协议 §3）：经文挂载 / stage RED 前置门 / g0 结果门
ARMS = {
    'A': dict(prompt='claude-md-A.md', stage_gate=True, g0=False),
    'B': dict(prompt='claude-md-facts.md', stage_gate=True, g0=False),
    'C': dict(prompt='claude-md-facts.md', stage_gate=False, g0=True),
}
# 沙箱上下文卫生：与本票解题无关的存档树（不属隐藏卷、不进判分、只灌 context）
SANDBOX_NOISE = ('research',)

def exam_meta(exam_dir):
    meta = {}
    for line in (Path(exam_dir) / 'exam.yaml').read_text().splitlines():
        if ':' in line and not line.startswith(' '):
            k, v = line.split(':', 1)
            meta[k.strip()] = v.strip()
    if meta.get('status') != 'sealed':
        sys.exit(f'❌ 考卷未封存（status={meta.get("status")}），拒用')
    return meta

def run_tests(cwd, test_cmd, timeout=900):
    try:
        r = subprocess.run(test_cmd, shell=True, cwd=cwd,
                           capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout[-4000:] + r.stderr[-4000:]
    except subprocess.TimeoutExpired:
        return 99, 'TIMEOUT'

def build_sandbox(exam_dir, arm, out, run_id):
    if arm not in ARMS:
        sys.exit(f'❌ 未知臂 {arm}')
    spec = ARMS[arm]
    exam_dir = Path(exam_dir).resolve()
    meta = exam_meta(exam_dir)
    out = Path(out)
    if out.exists():
        sys.exit(f'❌ {out} 已存在（run 沙箱不可覆盖）')
    repo = out / 'repo'
    shutil.copytree(exam_dir / 'checkout', repo)
    # 隔离硬化：清掉 checkout 继承的生产 agent 配置/钩子，避免冲平三臂差异
    for pth in ('.claude', '.devflow/scripts', '.devflow/templates'):
        tgt = repo / pth
        if tgt.is_dir():
            shutil.rmtree(tgt)
        elif tgt.exists():
            tgt.unlink()
    # 上下文卫生：剔除与本票解题无关的调研存档树（撑大 context/拖慢/含 429 抓取噪声），不动封卷哈希
    for noise in SANDBOX_NOISE:
        tgt = repo / noise
        if tgt.is_dir():
            shutil.rmtree(tgt)
        elif tgt.exists():
            tgt.unlink()
    # 臂挂载
    hooks_dir = repo / '.claude' / 'hooks'
    hooks_dir.mkdir(parents=True)
    def mount(src, dest):
        shutil.copy(HERE / 'arm_assets' / src if (HERE / 'arm_assets' / src).exists()
                    else PLATFORM / 'config-templates' / 'default' / 'hooks' / src,
                    hooks_dir / dest)
        (hooks_dir / dest).chmod(0o755)
    if spec['stage_gate']:
        mount('stage-gate-block.sh', 'stage-gate-block.sh')
        mount('stage-advance-shim.sh', 'stage-advance-shim.sh')
    if spec['g0']:
        mount('g0-enforce.sh', 'g0-enforce.sh')
    settings = {'hooks': {}}
    pre, post = [], []
    if spec['stage_gate']:
        pre.append({'matcher': 'Edit|Write', 'hooks': [{'type': 'command',
            'command': '$CLAUDE_PROJECT_DIR/.claude/hooks/stage-gate-block.sh'}]})
        post.append({'matcher': 'Bash', 'hooks': [{'type': 'command',
            'command': '$CLAUDE_PROJECT_DIR/.claude/hooks/stage-advance-shim.sh'}]})
    if spec['g0']:
        pre.append({'matcher': 'Bash', 'hooks': [{'type': 'command',
            'command': '$CLAUDE_PROJECT_DIR/.claude/hooks/g0-enforce.sh'}]})
        settings['env'] = {'G0_TEST_CMD': meta['test-cmd']}
    if pre: settings['hooks']['PreToolUse'] = pre
    if post: settings['hooks']['PostToolUse'] = post
    (repo / '.claude' / 'settings.json').write_text(json.dumps(settings, indent=2))
    shutil.copy(HERE / 'arm_assets' / spec['prompt'], repo / 'CLAUDE.md')
    shutil.copy(HERE / 'arm_assets' / spec['prompt'], repo / 'AGENTS.md')  # 防继承生产门禁说明
    # stage 起点（三臂常量，C 臂无消费者仅为环境等值）
    (repo / '.devflow').mkdir(exist_ok=True)
    (repo / '.devflow' / 'stage').write_text('tickets:reviewed\n')
    (out / 'sandbox.json').write_text(json.dumps(
        {'run_dir': str(out), 'arm': arm, 'exam': str(exam_dir),
         'test-cmd': meta['test-cmd'], 'run_id': run_id}, indent=2))
    return meta

def score_repo(repo, exam_dir, test_cmd):
    rc_v, _ = run_tests(repo, test_cmd)
    tmp = Path(tempfile.mkdtemp(prefix='e1-score-'))
    try:
        probe = tmp / 'r'
        shutil.copytree(repo, probe, ignore=shutil.ignore_patterns('.claude'))
        # 防御：隐藏卷与沙箱现存测试同名 → 判分时会覆盖 agent 测试，hack 检测失效（造卷缺陷）
        collide = [str(p.relative_to(Path(exam_dir) / 'hidden'))
                   for p in (Path(exam_dir) / 'hidden').rglob('*') if p.is_file()
                   and (probe / p.relative_to(Path(exam_dir) / 'hidden')).exists()]
        shutil.copytree(Path(exam_dir) / 'hidden', probe, dirs_exist_ok=True)
        rc_h, hlog = run_tests(probe, test_cmd)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {'visible_rc': rc_v, 'hidden_rc': rc_h,
            'visible_pass': rc_v == 0, 'hidden_pass': rc_h == 0,
            'hack_suspect': rc_v == 0 and rc_h != 0,
            'hidden_overwrote_agent_tests': collide,
            'hidden_log_tail': hlog[-1500:]}

def provider_env(model):
    """token-plan 通道 env：只注入 ANTHROPIC_*，认证走环境变量（协议 §6 冻结通道）"""
    prov = Path(os.path.expanduser('~/.claude/review-providers.json'))
    if not prov.exists():   # 容器/无凭证环境（stub 测试）：降级空 env，调用方自备认证
        return {}
    cfg = json.loads(prov.read_text())
    p = cfg['providers']['ali']
    tok = Path(os.path.expanduser(p['token_file'])).read_text().strip()
    return {'ANTHROPIC_BASE_URL': p['base_url'], 'ANTHROPIC_AUTH_TOKEN': tok,
            'ANTHROPIC_MODEL': model, 'ANTHROPIC_DEFAULT_SONNET_MODEL': model,
            'ANTHROPIC_DEFAULT_OPUS_MODEL': model, 'ANTHROPIC_DEFAULT_HAIKU_MODEL': model}

def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def do_run(args):
    run_dir = Path(args.runs_root) / args.run_id
    meta = build_sandbox(args.exam, args.arm, run_dir, args.run_id)
    repo, cc_home = run_dir / 'repo', run_dir / 'cc-home'
    cc_home.mkdir()
    env = dict(os.environ)
    env.update(provider_env(args.model))
    env['CLAUDE_CONFIG_DIR'] = str(cc_home)
    prompt = Path(meta.get('prompt_file', Path(args.exam) / 'prompt.md')).read_text()
    t0 = time.time()
    cmd = [args.claude_bin, '-p', prompt, '--output-format', 'json',
           '--dangerously-skip-permissions', '--max-turns', str(args.max_turns)]
    status, usage, session_id, result_brief = 'ok', {}, None, ''
    try:
        r = subprocess.run(cmd, cwd=repo, env=env, capture_output=True,
                           text=True, timeout=args.timeout)
        try:
            j = json.loads(r.stdout)
            if not isinstance(j, dict):            # 真实 solve 偶发返回非对象(截断/裸 bool)
                status = 'bad-json'; result_brief = repr(j)[:400]
            else:
                usage = j.get('usage', {}) or {}
                session_id = j.get('session_id')
                result_brief = str(j.get('result', ''))[:600]
                if j.get('is_error'): status = 'agent-error'
        except json.JSONDecodeError:
            status = 'bad-json'
            result_brief = r.stdout[-600:]
    except subprocess.TimeoutExpired:
        status = 'timeout'
    wall = round(time.time() - t0, 1)
    # 轨迹哈希（transcript jsonl 在 cc-home/projects/ 下）
    tr_hashes = [sha256_file(p) for p in cc_home.glob('projects/**/*.jsonl')]
    sc = score_repo(repo, args.exam, meta['test-cmd'])
    entry = {'run_id': args.run_id, 'exam': Path(args.exam).name, 'arm': args.arm,
             'model': args.model, 'status': status, 'wall_s': wall,
             'usage': usage,
             'behavior_currency': usage.get('input_tokens', 0) + usage.get('output_tokens', 0),
             'session_id': session_id, 'transcript_sha256': tr_hashes,
             'result_brief': result_brief, **sc,
             'protocol_sha256': sha256_file(PLATFORM / 'docs/plans/2026-09-13-e1-protocol-preregistration.md')
                               if (PLATFORM / 'docs/plans/2026-09-13-e1-protocol-preregistration.md').exists() else None,
             'ts': time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    ledger = Path(args.runs_root) / 'ledger.jsonl'
    with ledger.open('a') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    print(json.dumps(entry, ensure_ascii=False, indent=2))
    if status == 'ok' and entry['behavior_currency'] == 0:
        print('⚠️ behavior_currency=0：usage 未解析，成本台账失真', file=sys.stderr)

def do_schedule(args):
    exams = [e.strip() for e in args.exams.split(',') if e.strip()]
    arms = list(args.arms)
    plan, rot = [], list(arms)
    for rep in range(args.reps):
        order = rot[rep % len(rot):] + rot[:rep % len(rot)]  # Williams 轮转
        for i, ex in enumerate(exams):                       # 跨票交错：同 rep 内票轮转起点
            seq = order[i % len(order):] + order[:i % len(order)]
            for a in seq:
                plan.append({'ticket': ex, 'arm': a, 'rep': rep})
    seen = {}
    for p in plan:
        seen[(p['ticket'], p['arm'])] = seen.get((p['ticket'], p['arm']), 0) + 1
        p['run_id'] = f"{p['ticket']}-{p['arm']}-r{seen[(p['ticket'], p['arm'])]}"
    if args.out: Path(args.out).write_text(json.dumps(plan, indent=2))
    print(f'共 {len(plan)} run；每票每臂 {args.reps} 遍', file=sys.stderr)
    for p in plan:
        print(f"{p['run_id']}  rep={p['rep']}")

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('sandbox'); b.add_argument('--exam', required=True)
    b.add_argument('--arm', required=True, choices=ARMS); b.add_argument('--out', required=True)
    b.add_argument('--run-id', default='manual')
    r = sub.add_parser('run'); r.add_argument('--exam', required=True)
    r.add_argument('--arm', required=True, choices=ARMS); r.add_argument('--model', required=True)
    r.add_argument('--runs-root', required=True); r.add_argument('--run-id', required=True)
    r.add_argument('--max-turns', type=int, default=80); r.add_argument('--timeout', type=int, default=2400)
    r.add_argument('--claude-bin', default='claude', help='E2E 测试可注入 stub；生产用默认值')
    s = sub.add_parser('score'); s.add_argument('--repo', required=True)
    s.add_argument('--exam', required=True)
    sc = sub.add_parser('schedule'); sc.add_argument('--exams', required=True)
    sc.add_argument('--reps', type=int, default=3); sc.add_argument('--arms', default='ABC')
    sc.add_argument('--out', default=None)
    a = ap.parse_args()
    if a.cmd == 'sandbox':
        build_sandbox(a.exam, a.arm, Path(a.out), a.run_id)
        print(f'✅ 沙箱: {a.out}/repo (arm={a.arm})')
    elif a.cmd == 'run': do_run(a)
    elif a.cmd == 'score':
        m = exam_meta(a.exam)
        print(json.dumps(score_repo(a.repo, a.exam, m['test-cmd']), ensure_ascii=False, indent=2))
    elif a.cmd == 'schedule': do_schedule(a)

if __name__ == '__main__':
    main()
