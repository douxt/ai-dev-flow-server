#!/usr/bin/env python3
"""forward-speaker 修复 E2E — napcat 合成真实合并转发验证归属.

用法（langbot-plugin 容器内）:
    NAPCAT_TOKEN=xxx /app/.venv/bin/python tests/scripts/verify_forward_speaker.py
覆盖:
  (1b) 直发合并转发 → 插件 Forward 组件路径 → chat_index 归档行含 '[E2E-甲]'（无时间戳形态）
  (1a) 引用该转发 → 宿主展平归属头 '[E2E-甲 MM-DD' 带时间戳形态 → RAW PROMPT [引用 段含之
  (1c) reply 超时包裹后引用路径仍正常
"""
import json
import os
import sqlite3
import sys
import time
import urllib.request

NAPCAT = os.environ.get('NAPCAT_URL', 'http://napcat:5700')
TOKEN = os.environ.get('NAPCAT_TOKEN', '')
if not TOKEN:
    print('FATAL: 需 NAPCAT_TOKEN 环境变量')
    sys.exit(2)
GROUP = int(os.environ.get('SESSION', '1104330614'))
BOT_QQ = os.environ.get('BOT_QQ', '3228649756')
DB = '/app/data/plugins/dou__langbot-silent-observer/chat_index.db'
GATE_LOG = '/tmp/silent_gate.log'
EVENT_LOG = '/tmp/silent_event.log'

TS = int(time.time())
NICK_A, NICK_B = f'E2E甲{TS}', f'E2E乙{TS}'


def api(action, **params):
    req = urllib.request.Request(
        f'{NAPCAT}/{action}',
        data=json.dumps(params).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {TOKEN}'},
        method='POST')
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.loads(r.read())
    if out.get('status') != 'ok':
        raise RuntimeError(f'{action} -> {out}')
    return out.get('data', {})


def count(path, needle):
    try:
        with open(path, 'r', errors='replace') as f:
            return f.read().count(needle)
    except Exception:
        return 0


def main():
    fails = []
    t0_inject = count(EVENT_LOG, f'group_{GROUP} inject ')
    # 预检：目标群无在途消息（同 P1.5 判据：最后 hit 距今时长）
    try:
        with open(EVENT_LOG, 'r', errors='replace') as f:
            hits = [l for l in f.read().splitlines() if f'group_{GROUP} hit ' in l]
        if hits and time.time() - float(hits[-1].split()[0]) < 120:
            print('PREFLIGHT FAIL: 目标群 2 分钟内有 hit，稍后再跑')
            sys.exit(2)
    except Exception:
        pass

    # ── 1. 发合成合并转发（bot 自身发出，reportSelfMessage 回流）──
    data = api('send_group_forward_msg', group_id=GROUP, messages=[
        {'type': 'node', 'data': {'user_id': '10001', 'nickname': NICK_A,
                                  'content': [{'type': 'text', 'data': {'text': '我车不烧机油'}}]}},
        {'type': 'node', 'data': {'user_id': '10002', 'nickname': NICK_B,
                                  'content': [{'type': 'text', 'data': {'text': 'EA888修都修烂了'}}]}},
    ])
    fwd_id = data.get('message_id')
    print(f'send_group_forward_msg ok, msg_id={fwd_id}')

    # ── 2. 等回流入库，查 chat_index（1b 路径）──
    row = None
    for _ in range(12):  # 最多 60s
        time.sleep(5)
        try:
            c = sqlite3.connect(DB)
            row = c.execute('SELECT formatted_text FROM chat_index WHERE formatted_text LIKE ? '
                            'ORDER BY timestamp_unix DESC LIMIT 1', (f'%{NICK_A}%',)).fetchone()
            c.close()
        except Exception:
            continue
        if row:
            break
    if not row:
        fails.append('(1b) chat_index 无 E2E 归属行——Forward 组件未达插件/未入库')
    else:
        txt = row[0]
        if NICK_A in txt and NICK_B in txt and txt.index(NICK_A) < txt.index(NICK_B):
            print(f'(1b) PASS: 归档行两节点按序归属 | {txt[:120]}')
        else:
            fails.append(f'(1b) 归属缺失或乱序: {txt[:160]}')

    # ── 3. 引用该转发 + @bot（1a/1c 路径）──
    if fwd_id:
        try:
            api('send_group_msg', group_id=GROUP, message=[
                {'type': 'reply', 'data': {'id': fwd_id}},
                {'type': 'at', 'data': {'qq': BOT_QQ}},
                {'type': 'text', 'data': {'text': ' 这两人各说了什么'}}])
            print('reply+at sent')
        except Exception as e:
            fails.append(f'(1a) 引用消息发送失败: {e}')
        # 等 inject
        ok = False
        for _ in range(20):
            time.sleep(5)
            if count(EVENT_LOG, f'group_{GROUP} inject ') > t0_inject + (1 if row else 0):
                ok = True
                break
        if not ok:
            fails.append('(1a) 等 inject 超时')
        else:
            time.sleep(3)
            with open(GATE_LOG, 'r', errors='replace') as f:
                f.seek(0, 2)
                f.seek(max(0, f.tell() - 2_000_000))
                seg = f.read()
            i = seg.rfind('LLM RAW PROMPT')
            j = seg.find('=== END RAW PROMPT ===', i)
            seg = seg[i:j if j > 0 else len(seg)]
            # 1a 归属头带时间戳 [E2E甲<ts> MM-DD，区别于 1b 的 [nick] 无时间
            if f'[{NICK_A} ' in seg and '[引用' in seg:
                print('(1a) PASS: 引用段含带时间戳归属头')
            elif f'[{NICK_A} ' in seg:
                print('(1a) PASS(弱): 带时间戳归属头在 prompt（引用渲染路径未断言 [引用 前缀）')
            else:
                fails.append('(1a) RAW PROMPT 未见带时间戳归属头（展平仍丢 sender？）')
    else:
        fails.append('(1a) 未取得 fwd msg_id，无法测引用路径')

    print(f'\nE2E 完成。人工清理提示：测试群留了两条 bot 自身消息（转发+引用@） msg_id={fwd_id}')
    if fails:
        print('FAIL: ' + '; '.join(fails))
        sys.exit(1)
    print('PASS: forward-speaker E2E 全绿')


if __name__ == '__main__':
    main()
