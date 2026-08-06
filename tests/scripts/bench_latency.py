#!/usr/bin/env python3
"""Bot 全链路耗时分析工具。

数据源：
  A) langbot.db monitoring_llm_calls — LLM 推理耗时（duration_ms）、token 用量
  B) /tmp/silent_timing.log — 插件阶段耗时（gate、inject）
  C) /sync API — 端到端消息往返测试

用法：
  python3 bench_latency.py                    # 全量分析（读取 A+B）
  python3 bench_latency.py --quick            # 快速摘要（只看最近 50 条 LLM 调用）
  python3 bench_latency.py --send N           # 发送 N 条测试消息并测量 E2E 延迟
  python3 bench_latency.py --bottleneck       # 仅输出瓶颈诊断结论
"""

import json, os, sqlite3, subprocess, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from collections import defaultdict

BJT = timezone(timedelta(hours=8))

# === 配置 ===
NAS = os.environ.get('NAS_HOST', 'nas')
LANGBOT_DB = '/app/data/langbot.db'
TIMING_LOG = '/tmp/silent_timing.log'
BOT_UUID = '8053e7b4-f0b7-4264-b348-abc70eaa3550'  # AI对话
SECRET = 'udimc123'
SYNC_URL = f'http://langbot:2280/plugins/dou__langbot-silent-observer/sync?secret={SECRET}'
TEST_SESSION = 'group_1104330614'


def _ssh_exec(container: str, python_code: str, timeout: int = 30) -> str:
    """通过 SSH 在 NAS 容器中执行 Python 代码，返回 stdout。"""
    r = subprocess.run(
        ['ssh', f'root@{NAS}', 'docker', 'exec', '-i', container, 'python3'],
        input=python_code, capture_output=True, text=True, timeout=timeout
    )
    return r.stdout


def _ssh_cmd(container: str, cmd: str, timeout: int = 30) -> str:
    """通过 SSH 在 NAS 容器中执行 shell 命令，返回 stdout。"""
    r = subprocess.run(
        ['ssh', f'root@{NAS}', 'docker', 'exec', container, 'sh', '-c', cmd],
        capture_output=True, text=True, timeout=timeout
    )
    return r.stdout


