#!/usr/bin/env python3
"""E1 pilot/主段 编排器：读 pilot-plan.json，逐格串行调 run_driver.run，跳过已完成 run_id(断点续跑)。
用法: python3 pilot_runner.py --plan <json> --exam-root <e1 dir> --runs-root <runs dir> [--model ..] [--max-turns ..]
"""
import argparse, json, shutil, subprocess, sys, time
from pathlib import Path

def done_ids(ledger):
    ids = set()
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            try: ids.add(json.loads(line)['run_id'])
            except Exception: pass
    return ids

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', required=True); ap.add_argument('--exam-root', required=True)
    ap.add_argument('--runs-root', required=True); ap.add_argument('--model', default='qwen3.8-flash[1m]')
    ap.add_argument('--max-turns', type=int, default=120); ap.add_argument('--timeout', type=int, default=2400)
    ap.add_argument('--claude-bin', default='claude')
    a = ap.parse_args()
    plan = json.load(open(a.plan))
    ledger = Path(a.runs_root) / 'ledger.jsonl'
    driver = Path(__file__).resolve().parent / 'run_driver.py'
    done = done_ids(ledger)
    todo = [p for p in plan if p['run_id'] not in done]
    print(f'计划 {len(plan)}，已完成 {len(done)}，本轮跑 {len(todo)}', file=sys.stderr, flush=True)
    for i, p in enumerate(todo, 1):
        exam = Path(a.exam_root) / p['ticket']
        if not (exam / 'exam.yaml').exists():
            print(f'[{i}/{len(todo)}] 跳过缺卷 {p["ticket"]}', file=sys.stderr); continue
        print(f'[{i}/{len(todo)}] {p["run_id"]} 开始 {time.strftime("%H:%M:%S")}', file=sys.stderr, flush=True)
        # 孤儿自愈：run_dir 存在但台账无此 run_id = 上次跑到一半被杀/崩 → 清掉重跑
        # （否则 build_sandbox 见目录存在会拒绝，该格永远卡死）
        orphan = Path(a.runs_root) / p['run_id']
        if orphan.exists():
            shutil.rmtree(orphan); print(f'  清理孤儿半成品 {p["run_id"]}', file=sys.stderr, flush=True)
        r = subprocess.run(['python3', str(driver), 'run', '--exam', str(exam),
                            '--arm', p['arm'], '--model', a.model, '--runs-root', a.runs_root,
                            '--run-id', p['run_id'], '--max-turns', str(a.max_turns),
                            '--timeout', str(a.timeout), '--claude-bin', a.claude_bin],
                           capture_output=True, text=True)
        e = {}
        if ledger.exists():
            last = ledger.read_text().rstrip().split('\n')[-1] if ledger.stat().st_size else ''
            try: e = json.loads(last)
            except Exception: pass
        print(f'  → status={e.get("status","?")} wall={e.get("wall_s","?")}s bc={e.get("behavior_currency","?")} '
              f'vis={e.get("visible_pass")} hid={e.get("hidden_pass")} hack={e.get("hack_suspect")}',
              file=sys.stderr, flush=True)
        if r.returncode != 0:
            print(f'  ! driver rc={r.returncode}: {r.stderr[-200:]}', file=sys.stderr)
    print('PILOT DONE', file=sys.stderr, flush=True)

if __name__ == '__main__':
    main()
