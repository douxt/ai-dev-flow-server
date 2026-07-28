#!/usr/bin/env python3
"""Face 表情全场景回归测试 — 覆盖所有历史踩坑场景。
用法: docker cp 到 napcat 容器后执行 python3 /tmp/test_face_regression.py
验证: 执行后检查 /tmp/silent_gate.log 和 /tmp/silent_prompt_dump.log
"""
import urllib.request, json, time, hmac, hashlib, sys, os

BOT_UUID = "dcbe70d9-af11-4624-908a-9928e4a08bdb"
SECRET = b"udimc123"
LANGBOT = "http://langbot:5300"
SESSION = "group_1104330614"

def send_sync(message_parts, timeout=90):
    body = json.dumps({
        "session_id": SESSION,
        "session_type": "group",
        "sender": {"id": "999888777", "name": "E2E测试员", "group_name": "测试专用"},
        "message": message_parts
    }).encode()
    ts = str(int(time.time()))
    sig = "sha256=" + hmac.new(SECRET, ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(f"{LANGBOT}/bots/{BOT_UUID}/sync",
        data=body, headers={"Content-Type":"application/json","X-LB-Timestamp":ts,"X-LB-Signature":sig}, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        d = json.loads(resp.read())
        return d
    except Exception as e:
        return {"error": str(e)}

def extract_text(msg):
    """从 /sync 响应中提取所有 Plain text"""
    parts = msg.get("data", {}).get("message", [])
    return "".join(p.get("text","") for p in parts if p.get("type")=="Plain")

passed = 0
failed = 0
results = []

def check(name, condition, detail=""):
    global passed, failed
    tag = "✅" if condition else "❌"
    status = "PASS" if condition else "FAIL"
    results.append((tag, name, status, detail))
    if condition:
        passed += 1
    else:
        failed += 1
    print(f"{tag} {name}: {detail}")

# ============================================================
# 场景 1: 纯表情 @bot（无文字）— 历史最频繁的"没数据"场景
# ============================================================
print("=" * 60)
print("场景 1: 纯表情 @bot（无文字，依赖 _QQ_FACE_NAME 映射）")
print("=" * 60)
r = send_sync([
    {"type": "At", "target": "3228649756"},
    {"type": "Face", "face_id": 14, "face_name": ""}  # face_name 为空，依赖映射表
])
reply = extract_text(r)
check("HTTP 200", r.get("code") == 0, f"code={r.get('code')}")
check("LLM 回复非空", len(reply) > 5, reply[:80])
check("不含'没数据'", "没数据" not in reply and "没东西" not in reply, reply[:80])
check("含表情关键词", "惊讶" in reply or "表情" in reply or "QQ" in reply, reply[:80])
time.sleep(3)

# ============================================================
# 场景 2: 表情+文字 @bot（face_name 为空）
# ============================================================
print("\n" + "=" * 60)
print("场景 2: 表情+文字 @bot（face_name 为空）")
print("=" * 60)
r = send_sync([
    {"type": "At", "target": "3228649756"},
    {"type": "Face", "face_id": 178, "face_name": ""},
    {"type": "Plain", "text": " 看看这个"}
])
reply = extract_text(r)
check("HTTP 200", r.get("code") == 0)
check("不含'没数据'", "没数据" not in reply and "没东西" not in reply, reply[:80])
time.sleep(3)

# ============================================================
# 场景 3: 文字+表情 @bot（Face 在后面）
# ============================================================
print("\n" + "=" * 60)
print("场景 3: 文字+表情 @bot（Face 在后面）")
print("=" * 60)
r = send_sync([
    {"type": "At", "target": "3228649756"},
    {"type": "Plain", "text": "这个表情 "},
    {"type": "Face", "face_id": 0, "face_name": "微笑"}
])
reply = extract_text(r)
check("HTTP 200", r.get("code") == 0)
check("不含'没数据'", "没数据" not in reply and "没东西" not in reply, reply[:80])
time.sleep(3)

# ============================================================
# 场景 4: 多表情 @bot
# ============================================================
print("\n" + "=" * 60)
print("场景 4: 多表情 @bot")
print("=" * 60)
r = send_sync([
    {"type": "At", "target": "3228649756"},
    {"type": "Face", "face_id": 14, "face_name": ""},
    {"type": "Face", "face_id": 178, "face_name": ""},
    {"type": "Plain", "text": " 两个表情"}
])
reply = extract_text(r)
check("HTTP 200", r.get("code") == 0)
check("不含'没数据'", "没数据" not in reply and "没东西" not in reply, reply[:80])
time.sleep(3)

# ============================================================
# 场景 5: 纯文字 @bot（无表情）— 回归验证不会误注
# ============================================================
print("\n" + "=" * 60)
print("场景 5: 纯文字（无表情）— 回归")
print("=" * 60)
r = send_sync([
    {"type": "At", "target": "3228649756"},
    {"type": "Plain", "text": " 你好，现在几点了？"}
])
reply = extract_text(r)
check("HTTP 200", r.get("code") == 0)
check("正常回复", len(reply) > 5, reply[:80])
check("不误提表情", "表情" not in reply or "QQ表情" not in reply, reply[:80])
time.sleep(2)

# ============================================================
# 场景 6: 纯表情无 @ — 验证 gate miss 路径也提取 Face
# ============================================================
print("\n" + "=" * 60)
print("场景 6: 纯表情无 @（gate miss 路径）")
print("=" * 60)
r = send_sync([
    {"type": "Face", "face_id": 3, "face_name": ""},
    {"type": "Plain", "text": " 发呆测试"}
])
check("HTTP 200", r.get("code") == 0)
time.sleep(2)

# ============================================================
print(f"\n{'='*60}")
print(f"结果: {passed}/{passed+failed} 通过")
print(f"{'='*60}")
for tag, name, status, detail in results:
    print(f"  {tag} [{status}] {name}: {detail}")
sys.exit(0 if failed == 0 else 1)
