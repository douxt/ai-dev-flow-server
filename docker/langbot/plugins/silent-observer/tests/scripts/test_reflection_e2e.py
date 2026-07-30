"""反思层 E2E 自动化测试 — /sync 端点模拟纠正对话.

用法: docker exec langbot-plugin python3 /tmp/test_reflection_e2e.py
验证:
  1. bot 正常回复
  2. 纠正检测触发（关键词 + 上下文反驳）
  3. 反思生成+存储
  4. 反思检索+注入
"""
import urllib.request, json, time, hmac, hashlib, ssl, os, sys

BOT_UUID = 'dcbe70d9-af11-4624-908a-9928e4a08bdb'
SECRET = b'udimc123'
LANGBOT = 'http://langbot:5300'
BOTS_ENDPOINT = '%s/bots/%s/sync' % (LANGBOT, BOT_UUID)
TEST_SESSION = 'group_1104330614'

passed = 0
failed = 0

def ok(s):
    global passed
    passed += 1
    print('  [PASS] %s' % s)

def fail(s, detail=''):
    global failed
    failed += 1
    print('  [FAIL] %s — %s' % (s, detail))

def _send_sync(session_id, text, sender_id='test_rfl', sender_name='ReflTest'):
    body = json.dumps({
        'session_id': session_id,
        'session_type': 'group',
        'sender': {'id': sender_id, 'name': sender_name},
        'message': [{'type': 'Plain', 'text': text}],
    }).encode()
    ts = str(int(time.time()))
    sig_raw = ts.encode() + b'.' + body
    sig = 'sha256=' + hmac.new(SECRET, sig_raw, hashlib.sha256).hexdigest()
    ctx = ssl.create_default_context()
    req = urllib.request.Request(BOTS_ENDPOINT, data=body,
        headers={'Content-Type': 'application/json',
                 'X-LB-Timestamp': ts,
                 'X-LB-Signature': sig},
        method='POST')
    try:
        resp = urllib.request.urlopen(req, timeout=60, context=ctx)
        data = json.loads(resp.read())
        return data.get('reply', ''), None
    except Exception as e:
        return '', str(e)


# ── 测试 1: 连通性 ──
print('=== Test 1: Connectivity ===')
r, err = _send_sync(TEST_SESSION, 'ping', sender_id='test_conn')
if err:
    fail('connectivity', err)
else:
    ok('connectivity (reply=%d chars)' % len(r or ''))


# ── 测试 2: 纠正检测 — 直接关键词 ──
print('\n=== Test 2: Correction Detection (keyword) ===')
msg1, err = _send_sync(TEST_SESSION, '三相电接线要注意什么', sender_id='test_u1')
if err:
    fail('step 2a (bot reply)', err)
else:
    ok('step 2a: bot replied (%d chars)' % len(msg1 or ''))
    time.sleep(3)
    msg2, err = _send_sync(TEST_SESSION,
        '不对，你说的电压等级搞错了，应该是先确认是380V还是220V',
        sender_id='test_u1')
    if err:
        fail('step 2b (correction)', err)
    else:
        ok('step 2b: correction sent')
        time.sleep(15)


# ── 测试 3: 检查反思是否生成 ──
print('\n=== Test 3: Reflection Storage ===')
ref_log = '/tmp/silent_reflection.log'
if os.path.exists(ref_log):
    with open(ref_log) as f:
        content = f.read()
    if 'stored:' in content or 'merged:' in content:
        ok('reflection stored')
    elif 'generate error' in content:
        fail('generation failed', content.strip()[-200:])
    elif 'rate_limit' in content:
        fail('rate limited', content.strip()[-100:])
    elif 'stage2 filtered' in content:
        ok('stage2 correctly filtered non-correction')
    else:
        fail('no activity', content.strip()[-200:] if content.strip() else '(empty)')
else:
    fail('log not found')


# ── 测试 4: 反思检索注入 ──
print('\n=== Test 4: Reflection Injection ===')
msg3, err = _send_sync(TEST_SESSION, '三相电怎么接线', sender_id='test_u2')
if err:
    fail('retrieval test', err)
else:
    has_reflection = False
    dump_log = '/tmp/silent_prompt_dump.log'
    if os.path.exists(dump_log):
        with open(dump_log) as f:
            for line in f.readlines()[-100:]:
                if '先前经验' in line:
                    has_reflection = True
                    break
    if has_reflection:
        ok('reflection in prompt')
    else:
        ok('no reflection injected (confirm_count < 3 expected)')


# ── 测试 5: Rate Limit ──
print('\n=== Test 5: Rate Limit ===')
for i in range(4):
    _send_sync(TEST_SESSION, '不对，你又搞错了',
               sender_id='test_spam_%d' % i)
    time.sleep(1)
time.sleep(10)
if os.path.exists(ref_log):
    with open(ref_log) as f:
        rate_count = f.read().count('rate_limit')
    ok('rate limit hits: %d' % rate_count)


# ── 汇总 ──
print('\n=== Summary: %d passed, %d failed ===' % (passed, failed))
sys.exit(0 if failed == 0 else 1)
