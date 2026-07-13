#!/usr/bin/env python3
"""冒烟测试 — 部署后快速验证核心链路连通性。
用法: scp 到 napcat 容器后执行 python3 /tmp/test_smoke.py
返回: 全部通过 exit(0)，任一核心服务失败 exit(1)
"""
import urllib.request, json, time, hmac, hashlib, sys, os

BOT_UUID = "dcbe70d9-af11-4624-908a-9928e4a08bdb"
SECRET = b"udimc123"
TIMEOUT = 15
NAPCAT = "http://localhost:3000"
LANGBOT = "http://langbot:5300"
RELAY = "http://localhost:8888"

results = {}

def check(name, fn):
    try:
        fn()
        results[name] = (True, "")
    except Exception as e:
        results[name] = (False, str(e)[:120])

def check_napcat():
    resp = urllib.request.urlopen(f"{NAPCAT}/get_status?access_token=udimc123", timeout=5)
    d = json.loads(resp.read())
    assert d.get("data", {}).get("online") is True, "napcat not online"

def check_langbot():
    body = json.dumps({"session_id":"000","session_type":"person","sender":{"id":"0","name":"smoke"},"message":[{"type":"Plain","text":"ping"}]}).encode()
    ts = str(int(time.time()))
    sig = "sha256=" + hmac.new(SECRET, ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(f"{LANGBOT}/bots/{BOT_UUID}/sync",
        data=body, headers={"Content-Type":"application/json","X-LB-Timestamp":ts,"X-LB-Signature":sig}, method="POST")
    resp = urllib.request.urlopen(req, timeout=TIMEOUT)
    d = json.loads(resp.read())
    assert d.get("code") == 0, f"langbot /sync failed: {d.get('msg','?')}"

def check_relay():
    body = json.dumps({"session_id":"smoke","message":[{"type":"Plain","text":"ping"}],"is_final":True}).encode()
    req = urllib.request.Request(RELAY, data=body, headers={"Content-Type":"application/json"}, method="POST")
    resp = urllib.request.urlopen(req, timeout=5)
    assert resp.status == 200, f"relay returned {resp.status}"

def check_plugin():
    # 直接读插件 init log，不依赖 docker exec（napcat 容器内无法执行 docker）
    pass

if __name__ == "__main__":
    check("napcat", check_napcat)
    check("langbot-sync", check_langbot)
    check("relay", check_relay)

    all_ok = True
    for name, (ok_val, err) in results.items():
        tag = "[OK]" if ok_val else "[FAIL]"
        print(f"  {tag} {name}")
        if err:
            print(f"       {err}")
        if not ok_val and name != "relay":
            all_ok = False

    # relay 单独处理：失败仅告警不阻断
    if not results.get("relay", (True, ""))[0]:
        print("  [WARN] relay down (non-critical)")

    if all_ok:
        print("SMOKE: ALL OK")
        sys.exit(0)
    else:
        print("SMOKE: FAIL")
        sys.exit(1)
