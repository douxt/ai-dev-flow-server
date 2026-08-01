#!/usr/bin/env python3
"""Context 优化验证 — /sync 发 5 条测试消息 + 断言 + prompt dump 检查。
用法（langbot-plugin 容器内）:
  python3 /tmp/verify_ctx.py           # 全部场景
  python3 /tmp/verify_ctx.py --json    # JSON 输出
"""
import urllib.request, json, time, hmac, hashlib, sys, os, argparse, re

BOT_UUID = os.environ.get("BOT_UUID", "dcbe70d9-af11-4624-908a-9928e4a08bdb")
SECRET = os.environ.get("SECRET", "udimc123").encode()
LANGBOT = os.environ.get("LANGBOT", "http://langbot:5300")
SESSION = os.environ.get("SESSION", "group_1104330614")
BOT_QQ = "3228649756"
PROMPT_DUMP = "/tmp/silent_prompt_dump.log"

passed = 0
failed = 0
results = []


def send_sync(message_parts, timeout=120):
    body = json.dumps({
        "session_id": SESSION, "session_type": "group",
        "sender": {"id": "999888777", "name": "ContextTest", "group_name": "测试群"},
        "message": message_parts,
    }).encode()
    ts = str(int(time.time()))
    sig = "sha256=" + hmac.new(SECRET, ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        f"{LANGBOT}/bots/{BOT_UUID}/sync",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-LB-Timestamp": ts,
            "X-LB-Signature": sig,
        },
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def extract_text(resp):
    parts = resp.get("data", {}).get("message", [])
    if not parts:
        parts = resp.get("message", [])
    return "".join(p.get("text", "") for p in parts if p.get("type") == "Plain")


def check(condition, name, detail=""):
    global passed, failed
    if condition:
        passed += 1
        results.append({"name": name, "status": "PASS", "detail": detail})
        print(f"  ✅ {name}")
    else:
        failed += 1
        results.append({"name": name, "status": "FAIL", "detail": detail})
        print(f"  ❌ {name}: {detail}")


def get_dump_lines():
    """返回 prompt dump 最新一次的 timeline 信息."""
    try:
        with open(PROMPT_DUMP, "r") as f:
            content = f.read()
    except FileNotFoundError:
        return None, None

    # 找最后一次 PROMPT DUMP
    parts = content.split("=== PROMPT DUMP ===")
    if len(parts) < 2:
        return None, None
    last_dump = parts[-1]

    # 提取 timeline 行数: "timeline (N lines, M chars)"
    m = re.search(r"timeline \((\d+) lines", last_dump)
    timeline_lines = int(m.group(1)) if m else None

    # 提取 bot 行
    bot_lines = [l for l in last_dump.split("\n") if "机器豆(BOT):" in l]

    return timeline_lines, bot_lines


def check_prompt_dump():
    """验证 prompt dump 中的 context 优化效果."""
    print("\n" + "=" * 50)
    print("【Prompt Dump 验证】")

    timeline_lines, bot_lines = get_dump_lines()
    if timeline_lines is None:
        check(False, "dump: 有新 prompt dump", "未找到 PROMPT DUMP")
        return

    check(True, "dump: 有新 prompt dump", f"{timeline_lines} 行 timeline")

    # history_count=20 → timeline 应 ≤ 16 行（20 行去重后约 14-16）
    check(timeline_lines <= 16, f"dump: timeline ≤16 行",
          f"实际 {timeline_lines} 行")

    # bot 回复应 ≤ 120 字
    long_bot = [l for l in bot_lines if len(l) > 125]
    if long_bot:
        check(False, f"dump: bot 回复 ≤120 字",
              f"{len(long_bot)} 条超长: {long_bot[0][:80]}...")
    else:
        check(True, f"dump: bot 回复 ≤120 字",
              f"{len(bot_lines)} 条 bot 行，全部 ≤120")


# ── 测试场景 ─────────────────────────────────────────────

def test_kb_retrieval():
    """KB 检索 — 朱元璋问题触发 KB 搜索."""
    print("\n" + "=" * 50)
    print("【测试 1: KB 检索】")
    r = send_sync([
        {"type": "At", "target": BOT_QQ},
        {"type": "Plain", "text": " 朱元璋到底长什么样？"},
    ])
    reply = extract_text(r)
    check(r.get("code") == 0, "kb: HTTP 200", f"code={r.get('code')}")
    check(len(reply) > 5, "kb: 回复非空", reply[:100])
    print(f"    回复: {reply[:150]}")
    time.sleep(2)


