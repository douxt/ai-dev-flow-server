#!/usr/bin/env python3
"""E1 造卷器：从仓库历史票 + 修复 commit 区间产出抗污染考卷（实验协议见 docs/plans/2026-09-13-e1-protocol-preregistration.md）。

三道关：
  关1 历史剥离 —— 基线用 git archive 快照重建为"仅一个提交"的新仓，无 remote、无未来历史
  关2 fail-to-pass 入场券 —— 隐藏卷必须在基线必挂、叠加原修复后必过，二者任一不满足即弃题
  关3 可推导审查 —— 题面泄题正则扫描 + 人工推导审查标记，未过审的卷子 status=needs-review
"""
import argparse, hashlib, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

TEST_PATH_RE = re.compile(r'(^|/)(tests?|testing)/|test_[^/]*\.py$|_test\.go$|\.(spec|test)\.[jt]sx?$')
LEAK_RE = re.compile(
    r'PR\s*ready|已备好|见\s*[0-9a-f]{7,}|参考\s*commit|修复方案是把|改成\s*`|'
    r'具体实现|diff\s*如下|patch\s*如下|解法[:：]', re.I)

def git(repo, *args, **kw):
    return subprocess.run(['git', '-C', str(repo), *args],
                          capture_output=True, text=True, **kw)

def need_git(repo, *args):
    r = git(repo, *args)
    if r.returncode != 0:
        sys.exit(f'❌ git {" ".join(args)}: {r.stderr.strip()}')
    return r.stdout.strip()

def is_test_file(p):
    return bool(TEST_PATH_RE.search(p))

def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def snapshot_baseline(repo, base_commit, dest):
    dest.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(f'git -C {repo} archive {base_commit} | tar -x -C {dest}',
                       shell=True, capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f'❌ archive 失败: {p.stderr}')
    need_git(dest, 'init', '-q', '-b', 'exam')
    # 显式脱离全局 core.hooksPath（v3.6 全局串联会拦截任何新仓的 commit——考卷快照必须自造）
    need_git(dest, 'config', 'core.hooksPath', '.git/hooks')
    need_git(dest, '-c', 'user.email=e@x', '-c', 'user.name=exam', 'add', '-A')
    need_git(dest, '-c', 'user.email=e@x', '-c', 'user.name=exam',
             'commit', '-q', '-m', 'baseline')

def collect_hidden(repo, commits_spec, test_files, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in test_files:
        content = git(repo, 'show', f'{commits_spec.split("..")[1]}:{f}')
        if content.returncode != 0:
            sys.exit(f'❌ 隐藏卷文件 {f} 在修复末 commit 不存在——测试可能后续被删，弃题')
        dst = out_dir / f
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content.stdout)

def run_tests(repo_dir, test_cmd, timeout=600):
    try:
        r = subprocess.run(test_cmd, shell=True, cwd=repo_dir,
                           capture_output=True, text=True, timeout=timeout)
        return r.returncode
    except subprocess.TimeoutExpired:
        return 99

