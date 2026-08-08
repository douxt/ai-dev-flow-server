#!/usr/bin/env python3
"""查询压缩日志，输出统计/趋势/最近记录。
用法（langbot 容器内）:
  python3 /tmp/query_compression.py --all
  python3 /tmp/query_compression.py --session group_116381172 --last 5
  python3 /tmp/query_compression.py --since 24h
  python3 /tmp/query_compression.py --summary-trend
"""
import sqlite3, json, sys, argparse, os, time
from datetime import datetime, timedelta, timezone

DB_PATH = os.environ.get(
    'COMPRESSION_DB',
    '/app/data/plugins/dou__langbot-silent-observer/chat_index.db',
)
BJT = timezone(timedelta(hours=8))


def connect():
    if not os.path.exists(DB_PATH):
        print(json.dumps({"error": f"DB not found: {DB_PATH}"}))
        sys.exit(1)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def parse_since(s: str) -> float:
    """解析 --since 参数: 24h / 7d / 1h."""
    s = s.strip().lower()
    if s.endswith('h'):
        return time.time() - int(s[:-1]) * 3600
    if s.endswith('d'):
        return time.time() - int(s[:-1]) * 86400
    raise ValueError(f"unsupported since format: {s}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--last', type=int, default=10, help='最近 N 次 (默认 10)')
    p.add_argument('--session', help='按 session 过滤')
    p.add_argument('--since', help='时间范围 (24h/7d/1h)')
    p.add_argument('--summary-trend', action='store_true', help='摘要趋势')
    p.add_argument('--wide', action='store_true', help='宽表格')
    args = p.parse_args()

    db = connect()
    since_ts = parse_since(args.since) if args.since else 0

    # ── 统计摘要 ──
    wheres = ['started_at >= ?']
    params = [since_ts]
    if args.session:
        wheres.append('session_name = ?')
        params.append(args.session)

    base = f"FROM compression_log WHERE {' AND '.join(wheres)}"
    total = db.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
    oks = db.execute(f"SELECT COUNT(*) {base} AND status='ok'", params).fetchone()[0]
    fails = db.execute(f"SELECT COUNT(*) {base} AND status='fail'", params).fetchone()[0]
    timeouts = db.execute(f"SELECT COUNT(*) {base} AND status='timeout'", params).fetchone()[0]
    parse_nones = db.execute(f"SELECT COUNT(*) {base} AND status='parse_none'", params).fetchone()[0]

    stats_row = db.execute(
        f"SELECT AVG(duration_ms), AVG(input_chars), AVG(output_chars), "
        f"AVG(msg_count), AVG(summary_chars_after - summary_chars_before) "
        f"{base}", params
    ).fetchone()

    print("=" * 60)
    label = f"(最近 {args.since})" if args.since else "(全部)"
    print(f"压缩统计 {label}")
    print(f"  总次数: {total}  成功: {oks}  失败: {fails}  timeout: {timeouts}  parse_none: {parse_nones}")
    if total > 0:
        print(f"  成功率: {oks/max(total,1)*100:.1f}%")
    if stats_row[0]:
        print(f"  平均耗时: {stats_row[0]/1000:.1f}s  平均输入: {stats_row[1]:.0f} chars  平均输出: {stats_row[2]:.0f} chars")
        print(f"  平均压缩: {stats_row[3]:.0f} msgs/次  摘要变化: {stats_row[4]:.0f} chars/次")
    print()

    # ── 摘要趋势 ──
    if args.summary_trend or not args.last:
        trends = db.execute(
            f"SELECT session_name, MAX(summary_chars_after) as latest_size, "
            f"MAX(started_at) as last_at, COUNT(*) as rounds "
            f"{base} AND status='ok' "
            f"GROUP BY session_name ORDER BY last_at DESC LIMIT 10",
            params,
        ).fetchall()
        print("─ 摘要趋势 ─")
        for r in trends:
            last_dt = datetime.fromtimestamp(r['last_at'], tz=BJT).strftime('%m-%d %H:%M')
            print(f"  {r['session_name']}: {r['latest_size']} chars ({r['rounds']} rounds, last={last_dt})")
        print()

    # ── 最近 N 次 ──
    rows = db.execute(
        f"SELECT * {base} ORDER BY started_at DESC LIMIT ?",
        params + [args.last],
    ).fetchall()

    print(f"─ 最近 {len(rows)} 次 ─")
    status_icon = {'ok': '✅', 'fail': '❌', 'timeout': '⏱️', 'parse_none': '⚠️', 'no_signal': '—'}
    for r in rows:
        icon = status_icon.get(r['status'], '?')
        dt = datetime.fromtimestamp(r['started_at'], tz=BJT).strftime('%m-%d %H:%M')
        dur = f"{r['duration_ms']/1000:.1f}s" if r['duration_ms'] else '—'
        row = (f"  {icon} {dt}  {r['session_name']}  "
               f"{r['msg_count']}msgs  "
               f"{r['summary_chars_before']}→{r['summary_chars_after']}chars  "
               f"{dur}  {r['status']}")
        if r['error']:
            row += f"  [{r['error'][:60]}]"
        print(row)

    db.close()


if __name__ == '__main__':
    main()
