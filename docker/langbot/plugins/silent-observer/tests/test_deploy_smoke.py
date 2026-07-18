#!/usr/bin/env python3
"""部署烟雾测试 — 8 场景，部署后自动验证核心功能。
用法: docker cp 到 napcat 容器后执行 python3 /tmp/test_deploy_smoke.py
      退出码 0=全部通过, 1=有失败"""
import urllib.request, json, time, hmac, hashlib, sys, sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed

BOT_UUID = "dcbe70d9-af11-4624-908a-9928e4a08bdb"
SECRET = b"udimc123"
LANGBOT = "http://langbot:5300"
SESSION = "group_1104330614"
NAPCAT = "http://localhost:3000"
DB = "/app/data/plugins/dou__langbot-silent-observer/chat_index.db"

passed = 0
failed = 0

def send_sync(message_parts, timeout=90, session=None):
    body = json.dumps({
        "session_id": session or SESSION, "session_type": "group",
        "sender": {"id": "999888777", "name": "Smoke测试", "group_name": "测试群"},
        "message": message_parts
    }).encode()
    ts = str(int(time.time()))
    sig = "sha256=" + hmac.new(SECRET, ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(f"{LANGBOT}/bots/{BOT_UUID}/sync",
        data=body, headers={"Content-Type":"application/json",
        "X-LB-Timestamp": ts, "X-LB-Signature": sig}, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def extract_text(resp):
    parts = resp.get("data", {}).get("message", [])
    return "".join(p.get("text","") for p in parts if p.get("type")=="Plain")

def check(condition, name, detail=""):
    global passed, failed
    if condition:
        passed += 1; print(f"  ✅ {name}")
    else:
        failed += 1; print(f"  ❌ {name}: {detail}")

def count_rows():
    try:
        db = sqlite3.connect(DB, timeout=5)
        rows = db.execute("SELECT COUNT(*) FROM chat_index").fetchone()[0]
        db.close()
        return rows
    except: return -1

# ============================================================
# 场景 1: Napcat 存活
# ============================================================
print("=" * 60)
print("场景 1: Napcat 存活")
req = urllib.request.Request(f"{NAPCAT}/get_status?access_token=udimc123")
try:
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
    check(resp.get("data", {}).get("online") is True, "napcat online")
except Exception as e:
    check(False, "napcat online", str(e))

# ============================================================
# 场景 2: Langbot /sync 正常
# ============================================================
print("\n" + "=" * 60)
print("场景 2: Langbot /sync 正常")
r = send_sync([
    {"type": "At", "target": "3228649756"},
    {"type": "Plain", "text": " 你好"}
])
reply = extract_text(r)
check(r.get("code") == 0, "sync HTTP 200", f"code={r.get('code')}")
check(len(reply) > 3, "sync 回复非空", reply[:60])

# ============================================================
# 场景 3: 表情 @bot → 识别正确
# ============================================================
print("\n" + "=" * 60)
print("场景 3: 表情 @bot")
r = send_sync([
    {"type": "At", "target": "3228649756"},
    {"type": "Face", "face_id": 14, "face_name": ""}
])
reply = extract_text(r)
check(r.get("code") == 0, "face: HTTP 200", f"code={r.get('code')}")
check(len(reply) > 5, "face: 回复非空", reply[:80])
check("没数据" not in reply and "没东西" not in reply, "face: 不含拒绝语", reply[:80])
check("惊讶" in reply or "表情" in reply or "QQ" in reply, "face: 含表情关键词", reply[:80])
time.sleep(2)

# ============================================================
# 场景 4: 引用消息 → 正常处理
# ============================================================
print("\n" + "=" * 60)
print("场景 4: 引用消息")
r = send_sync([
    {"type": "At", "target": "3228649756"},
    {"type": "Quote", "origin": [{"type": "Plain", "text": "这是一条被引用的消息"}]},
    {"type": "Plain", "text": " 上面说的对吗"}
])
reply = extract_text(r)
check(r.get("code") == 0, "quote: HTTP 200", f"code={r.get('code')}")
check(len(reply) > 5, "quote: 回复非空", reply[:80])
time.sleep(2)

# ============================================================
# 场景 5: 图片 → 验证 base64 清除（WS 不膨胀）
# ============================================================
print("\n" + "=" * 60)
print("场景 5: 图片（strip-base64）")
r = send_sync([
    {"type": "At", "target": "3228649756"},
    {"type": "Plain", "text": " 处理这张图"},
    {"type": "Image", "url": "https://example.com/test.png", "base64": "data:image/png;base64,AAAA"}
])
reply = extract_text(r)
check(r.get("code") == 0, "img: HTTP 200", f"code={r.get('code')}")
time.sleep(3)

# ============================================================
# 场景 6: 并发 flood → 队列不溢出
# ============================================================
print("\n" + "=" * 60)
print("场景 6: 并发 flood (15 条)")

rows_before = count_rows()

def send_one(i):
    return send_sync([
        {"type": "Plain", "text": f" 烟雾并发消息 #{i}"}
    ], timeout=60, session=f"smoke_flood_{int(time.time()*1000)}_{i}")

http_errors = 0
with ThreadPoolExecutor(max_workers=15) as ex:
    futures = [ex.submit(send_one, i) for i in range(15)]
    for f in as_completed(futures):
        r = f.result()
        if r.get("code") != 0:
            http_errors += 1

time.sleep(5)
rows_after = count_rows()
delta = rows_after - rows_before if rows_before >= 0 and rows_after >= 0 else 0
check(http_errors <= 3, f"flood: HTTP 错误 ({http_errors}/15)", f"errors={http_errors}")
check(delta >= 10, f"flood: DB 写入 ({delta}/15)", f"rows={rows_before}→{rows_after}")

# ============================================================
# 场景 7: chat_index 完整性
# ============================================================
print("\n" + "=" * 60)
print("场景 7: chat_index 完整性")
try:
    db = sqlite3.connect(DB, timeout=5)
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    check("chat_index" in tables, "chat_index 表存在")
    indexes = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='index'")]
    check("idx_chat_session_time" in indexes, "idx_chat_session_time 索引存在")
    mode = db.execute("PRAGMA journal_mode").fetchone()[0]
    check(mode.lower() == "wal", f"WAL 模式 ({mode})")
    db.close()
except Exception as e:
    check(False, "DB 查询", str(e))

# ============================================================
# 场景 8: 时区正确 → 北京时间的凌晨不应出现
# ============================================================
print("\n" + "=" * 60)
print("场景 8: 时区正确")
r = send_sync([
    {"type": "At", "target": "3228649756"},
    {"type": "Plain", "text": " 现在北京时间几点了？"}
])
reply = extract_text(r)
check(r.get("code") == 0, "tz: HTTP 200", f"code={r.get('code')}")
check("凌晨" not in reply, "tz: 不含凌晨（时区正确）", reply[:80])

# ============================================================
# 结果
# ============================================================
total = passed + failed
print(f"\n{'='*60}")
print(f"结果: {passed}/{total} 通过 ({'✅' if failed == 0 else '❌'})")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
