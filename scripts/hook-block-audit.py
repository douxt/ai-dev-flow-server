#!/usr/bin/env python3
"""hook-block-audit.py — CC transcript 钩子阻断/报错分层审计

背景教训（2026-09-11 生图会话事件）：粗粒度统计把 exitCode 126/1 的
hook_non_blocking_error（钩子崩溃/无执行位 = 未拦截，工具照常执行）与真实
exit 2 拦截混计，"349 次 block"中真 block 不足一成。本工具按记录形态分层，
把真 block 还原到 file_path + hook + 原因，供判定误拦/正确拦截。

用法:
  python3 hook-block-audit.py <transcript.jsonl> [<transcript2.jsonl> ...]
  python3 hook-block-audit.py --since 11:00 --until 12:30 <file>
  # --since/--until 为本地(+08)时间窗；transcript 时间戳是 UTC，自动换算
输出: stdout 文本报告（真 block 明细 + 噪声分层 + 按分钟分布）
退出码: 恒 0（分析工具）；transcript 不存在时 2
"""
import sys, os, json, re, argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=8))
HOOK_ERR_RE = re.compile(
    r'^(PreToolUse|PostToolUse):(\w+) hook error: \[?(?:bash )?([^\]]*?/([\w.\-]+\.sh))\]?:?\s*(.*)', re.S)

def parse(path):
    tool_names = {}   # toolUseID -> (name, target)
    real_blocks = []  # (ts, event, target, hook, reason)
    noise = Counter() # (hookName, exitCode, stderr_head)
    for line in open(path, encoding='utf-8', errors='replace'):
        try:
            d = json.loads(line)
        except Exception:
            continue
        ts_raw = d.get('timestamp') or ''
        a = d.get('attachment')
        if isinstance(a, dict):
            if a.get('type') == 'hook_non_blocking_error':
                ec = a.get('exitCode')
                if ec in (1, 126):  # 非阻断：钩子崩溃/无执行位，工具照常执行
                    noise[(a.get('hookName', '?'), ec,
                           (a.get('stderr') or '').strip()[:70])] += 1
                continue
            if a.get('type') == 'hook_blocking_error':
                ev = a.get('blockingError') or {}
                real_blocks.append((ts_raw, a.get('hookName', '?'), '',
                                    'blocking_error',
                                    str(ev.get('blockingError', ''))[:160].replace('\n', ' ')))
                continue
        msg = d.get('message')
        if not isinstance(msg, dict):
            continue
        content = msg.get('content')
        if not isinstance(content, list):
            continue
        if d.get('type') == 'assistant':
            for part in content:
                if isinstance(part, dict) and part.get('type') == 'tool_use':
                    inp = part.get('input') or {}
                    tgt = inp.get('file_path') or inp.get('path') or (inp.get('command') or '')[:60]
                    tool_names[part.get('id')] = (part.get('name', '?'), str(tgt))
        elif d.get('type') == 'user':
            for part in content:
                if not (isinstance(part, dict) and part.get('type') == 'tool_result'
                        and part.get('is_error')):
                    continue
                c = part.get('content')
                txt = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
                m = HOOK_ERR_RE.match(txt.strip())
                if m:  # exit 2 真拦截回灌模型的形态："PreToolUse:X hook error: [cmd]: 原因"
                    phase, tool, cmd, hook, reason = m.groups()
                    tgt = tool_names.get(part.get('tool_use_id'), ('?', ''))[1]
                    real_blocks.append((ts_raw, f'{phase}:{tool}', tgt, hook,
                                        reason.strip()[:160].replace('\n', ' ')))
    return tool_names, real_blocks, noise

def local(ts):
    try:
        return datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone(TZ)
    except Exception:
        return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+')
    ap.add_argument('--since', help='本地时间窗起 HH:MM')
    ap.add_argument('--until', help='本地时间窗止 HH:MM')
    args = ap.parse_args()
    all_blocks, all_noise = [], Counter()
    for f in args.files:
        if not os.path.isfile(f):
            print(f"❌ 不存在: {f}", file=sys.stderr); return 2
        _, b, n = parse(f)
        all_blocks += b; all_noise += n
    def in_win(ts):
        if not (args.since or args.until):
            return True
        t = local(ts)
        if not t:
            return False
        hm = t.strftime('%H:%M')
        return (not args.since or hm >= args.since) and (not args.until or hm <= args.until)
    blocks = sorted([b for b in all_blocks if in_win(b[0])], key=lambda x: x[0])
    print(f"═══ 真实拦截（exit 2 / blocking_error）: {len(blocks)} 条 ═══")
    print('按钩子:', dict(Counter(b[3] for b in blocks).most_common()))
    per_min = Counter((local(b[0]).strftime('%H:%M') if local(b[0]) else '?') for b in blocks)
    print('按分钟:', dict(sorted(per_min.items())))
    print('\n按 (事件,钩子,原因) 聚合:')
    for k, v in Counter((b[1], b[3], b[4][:70]) for b in blocks).most_common(15):
        print(f'  {v:4d}  {k[0]} | {k[1]} | {k[2]}')
    print('\n明细（前 40）:')
    for b in blocks[:40]:
        t = local(b[0])
        print(f'  {t.strftime("%H:%M:%S") if t else b[0][:19]}  [{b[1]}] {b[2][:70]}  ← {b[3]}: {b[4][:80]}')
    print("\n═══ 钩子崩溃噪声（exit 1/126 = 非拦截，工具照常执行；勿计入 block）═══")
    for (hook, ec, err), v in all_noise.most_common(12):
        print(f'  {v:5d}  {hook} rc={ec}  {err}')
    return 0

if __name__ == '__main__':
    sys.exit(main())
