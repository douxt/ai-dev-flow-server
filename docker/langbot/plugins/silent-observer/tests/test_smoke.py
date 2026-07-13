import urllib.request, json, time, hmac, hashlib, sys, ssl

BOT_UUID = 'dcbe70d9-af11-4624-908a-9928e4a08bdb'
SECRET = b'udimc123'
NAPCAT = 'http://localhost:3000'
LANGBOT = 'http://langbot:5300'

def ok(s): print(f'  [OK] {s}')
def fail(s, e=None): print(f'  [FAIL] {s}' + (f': {e}' if e else '')); return False
def warn(s, e=None): print(f'  [WARN] {s}' + (f': {e}' if e else '')); return False

# 1. napcat
try:
    resp = urllib.request.urlopen(f'{NAPCAT}/get_status?access_token=udimc123', timeout=5)
    d = json.loads(resp.read())
    assert d.get('data',{}).get('online'), 'not online'
    ok('napcat')
except Exception as e:
    fail('napcat', e)

# 2. langbot /sync (use unique session to avoid 409)
try:
    uid = str(int(time.time()))[-6:]
    body = json.dumps({'session_id':uid,'session_type':'person','sender':{'id':'0','name':'smoke'},'message':[{'type':'Plain','text':'hi'}]}).encode()
    ts = str(int(time.time()))
    sig = 'sha256=' + hmac.new(SECRET, ts.encode()+b'.'+body, hashlib.sha256).hexdigest()
    ctx = ssl.create_default_context()
    req = urllib.request.Request(f'{LANGBOT}/bots/{BOT_UUID}/sync',
        data=body, headers={'Content-Type':'application/json','X-LB-Timestamp':ts,'X-LB-Signature':sig}, method='POST')
    resp = urllib.request.urlopen(req, timeout=30, context=ctx)
    d = json.loads(resp.read())
    assert d.get('code') == 0, f'code={d.get("code")} msg={d.get("msg","")}'
    ok('langbot-sync')
except Exception as e:
    fail('langbot-sync', e)

# 3. relay (non-critical, just warn)
try:
    body = json.dumps({'session_id':'smoke','message':[{'type':'Plain','text':'ping'}],'is_final':True}).encode()
    req = urllib.request.Request('http://localhost:8888', data=body, headers={'Content-Type':'application/json'}, method='POST')
    resp = urllib.request.urlopen(req, timeout=5)
    assert resp.status == 200, f'status={resp.status}'
    ok('relay')
except Exception as e:
    warn('relay', e)

print('SMOKE: DONE' if True else '')
