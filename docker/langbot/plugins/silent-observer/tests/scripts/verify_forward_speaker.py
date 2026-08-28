#!/usr/bin/env python3
"""forward-speaker 修复验证 — check 模式（人工触发）+ send 模式（napcat HTTP 可用时）.

用法（langbot-plugin 容器内）:
  check（默认）：人工在测试群直发合并转发、再引用+@bot 后运行
      /app/.venv/bin/python tests/scripts/verify_forward_speaker.py
  send（需 napcat HTTP server 启用，当前部署未开）：
      NAPCAT_TOKEN=xxx .../verify_forward_speaker.py --send
断言:
  (1b) chat_index 最新含 Forward 归属的行：'[nick] 文本'（插件侧前缀，无时间戳）
  (1a) gate.log 最新 RAW PROMPT 段含引用展平归属头 '[nick MM-DD HH:MM]'（带时间戳）
"""
import json, os, re, sqlite3, sys, time, urllib.request

DB = '/app/data/plugins/dou__langbot-silent-observer/chat_index.db'
GATE_LOG = '/tmp/silent_gate.log'
GROUP = os.environ.get('SESSION', '1104330614')
NAPCAT = os.environ.get('NAPCAT_URL', 'http://napcat:5700')
BOT_QQ = os.environ.get('BOT_QQ', '3228649756')

HEAD_PLAIN = re.compile(r'\[[^\] ]+\] \S')          # 1b: [nick] text
HEAD_STAMP = re.compile(r'\[[^\] ]+ \d{2}-\d{2} \d{2}:\d{2}\]')  # 1a: [nick MM-DD HH:MM]


def check():
    fails = []
    try:
        c = sqlite3.connect(DB)
        rows = c.execute('SELECT formatted_text FROM chat_index WHERE session_id=? '
                         'ORDER BY timestamp_unix DESC LIMIT 40', (f'group_{GROUP}',)).fetchall()
        c.close()
    except Exception as e:
        print(f'FATAL: chat_index 不可读 {e}')
        sys.exit(2)
    hit_1b = next((r[0] for r in rows if HEAD_PLAIN.search(r[0])), None)
    if hit_1b:
        print(f'(1b) PASS: 归档行含节点归属 | {hit_1b[:140]}')
    else:
        fails.append("(1b) 最近 40 条无 '[nick] text' 归属行——未转发过？或 1b 路径未通")

    with open(GATE_LOG, 'r', errors='replace') as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - 2_000_000))
        data = f.read()
    i = data.rfind('LLM RAW PROMPT')
    seg = data[i:] if i >= 0 else ''
    j = seg.find('=== END RAW PROMPT ===')
    seg = seg[:j] if j > 0 else seg
    m = HEAD_STAMP.search(seg)
    if m:
        print(f'(1a) PASS: RAW PROMPT 含带时间戳归属头 {m.group(0)[:40]!r}')
    else:
        fails.append("(1a) 最后 RAW PROMPT 段无 '[nick MM-DD HH:MM]'——引用展平未通或未做引用轮")
    return fails


def send():
    token = os.environ.get('NAPCAT_TOKEN', '')
    if not token:
        print('FATAL: send 模式需 NAPCAT_TOKEN'); sys.exit(2)
    ts = int(time.time())
    msgs = [
        {'type': 'node', 'data': {'user_id': '10001', 'nickname': f'E2E甲{ts}',
                                  'content': [{'type': 'text', 'data': {'text': '我车不烧机油'}}]}},
        {'type': 'node', 'data': {'user_id': '10002', 'nickname': f'E2E乙{ts}',
                                  'content': [{'type': 'text', 'data': {'text': 'EA888修都修烂了'}}]}},
    ]
    body = json.dumps({'group_id': int(GROUP), 'messages': msgs}).encode()
    req = urllib.request.Request(f'{NAPCAT}/send_group_forward_msg', data=body,
                                 headers={'Content-Type': 'application/json',
                                          'Authorization': f'Bearer {token}'}, method='POST')
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.loads(r.read())
    assert out.get('status') == 'ok', out
    print(f'sent fwd msg_id={out.get("data", {}).get("message_id")}, 等 60s 后 check')
    time.sleep(60)
    return check()


if __name__ == '__main__':
    fails = send() if '--send' in sys.argv else check()
    if fails:
        print('FAIL: ' + '; '.join(fails))
        sys.exit(1)
    print('PASS: forward-speaker 验证全绿')