def proof(chechedk_dir, hidden_dir, test_cmd):
    shutil.copytree(hidden_dir, chechedk_dir, dirs_exist_ok=True)
    return run_tests(chechedk_dir, test_cmd)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', required=True)
    ap.add_argument('--ticket', required=True, help='题面 markdown 路径（票文件）')
    ap.add_argument('--fix-commits', required=True, help='first..last（票对应的修复提交区间）')
    ap.add_argument('--test-cmd', required=True, help='隐藏卷执行命令，如 python3 -m pytest -q')
    ap.add_argument('--out', required=True, help='产出目录 exams/<exam-id>/')
    ap.add_argument('--split', default='report', choices=['dev', 'report', 'holdback'])
    ap.add_argument('--exam-id', default=None)
    ap.add_argument('--ticket-at', default=None,
                    help='题面取该 commit 的票历史版本（防实现期附注泄题；声明过滤仍以票当前版为准）')
    ap.add_argument('--drop-tests', action='append', default=[],
                    help='整文件剔除出隐藏卷（可重复），理由须入 amendment')
    ap.add_argument('--deselect', action='append', default=[],
                    help='pytest --deselect 断言级剔除（path::test，可重复）')
    a = ap.parse_args()

    repo = Path(a.repo).resolve()
    first, last = a.fix_commits.split('..')
    r = git(repo, 'rev-parse', f'{first}^')
    if r.returncode != 0:
        sys.exit('❌ --fix-commits 的 first 应为该票的第一个修复 commit（其父=基线）；'
                 f'first 无父提交或不可解析: {first}')
    base = r.stdout.strip()
    exam_id = a.exam_id or f'{Path(a.ticket).stem}-{last[:8]}'
    out = Path(a.out) / exam_id
    if out.exists():
        sys.exit(f'❌ {out} 已存在（考卷不可覆盖，防止无声漂移）')

    changed = [f for f in need_git(repo, 'diff', '--name-only', base, last).splitlines() if f]
    if not changed:
        sys.exit('❌ 修复区间无文件变化')
    test_files = [f for f in changed if is_test_file(f)]
    impl_files = [f for f in changed if not is_test_file(f)]
    if not test_files:
        sys.exit('❌ 关2失败：修复未附带测试文件，无法构成隐藏卷')

    # 声明过滤：隐藏卷 ⊆ 票头 test_files（修复区间跨票夹带别人测试=DEFECT-015 同族洞）
    dropped = list(a.drop_tests)
    decl = re.search(r'test_files:\s*\[([^\]]*)\]', Path(a.ticket).read_text())
    if decl:
        declared = {x.strip().strip('"\'') for x in decl.group(1).split(',') if x.strip()}
        stray = [f for f in test_files if f not in declared]
        if stray:
            print(f'· 声明过滤剔除（票 test_files 未列）: {stray}')
            dropped += stray
        test_files = [f for f in test_files if f in declared]
    else:
        print('⚠️ 票头无 test_files 声明，跳过声明过滤（审卷段将按 alignment 判据兜底）')
    if a.drop_tests:
        test_files = [f for f in test_files if f not in a.drop_tests]
    if not test_files:
        sys.exit('❌ 过滤后隐藏卷为空')
    # 被剔文件若在基线已存在：checkout 里旧版会被本票实现连带打破（原修复曾被迫 align 它），
    # 判分须 --ignore 之——其失败与本票验收行为无关，属相邻票整备
    stale = [f for f in dropped
             if f in need_git(repo, 'ls-tree', '-r', '--name-only', base).splitlines()]
    if stale:
        print(f'· 判分忽略基线旧版（被剔但基线存在）: {stale}')
    test_cmd = (a.test_cmd
                + ''.join(f' --ignore {f}' for f in stale)
                + ''.join(f' --deselect {d}' for d in a.deselect))

    checkout, hidden = out / 'checkout', out / 'hidden'
    print(f'· 关1 历史剥离: baseline={base[:8]} → 无历史快照')
    snapshot_baseline(repo, base, checkout)
    collect_hidden(repo, a.fix_commits, test_files, hidden)

    print('· 关2 fail-to-pass：两验证 run（本地执行，零 API）')
    tmp_a = tempfile.mkdtemp(prefix='f2p-a-')
    snap_a = Path(tmp_a) / 'c'
    shutil.copytree(checkout, snap_a)
    rc_fail = proof(snap_a, hidden, test_cmd)
    tmp_b = tempfile.mkdtemp(prefix='f2p-b-')
    snap_b = Path(tmp_b) / 'c'
    shutil.copytree(checkout, snap_b)
    diff = git(repo, 'diff', base, last, '--', *impl_files)
    if diff.returncode != 0:
        sys.exit(f'❌ 生成实现 diff 失败: {diff.stderr}')
    (snap_b / '_impl.patch').write_text(diff.stdout)
    r = subprocess.run(f'cd {snap_b} && git apply -p1 _impl.patch && rm _impl.patch',
                       shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f'❌ 原修复 patch 不可应用（依赖了历史里的其他改动？）: {r.stderr[:300]}')
    rc_pass = proof(snap_b, hidden, test_cmd)
    shutil.rmtree(tmp_a, ignore_errors=True); shutil.rmtree(tmp_b, ignore_errors=True)
    if rc_fail == 0:
        sys.exit('❌ 关2失败：隐藏卷在基线上就通过（题目太弱或测错东西），弃题')
    if rc_pass != 0:
        sys.exit(f'❌ 关2失败：原修复未让隐藏卷通过（rc={rc_pass}），测的可能是实现细节而非可推导行为')

    if a.ticket_at:
        rel = os.path.relpath(Path(a.ticket).resolve(), repo)
        pr = git(repo, 'show', f'{a.ticket_at}:{rel}')
        if pr.returncode != 0:
            sys.exit(f'❌ --ticket-at 版本无此票: {a.ticket_at}:{rel}')
        prompt = pr.stdout
        print(f'· 题面取历史版: {a.ticket_at}:{rel}（当前版仅用于 test_files 声明过滤）')
    else:
        prompt = Path(a.ticket).read_text()
    leaks = LEAK_RE.findall(prompt)
    out_join = 'sealed' if not leaks else 'needs-review'
    print(f'· 关3 题面审查: {"命中泄题模式 " + str(leaks) if leaks else "正则无命中"}（仍需人工推导审查）')

    files = {str(p.relative_to(hidden)): sha256(p) for p in hidden.rglob('*') if p.is_file()}
    meta = [
        f'# exam {exam_id}', f'exam-id: {exam_id}', f'repo: {repo}',
        f'baseline-commit: {base}', f'fix-commits: {a.fix_commits}',
        f'test-cmd: {test_cmd}', f'split: {a.split}', f'status: {out_join}',
        f'fail-to-pass: baseline_rc={rc_fail} fixed_rc={rc_pass}',
    ]
    if a.ticket_at: meta.append(f'ticket-at: {a.ticket_at}')
    if a.drop_tests: meta.append('drop-tests: ' + ' '.join(a.drop_tests))
    if a.deselect: meta.append('deselect: ' + ' '.join(a.deselect))
    if stale: meta.append('ignore-stale: ' + ' '.join(stale))
    meta = meta + [
        'derivation-review: pending',
        'prompt-sha256: ' + hashlib.sha256(prompt.encode()).hexdigest(),
        'hidden-sha256:',
    ]
    meta += [f'  {h}  {f}' for f, h in sorted(files.items())]
    (out / 'exam.yaml').write_text('\n'.join(meta) + '\n')
    (out / 'prompt.md').write_text(prompt)
    print(f'✅ 封卷: {out}/exam.yaml (status={out_join})')
    if leaks:
        print('⚠️ 存在泄题命中——人工删除泄题段后将 status 改 sealed 并重算哈希')

if __name__ == '__main__':
    main()
