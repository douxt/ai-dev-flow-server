#!/usr/bin/env python3
"""E2E 回归测试 — 验证 /sync 模式不产生 KB flood。
用法: scp 到 napcat 容器后执行 python3 /tmp/test_e2e_sync.py
"""
import urllib.request, json, time, hmac, hashlib, sys, sqlite3

BOT_UUID = "dcbe70d9-af11-4624-908a-9928e4a08bdb"
SECRET = b"udimc123"
LANGBOT = "http://langbot:5300"
DB = "/app/data/plugins/dou__langbot-silent-observer/chat_index.db"
TIMEOUT = 60
RETRY_WAIT = 30
SESSION = "group_1104330614"

def count_bot_replies():
    try:
        db = sqlite3.connect(DB)
        n = db.execute("SELECT count(*) FROM chat_index WHERE session_id=? AND formatted_text LIKE '%机器豆(BOT)%'", (SESSION,)).fetchone()[0]
        db.close()
        return n
    except Exception as e:
        print(f"[FAIL] cannot read chat_index: {e}")
        sys.exit(1)

def send_sync():
    body = json.dumps({
        "session_id": SESSION,
        "session_type": "group",
        "sender": {"id": "999888777", "name": "E2E测试员", "group_name": "测试专用"},
        "message": [
            {"type": "At", "target": "3228649756"},
            {"type": "Plain", "text": " 你好，确认一下现在是什么时间？"}
        ]
    }).encode()
    ts = str(int(time.time()))
    sig = "sha256=" + hmac.new(SECRET, ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(f"{LANGBOT}/bots/{BOT_UUID}/sync",
        data=body, headers={"Content-Type":"application/json","X-LB-Timestamp":ts,"X-LB-Signature":sig}, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        d = json.loads(resp.read())
        return d.get("message", [])
    except Exception as e:
        return None

def extract_text(msg_parts):
    return "".join(p.get("text","") for p in msg_parts if p.get("type")=="Plain")

if __name__ == "__main__":
    before = count_bot_replies()
    print(f"[1] before count: {before}")

    # 发送（含 1 次重试）
    msg = send_sync()
    if msg is None:
        print("[2] first attempt timeout, retrying...")
        time.sleep(RETRY_WAIT)
        msg = send_sync()
    if msg is None:
        print("[FAIL] /sync failed after retry")
        sys.exit(1)

    reply = extract_text(msg)
    print(f"[2] reply: {reply[:150]}")

    time.sleep(2)  # 等异步写入
    after = count_bot_replies()
    delta = after - before
    print(f"[3] after count: {after} (delta={delta})")

    # 断言
    errors = []
    if delta == 0:
        errors.append("no new bot reply saved")
    if delta > 3:
        errors.append(f"flood detected: {delta} new entries (expected 1)")
    if "凌晨" in reply:
        errors.append("timezone hallucination: reply contains 凌晨")

    if errors:
        for e in errors:
            print(f"[FAIL] {e}")
        sys.exit(1)
    print(f"[OK] delta={delta}, no tz hallucination")
    sys.exit(0)
