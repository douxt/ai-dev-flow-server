#!/usr/bin/env python3
"""P1 quick smoke test — 5 messages + check summary table."""
import urllib.request, json, time, hmac, hashlib, sys, os, sqlite3

BOT_UUID = os.environ.get("BOT_UUID", "dcbe70d9-af11-4624-908a-9928e4a08bdb")
SECRET = os.environ.get("SECRET", "udimc123").encode()
LANGBOT = os.environ.get("LANGBOT", "http://langbot:5300")
SESSION = os.environ.get("SESSION", "group_1104330614")
SESSION_NAME = f"group_{SESSION}"
BOT_QQ = "3228649756"
SUMMARY_DB = "/app/data/plugins/dou__langbot-silent-observer/chat_index.db"


def send_sync(text):
    body = json.dumps({
        "session_id": SESSION, "session_type": "group",
        "sender": {"id": "smoke", "name": "SmokeTest", "group_name": "测试群"},
        "message": [
            {"type": "Plain", "text": text},
            {"type": "At", "target": BOT_QQ},
        ],
    }).encode()
    ts = str(int(time.time()))
    sig = "sha256=" + hmac.new(SECRET, ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        f"{LANGBOT}/bots/{BOT_UUID}/sync",
        data=body,
        headers={"Content-Type": "application/json", "X-LB-Timestamp": ts, "X-LB-Signature": sig},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


# Send 5 messages
for i in range(5):
    resp = send_sync(f"P1快速测试第{i}条。限价9382元。长一点的内容" + "测试" * 15)
    err = resp.get("error", "")
    if err:
        print(f"msg {i} error: {err}")
    else:
        print(f"msg {i} ok")
    time.sleep(3)

# Wait for background compression
print("waiting for compression...")
for i in range(30):
    try:
        db = sqlite3.connect(SUMMARY_DB, timeout=5)
        row = db.execute("SELECT * FROM summary WHERE session_name = ?", (SESSION_NAME,)).fetchone()
        db.close()
        if row and (row[6] or 0) > 0:
            print(f"FOUND summary: message_count={row[6]} topics={row[1][:50] if row[1] else ''} facts={row[2][:80] if row[2] else ''}")
            sys.exit(0)
    except Exception as e:
        print(f"  poll {i}: {e}")
    time.sleep(2)

print("TIMEOUT: summary not created after 60s")
sys.exit(1)