def test_web_search():
    """web_search — 要求搜索新闻."""
    print("\n" + "=" * 50)
    print("【测试 2: web_search】")
    r = send_sync([
        {"type": "At", "target": BOT_QQ},
        {"type": "Plain", "text": " 帮我搜索一下今天的科技新闻"},
    ])
    reply = extract_text(r)
    check(r.get("code") == 0, "web: HTTP 200", f"code={r.get('code')}")
    check(len(reply) > 5, "web: 回复非空", reply[:100])
    print(f"    回复: {reply[:150]}")
    time.sleep(2)


def test_timezone():
    """时区 — 白天回复不含'凌晨'."""
    print("\n" + "=" * 50)
    print("【测试 3: 时区规则】")
    r = send_sync([
        {"type": "At", "target": BOT_QQ},
        {"type": "Plain", "text": " 现在几点？"},
    ])
    reply = extract_text(r)
    check(r.get("code") == 0, "tz: HTTP 200", f"code={r.get('code')}")
    check(len(reply) > 3, "tz: 回复非空", reply[:100])
    check("凌晨" not in reply, "tz: 白天不含'凌晨'", reply[:100])
    print(f"    回复: {reply[:150]}")
    time.sleep(2)


def test_identity():
    """身份 — '你是谁'含'机器豆'."""
    print("\n" + "=" * 50)
    print("【测试 4: 身份保护】")
    r = send_sync([
        {"type": "At", "target": BOT_QQ},
        {"type": "Plain", "text": " 你是谁"},
    ])
    reply = extract_text(r)
    check(r.get("code") == 0, "id: HTTP 200", f"code={r.get('code')}")
    check(len(reply) > 3, "id: 回复非空", reply[:100])
    check("机器豆" in reply, "id: 含'机器豆'", reply[:100])
    print(f"    回复: {reply[:150]}")
    time.sleep(2)


def test_emoji():
    """表情 — 回复不含'看不到表情'."""
    print("\n" + "=" * 50)
    print("【测试 5: 表情识别】")
    r = send_sync([
        {"type": "At", "target": BOT_QQ},
        {"type": "Face", "face_id": 14, "face_name": ""},
    ])
    reply = extract_text(r)
    check(r.get("code") == 0, "emoji: HTTP 200", f"code={r.get('code')}")
    check(len(reply) > 3, "emoji: 回复非空", reply[:100])
    check("看不到表情" not in reply and "没接入" not in reply,
          "emoji: 不含拒绝语", reply[:100])
    print(f"    回复: {reply[:150]}")
    time.sleep(1)


TESTS = [
    ("kb", test_kb_retrieval),
    ("web", test_web_search),
    ("tz", test_timezone),
    ("id", test_identity),
    ("emoji", test_emoji),
]


def main():
    parser = argparse.ArgumentParser(description="Context 优化验证")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--scene", help="只跑单个场景 (kb/web/tz/id/emoji/dump)")
    parser.add_argument("--skip-dump", action="store_true", help="跳过 prompt dump 检查")
    args = parser.parse_args()

    if not args.json:
        print(f"Context 优化验证 — {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"BOT_UUID={BOT_UUID[:8]}... SESSION={SESSION}")

    start = time.time()

    if args.scene:
        if args.scene == "dump":
            check_prompt_dump()
        else:
            for name, fn in TESTS:
                if name == args.scene:
                    try:
                        fn()
                    except Exception as e:
                        check(False, f"{name}: 异常", str(e))
                    break
    else:
        for name, fn in TESTS:
            try:
                fn()
            except Exception as e:
                check(False, f"{name}: 异常", str(e))

        if not args.skip_dump:
            time.sleep(1)
            check_prompt_dump()

    elapsed = time.time() - start

    if args.json:
        print(json.dumps({
            "passed": passed, "failed": failed, "total": passed + failed,
            "elapsed_s": round(elapsed, 1), "results": results,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'='*50}")
        status = "✅ 全部通过" if failed == 0 else "❌ 有失败"
        print(f"结果: {passed}/{passed + failed} {status} ({elapsed:.1f}s)")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
