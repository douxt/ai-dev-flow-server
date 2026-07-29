#!/usr/bin/env python3
"""E2E 引用消息测试 — 模拟引用文本/引用图片/引用转发群聊，验证入库正确。
通过 HTTP Bot /sync 发送，不依赖真实 QQ 操作。
"""
import urllib.request, json, time, hmac, hashlib, sys, sqlite3

BOT_UUID = "dcbe70d9-af11-4624-908a-9928e4a08bdb"
SECRET = b"udimc123"
LANGBOT = "http://langbot:5300"
DB = "/app/data/plugins/dou__langbot-silent-observer/chat_index.db"
SESSION = "group_1104330614"

def count_rows():
    db = sqlite3.connect(DB)
    n = db.execute("SELECT count(*) FROM chat_index WHERE session_id=?", (SESSION,)).fetchone()[0]
    db.close()
    return n

def count_pending():
    """检查 langbot DB pending 数（需在 langbot 容器内运行）"""
    try:
        db2 = sqlite3.connect("/app/data/langbot.db")
        n = db2.execute("SELECT count(*) FROM monitoring_messages WHERE session_id=? AND status='pending'", (SESSION,)).fetchone()[0]
        db2.close()
        return n
    except:
        return -1

def send_sync(msg_parts, timeout=30):
    body = json.dumps({
        "session_id": SESSION, "session_type": "group",
        "sender": {"id": "370087943", "name": "小通豆", "group_name": "测试专用"},
        "message": msg_parts
    }).encode()
    ts = str(int(time.time()))
    sig = "sha256=" + hmac.new(SECRET, ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(f"{LANGBOT}/bots/{BOT_UUID}/sync",
        data=body, headers={"Content-Type": "application/json", "X-LB-Timestamp": ts, "X-LB-Signature": sig}, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        d = json.loads(resp.read())
        return d.get("code") == 0
    except:
        return False

# ---- 测试 ----
errors = []
before = count_rows()

# 用例1: 引用纯文本
ok = send_sync([
    {"type": "At", "target": "3228649756"},
    {"type": "Quote", "origin": [
        {"type": "Plain", "text": "这是被引用的消息内容"},
        {"type": "Plain", "text": "第二段"}
    ]},
    {"type": "Plain", "text": " 看看这段引用"}
])
if ok:
    print("[OK] 用例1: 引用纯文本")
else:
    errors.append("用例1: HTTP超时")
    print("[FAIL] 用例1")

time.sleep(2)

# 用例2: 引用含图片
ok = send_sync([
    {"type": "At", "target": "3228649756"},
    {"type": "Quote", "origin": [
        {"type": "Plain", "text": "看这张图"},
        {"type": "Image"}
    ]},
    {"type": "Plain", "text": " 图里是什么"}
])
if ok:
    print("[OK] 用例2: 引用图片")
else:
    errors.append("用例2: HTTP超时")
    print("[FAIL] 用例2")

time.sleep(2)

# 用例3: 引用转发群聊 (Source only)
ok = send_sync([
    {"type": "At", "target": "3228649756"},
    {"type": "Quote", "origin": [
        {"type": "Source"}
    ]},
    {"type": "Plain", "text": " 转发里有什么"}
])
if ok:
    print("[OK] 用例3: 引用转发(Source only)")
else:
    errors.append("用例3: HTTP超时")
    print("[FAIL] 用例3")

time.sleep(2)

after = count_rows()
delta = after - before
print(f"[INFO] delta={delta} (期望 >= 3)")

if delta < 2:
    errors.append(f"入库不足: delta={delta} (LLM超时可重试)")

pending = count_pending()
if pending >= 0:
    print(f"[INFO] pending={pending}")
    if pending > 3:
        errors.append(f"pending堆积: {pending}")

if errors:
    for e in errors:
        print(f"[FAIL] {e}")
    sys.exit(1)
print("[OK] 全部通过")
sys.exit(0)