def query_llm_stats(days: int = 7, limit: int = None) -> dict:
    """从 langbot.db 查询 LLM 调用统计数据。"""
    limit_clause = f'LIMIT {limit}' if limit else ''
    code = f'''
import sqlite3, json
db = sqlite3.connect("{LANGBOT_DB}")
sql = \"\"\"SELECT timestamp, model_name, input_tokens, output_tokens, total_tokens,
       duration, status, session_id, error_message
FROM monitoring_llm_calls
WHERE bot_id = '{BOT_UUID}' AND status = 'success'
  AND timestamp > datetime('now', '-{days} days')
ORDER BY timestamp DESC
{limit_clause}\"\"\"
rows = list(db.execute(sql))
print(json.dumps([list(r) for r in rows], ensure_ascii=False))
'''
    raw = _ssh_exec('langbot', code)
    try:
        rows = json.loads(raw.strip())
    except json.JSONDecodeError:
        print(f'[ERROR] Failed to parse LLM stats: {raw[:200]}')
        return {'error': raw[:500], 'rows': []}

    if not rows:
        return {'rows': [], 'count': 0}

    durations = sorted([r[5] for r in rows if r[5] is not None])
    input_tokens = [r[2] for r in rows if r[2] is not None]
    output_tokens = [r[3] for r in rows if r[3] is not None]

    def pct(arr, p):
        if not arr:
            return 0
        return arr[min(len(arr) - 1, len(arr) * p // 100)]

    # 按 session 分组
    by_session = defaultdict(list)
    for r in rows:
        sess = r[7] or 'unknown'
        by_session[sess].append(r[5])

    # 按日期分组
    by_date = defaultdict(list)
    for r in rows:
        date = (r[0] or '')[:10]
        by_date[date].append(r[5])

    # 输入 token vs 耗时 分组
    token_buckets = [(0, 4000), (4000, 6000), (6000, 8000), (8000, 10000),
                     (10000, 15000), (15000, 20000), (20000, 999999)]
    by_tokens = {}
    for lo, hi in token_buckets:
        durs = [r[5] for r in rows if lo <= (r[2] or 0) < hi]
        if durs:
            by_tokens[f'{lo//1000}k-{hi//1000}k'] = {
                'n': len(durs), 'p50': pct(sorted(durs), 50),
                'mean': sum(durs) // len(durs), 'max': max(durs)
            }

    # 输出 token vs 耗时 分组
    out_buckets = [(0, 50), (50, 100), (100, 200), (200, 500), (500, 1000), (1000, 99999)]
    by_out = {}
    for lo, hi in out_buckets:
        durs = [r[5] for r in rows if lo <= (r[3] or 0) < hi]
        if durs:
            by_out[f'{lo}-{hi}'] = {
                'n': len(durs), 'p50': pct(sorted(durs), 50),
                'mean': sum(durs) // len(durs), 'max': max(durs)
            }

    return {
        'rows': rows,
        'count': len(rows),
        'duration_ms': {
            'min': min(durations), 'max': max(durations),
            'p50': pct(durations, 50), 'p75': pct(durations, 75),
            'p90': pct(durations, 90), 'p95': pct(durations, 95),
            'p99': pct(durations, 99), 'mean': sum(durations) // len(durations),
        },
        'tokens': {
            'input_mean': sum(input_tokens) // len(input_tokens) if input_tokens else 0,
            'output_mean': sum(output_tokens) // len(output_tokens) if output_tokens else 0,
        },
        'by_session': {k: {'n': len(v), 'mean': sum(v)//len(v), 'p50': pct(sorted(v), 50)}
                       for k, v in by_session.items()},
        'by_date': {k: {'n': len(v), 'mean': sum(v)//len(v)} for k, v in sorted(by_date.items())},
        'by_input_tokens': by_tokens,
        'by_output_tokens': by_out,
    }


def query_timing_log() -> list:
    """从 /tmp/silent_timing.log 读取插件阶段耗时。"""
    raw = _ssh_cmd('langbot-plugin', 'cat /tmp/silent_timing.log 2>/dev/null | tail -200')
    entries = []
    for line in raw.strip().split('\n'):
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return entries


def analyze_timing(entries: list) -> dict:
    """分析 timing log，计算各阶段耗时分布。"""
    gate_entries = [e for e in entries if e.get('stage') == 'gate']
    inject_entries = [e for e in entries if e.get('stage') == 'inject']

    def stats(arr, key='total_ms'):
        vals = sorted([e[key] for e in arr if key in e])
        if not vals:
            return None
        n = len(vals)
        return {
            'n': n, 'min': min(vals), 'max': max(vals),
            'p50': vals[n//2], 'mean': sum(vals)//n,
        }

    # 配对 gate+inject（相同 session 且时间接近）
    paired = []
    inject_by_session = defaultdict(list)
    for e in inject_entries:
        inject_by_session[e.get('session', '')].append(e)
    for g in gate_entries:
        sess = g.get('session', '')
        candidates = inject_by_session.get(sess, [])
        for i in candidates:
            if abs(g.get('ts', 0) - i.get('ts', 0)) < 30:
                paired.append({
                    'session': sess,
                    'gate_ms': g.get('total_ms', 0),
                    'save_ms': g.get('save_ms', 0),
                    'inject_ms': i.get('total_ms', 0),
                    'total_plugin_ms': g.get('total_ms', 0) + i.get('total_ms', 0),
                    'trigger': i.get('trigger', '?'),
                })
                break

    return {
        'gate': stats(gate_entries),
        'inject': stats(inject_entries),
        'save': stats([e for e in gate_entries if e.get('save_ms', 0) > 0], 'save_ms'),
        'paired': paired,
    }


def send_test_message(session: str, text: str) -> dict:
    """通过 /sync 发送测试消息，测量 E2E 延迟。"""
    import subprocess
    payload = json.dumps({'session_name': session, 'user_message_text': text}).encode()
    t0 = time.time()
    try:
        req = urllib.request.Request(SYNC_URL, data=payload, headers={
            'Content-Type': 'application/json',
            'User-Agent': 'bench_latency/1.0',
        })
        resp = urllib.request.urlopen(req, timeout=60)
        body = resp.read().decode()
        elapsed = (time.time() - t0) * 1000
        return {'ok': True, 'elapsed_ms': round(elapsed), 'body': body[:500],
                'status': resp.status}
    except urllib.error.HTTPError as e:
        elapsed = (time.time() - t0) * 1000
        body = e.read().decode()[:500] if e.fp else ''
        return {'ok': False, 'elapsed_ms': round(elapsed), 'body': body,
                'status': e.code, 'error': str(e)}
    except Exception as e:
        elapsed = (time.time() - t0) * 1000
        return {'ok': False, 'elapsed_ms': round(elapsed), 'error': str(e)}


def run_e2e_bench(n: int = 5, delay: float = 3.0) -> list:
    """发送 N 条测试消息并记录 E2E 延迟。"""
    results = []
    messages = [
        '你好',
        '今天天气怎么样？',
        '帮我查一下最近的消息',
        '1+1等于几？',
        '讲个笑话',
        '最近群里有啥新鲜事？',
        '表情包来一套',
        '你是谁？',
        '帮我记一下：明天下午3点开会',
        '周末去哪玩好？',
    ]
    for i in range(n):
        text = messages[i % len(messages)]
        print(f'  [{i+1}/{n}] sending: "{text}" ...', end=' ', flush=True)
        r = send_test_message(TEST_SESSION, text)
        status = 'OK' if r['ok'] else f'FAIL({r.get("status","?")})'
        print(f'{status} {r["elapsed_ms"]}ms')
        results.append(r)
        if i < n - 1:
            time.sleep(delay)
    return results


def print_bottleneck(llm_stats: dict, timing_stats: dict, e2e_results: list = None):
    """输出瓶颈诊断结论。"""
    print()
    print('=' * 60)
    print('  瓶 颈 诊 断')
    print('=' * 60)

    dur = llm_stats.get('duration_ms', {})
    tokens = llm_stats.get('tokens', {})
    by_out = llm_stats.get('by_output_tokens', {})

    print(f'\n📊 LLM 推理耗时（{llm_stats.get("count", 0)} 次调用）:')
    print(f'   P50={dur.get("p50",0)}ms  P75={dur.get("p75",0)}ms  '
          f'P90={dur.get("p90",0)}ms  P95={dur.get("p95",0)}ms')
    print(f'   输入 tokens 均值={tokens.get("input_mean",0)}  输出 tokens 均值={tokens.get("output_mean",0)}')

    gate = timing_stats.get('gate', {}) or {}
    inject = timing_stats.get('inject', {}) or {}
    save = timing_stats.get('save', {}) or {}

    if gate:
        print(f'\n📊 插件阶段耗时:')
        print(f'   Gate: P50={gate.get("p50",0)}ms  均值={gate.get("mean",0)}ms')
    if save:
        print(f'   ├─ KB 保存: P50={save.get("p50",0)}ms  均值={save.get("mean",0)}ms')
    if inject:
        print(f'   Inject: P50={inject.get("p50",0)}ms  均值={inject.get("mean",0)}ms')

    if e2e_results:
        ok_results = [r for r in e2e_results if r['ok']]
        if ok_results:
            durs = sorted([r['elapsed_ms'] for r in ok_results])
            print(f'\n📊 E2E 往返延迟（{len(ok_results)} 次测试）:')
            print(f'   P50={durs[len(durs)//2]}ms  min={min(durs)}ms  max={max(durs)}ms')

    # === 瓶颈判定 ===
    print()
    print('🔍 瓶颈分析:')

    findings = []

    # 1. 输出 token 是最大瓶颈
    if by_out:
        small = by_out.get('0-50', {})
        large = by_out.get('500-1000', {})
        if small and large:
            ratio = large.get('p50', 0) / max(small.get('p50', 1), 1)
            if ratio > 3:
                findings.append(
                    f'⚠️  输出 token 数量是最大瓶颈：500-1000 tok 的 P50={large["p50"]}ms '
                    f'是 0-50 tok P50={small["p50"]}ms 的 {ratio:.1f}x'
                )

    huge_out = by_out.get('1000-99999', {})
    if huge_out and huge_out.get('p50', 0) > 10000:
        findings.append(
            f'🔴 长回复（>1000 tok）P50={huge_out["p50"]}ms —— '
            f'占调用 {huge_out["n"]}/{llm_stats.get("count", 1)} 次，显著拉高 P95'
        )

    # 2. 插件开销
    if gate and gate.get('p50', 0) > 500:
        findings.append(f'⚠️  Gate 处理 P50={gate["p50"]}ms > 500ms，需优化 KB 写入')
    elif gate:
        findings.append(f'✅ Gate 处理 P50={gate["p50"]}ms，开销合理')

    if inject and inject.get('p50', 0) > 500:
        findings.append(f'⚠️  Inject 处理 P50={inject["p50"]}ms > 500ms，需优化 KB 查询')
    elif inject:
        findings.append(f'✅ Inject 处理 P50={inject["p50"]}ms，开销合理')

    # 3. 输入 token 影响
    by_in = llm_stats.get('by_input_tokens', {})
    if by_in:
        lo = by_in.get('6k-8k', {})
        hi = by_in.get('10k-15k', {})
        if lo and hi:
            ratio = hi.get('p50', 0) / max(lo.get('p50', 1), 1)
            if ratio > 1.5:
                findings.append(
                    f'💡 输入 token 影响：10k-15k 的 P50={hi["p50"]}ms '
                    f'是 6k-8k P50={lo["p50"]}ms 的 {ratio:.1f}x —— '
                    f'建议控制 prompt 大小或减少 timeline 条数'
                )

    # 4. 总瓶颈占比
    if gate and dur:
        plugin_ms = gate.get('p50', 0) + (inject.get('p50', 0) if inject else 0)
        llm_ms = dur.get('p50', 0)
        total = plugin_ms + llm_ms
        if total > 0:
            llm_pct = llm_ms * 100 // total
            plugin_pct = plugin_ms * 100 // total
            findings.append(
                f'📊 耗时占比：LLM 推理 {llm_pct}% ({llm_ms}ms) / '
                f'插件处理 {plugin_pct}% ({plugin_ms}ms)'
            )

    if not findings:
        findings.append('✅ 未发现明显瓶颈')

    for f in findings:
        print(f'   {f}')

    # 建议
    print()
    print('💡 优化建议:')
    if dur.get('p95', 0) > 10000:
        print('   1. 限制 max_tokens（当前无限制），截断过长回复')
    if tokens.get('output_mean', 0) > 300:
        print('   2. Prompt 中加 "回复控制在 100 字以内" 减少输出 token')
    if tokens.get('input_mean', 0) > 10000:
        print('   3. 减少 history_count 或启用压缩摘要降低输入 token')
    print('   4. 切换到更快的模型（如 deepseek-v4-flash 替代 deepseek-v4）')
    print('   5. 启用 streaming 回复减少感知延迟')


def print_summary(llm_stats, timing_stats):
    """打印完整报告。"""
    dur = llm_stats.get('duration_ms', {})
    tokens = llm_stats.get('tokens', {})
    by_out = llm_stats.get('by_output_tokens', {})
    by_in = llm_stats.get('by_input_tokens', {})
    by_date = llm_stats.get('by_date', {})
    by_session = llm_stats.get('by_session', {})

    print('╔══════════════════════════════════════════════╗')
    print('║  Bot 全链路耗时分析报告                       ║')
    print('╠══════════════════════════════════════════════╣')

    print(f'\n📊 LLM 推理耗时分布（{llm_stats.get("count", 0)} 次成功调用）:')
    print(f'   {"Min":>5}  {"P50":>6}  {"P75":>6}  {"P90":>6}  {"P95":>6}  {"P99":>6}  {"Max":>6}  {"Mean":>6}')
    print(f'   {dur.get("min",0):5}  {dur.get("p50",0):6}  {dur.get("p75",0):6}  '
          f'{dur.get("p90",0):6}  {dur.get("p95",0):6}  {dur.get("p99",0):6}  '
          f'{dur.get("max",0):6}  {dur.get("mean",0):6}  ms')

    print(f'\n📊 Token 用量:')
    print(f'   输入: 均值={tokens.get("input_mean",0)} tok')
    print(f'   输出: 均值={tokens.get("output_mean",0)} tok')

    if by_out:
        print(f'\n📊 输出 token 对耗时的影响:')
        for k, v in by_out.items():
            bar = '█' * (v['p50'] // 1000)
            print(f'   out {k:>10} tok: P50={v["p50"]:5d}ms  mean={v["mean"]:5d}ms  n={v["n"]:3d}  {bar}')

    if by_in:
        print(f'\n📊 输入 token 对耗时的影响:')
        for k, v in by_in.items():
            print(f'   in  {k:>10} tok: P50={v["p50"]:5d}ms  mean={v["mean"]:5d}ms  n={v["n"]:3d}')

    if by_date:
        print(f'\n📊 每日趋势:')
        for date, v in by_date.items():
            print(f'   {date}: n={v["n"]:3d}  mean={v["mean"]:5d}ms')

    if by_session:
        print(f'\n📊 按会话:')
        for sess, v in sorted(by_session.items()):
            print(f'   {sess}: n={v["n"]:3d}  mean={v["mean"]:5d}ms  P50={v["p50"]}ms')

    gate = timing_stats.get('gate', {}) or {}
    inject = timing_stats.get('inject', {}) or {}
    save = timing_stats.get('save', {}) or {}

    if gate or inject:
        print(f'\n📊 插件阶段耗时:')
        if gate:
            print(f'   Gate:  n={gate.get("n",0)}  P50={gate.get("p50",0)}ms  '
                  f'mean={gate.get("mean",0)}ms  max={gate.get("max",0)}ms')
        if save:
            print(f'   ├─ KB保存: n={save.get("n",0)}  P50={save.get("p50",0)}ms  '
                  f'mean={save.get("mean",0)}ms')
        if inject:
            print(f'   Inject: n={inject.get("n",0)}  P50={inject.get("p50",0)}ms  '
                  f'mean={inject.get("mean",0)}ms  max={inject.get("max",0)}ms')


def main():
    import argparse
    ap = argparse.ArgumentParser(description='Bot 全链路耗时分析')
    ap.add_argument('--quick', action='store_true', help='快速摘要')
    ap.add_argument('--bottleneck', action='store_true', help='仅瓶颈诊断')
    ap.add_argument('--send', type=int, default=0, metavar='N', help='发送 N 条测试消息')
    ap.add_argument('--days', type=int, default=7, help='分析天数（默认 7）')
    args = ap.parse_args()

    limit = 50 if args.quick else None

    print('🔍 采集 LangBot 监控数据...')
    llm_stats = query_llm_stats(days=args.days, limit=limit)

    if 'error' in llm_stats:
        print(f'❌ 数据采集失败: {llm_stats["error"][:200]}')
        sys.exit(1)

    print('🔍 采集插件计时日志...')
    timing_entries = query_timing_log()
    timing_stats = analyze_timing(timing_entries)

    e2e_results = None
    if args.send > 0:
        print(f'\n🚀 E2E 延迟测试（发送 {args.send} 条消息）...')
        e2e_results = run_e2e_bench(args.send)

    if args.bottleneck:
        print_bottleneck(llm_stats, timing_stats, e2e_results)
    else:
        print_summary(llm_stats, timing_stats)
        print_bottleneck(llm_stats, timing_stats, e2e_results)


if __name__ == '__main__':
    main()
