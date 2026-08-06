#!/usr/bin/env python3
"""验证 QQ 表情修复 — /sync 发送 Face 组件 → 检查 gate log + prompt dump.
用法: python3 verify_face.py [--json]
退出码: 0=表情正确处理, 1=仍有 Unknown Face
"""
import sys, os, time, json, urllib.request, urllib.error, hmac, hashlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

BOT_UUID = os.environ.get("BOT_UUID", "dcbe70d9-af11-4624-908a-9928e4a08bdb")
SECRET = os.environ.get("SECRET", "udimc123").encode()
LANGBOT = os.environ.get("LANGBOT", "http://langbot:5300")
BOT_QQ = "3228649756"
GATE_LOG = "/tmp/silent_gate.log"

SESSION_ID = f"face_test_{int(time.time())}"
passed = 0
failed = 0


def check(cond, name, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name}: {detail}")
    return cond


def send_sync(message_parts, timeout=30):
    body = json.dumps({
        "session_id": SESSION_ID, "session_type": "group",
        "sender": {"id": "facetest", "name": "FaceTest", "group_name": "表情测试群"},
        "message": message_parts,
    }).encode()
    ts = str(int(time.time()))
    sig = "sha256=" + hmac.new(SECRET, ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        f"{LANGBOT}/bots/{BOT_UUID}/sync",
        data=body, headers={"Content-Type": "application/json", "X-LB-Timestamp": ts, "X-LB-Signature": sig},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def get_gate_lines_after(line_count):
    """返回 gate log 第 line_count 行之后的新增行."""
    with open(GATE_LOG, "r") as f:
        lines = f.readlines()
    return lines[line_count:]


def main():
    global passed, failed
    print(f"=== QQ 表情修复验证 [session={SESSION_ID}] ===")

    # 记录当前行数
    with open(GATE_LOG, "r") as f:
        baseline = len(f.readlines())

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    # 测试 1: 正常 Face 组件（含 face_id + face_name）
    print("\n[1] 正常 Face 组件 (face_id=14 face_name=惊讶)")
    resp = send_sync([
        {"type": "Face", "face_id": 14, "face_name": "惊讶"},
        {"type": "Plain", "text": "测试表情"},
        {"type": "At", "target": BOT_QQ},
    ])
    time.sleep(5)

    new_lines = get_gate_lines_after(baseline)
    new_text = "".join(new_lines)

    has_unknown = "Unknown component type: Face" in new_text
    has_qq_face = "[QQ表情:惊讶]" in new_text or "[QQ表情:14]" in new_text or "face_text=惊讶" in new_text or "QQ表情" in new_text

    check(not has_unknown, "no-unknown-face", "Face 组件未被降级为 Unknown")
    check(has_qq_face, "qq-face-text", f"gate log 含表情文本: {'found' if has_qq_face else 'NOT FOUND'}")

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    # 测试 2: 检查 prompt dump 的 [6] face 段
    print("\n[2] Prompt dump [6] face 段")
    dump_file = "/tmp/silent_prompt_dump.log"
    try:
        with open(dump_file, "r") as f:
            dump_content = f.read()
    except FileNotFoundError:
        dump_content = ""

    # 找最新 dump
    idx = dump_content.rfind("=== PROMPT DUMP")
    last_dump = dump_content[idx:] if idx >= 0 else ""
    face_section = ""
    if "[6] face:" in last_dump:
        s6 = last_dump.split("[6] face:")[1]
        face_section = s6.split("\n")[0].strip()

    check("(无)" not in face_section if face_section else True,
          "prompt-face-section", f"face 段={face_section[:80] if face_section else '(empty)'}")

    # = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
    # 结果
    print(f"\n{'─' * 20}")
    print(f"结果: {passed} 通过, {failed} 失败")
    if "--json" in sys.argv:
        print(json.dumps({"passed": passed, "failed": failed}, ensure_ascii=False))
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
