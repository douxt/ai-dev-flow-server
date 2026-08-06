#!/usr/bin/env python3
"""P1 上下文压缩验证 — /sync 驱动，验证压缩触发、摘要注入、信息保真。
用法（langbot-plugin 容器内）:
  python3 /tmp/verify_p1.py           # 全部场景
  python3 /tmp/verify_p1.py --scene 1 # 单场景
  python3 /tmp/verify_p1.py --json    # JSON 输出
"""
import urllib.request, json, time, hmac, hashlib, sys, os, re, sqlite3

BOT_UUID = os.environ.get("BOT_UUID", "dcbe70d9-af11-4624-908a-9928e4a08bdb")
SECRET = os.environ.get("SECRET", "udimc123").encode()
LANGBOT = os.environ.get("LANGBOT", "http://langbot:5300")
SESSION = os.environ.get("SESSION", "group_1104330614")
SESSION_NAME = f"group_{SESSION}"  # 插件内部格式
BOT_QQ = "3228649756"
PROMPT_DUMP = "/tmp/silent_prompt_dump.log"
SUMMARY_DB = "/app/data/plugins/dou__langbot-silent-observer/chat_index.db"

passed = 0
failed = 0
skipped = 0
results = []


def send_sync(message_parts, timeout=120):
    body = json.dumps({
        "session_id": SESSION, "session_type": "group",
        "sender": {"id": "p1test", "name": "P1Test", "group_name": "测试群"},
        "message": message_parts,
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


def skip(name, reason):
    global skipped
    skipped += 1
    results.append({"name": name, "status": "SKIP", "detail": reason})
    print(f"  ⏳ {name}: {reason}")


def get_summary_row():
    """读 summary 表，返回 (row | None, error | None)."""
    try:
        db = sqlite3.connect(SUMMARY_DB, timeout=5)
        row = db.execute(
            "SELECT * FROM summary WHERE session_name = ?", (SESSION_NAME,)
        ).fetchone()
        db.close()
        return row, None
    except Exception as e:
        return None, str(e)


def get_dump_last():
    """返回最后一次 prompt dump 内容."""
    try:
        with open(PROMPT_DUMP, "r") as f:
            content = f.read()
    except FileNotFoundError:
        return None
    parts = content.split("=== PROMPT DUMP ===")
    return parts[-1] if len(parts) >= 2 else None


# ── 场景 ──────────────────────────────────────────────


def scene_1_trigger():
    """发 15+ 条消息 → 等待后台压缩 → summary 表有新行."""
    print("\n[1] 压缩触发")

    # 清旧数据
    try:
        db = sqlite3.connect(SUMMARY_DB, timeout=5)
        db.execute("DELETE FROM summary WHERE session_name = ?", (SESSION_NAME,))
        db.commit()
        db.close()
    except Exception:
        pass

    # 发送 15 条消息（@bot 才能过 gate 触发压缩）
    for i in range(15):
        resp = send_sync([
            {"type": "Plain", "text": f"P1压缩测试第{i}条。请简单回复。"},
            {"type": "At", "target": BOT_QQ},
        ])
        reply = extract_text(resp)
        if not reply and resp.get("error"):
            check(False, f"compress-msg-{i}", f"HTTP error: {resp['error']}")
            return
        time.sleep(2)  # 给后台压缩时间

    # 等待后台压缩完成（轮询 summary 表，最多 60s）
    for _ in range(30):
        row, err = get_summary_row()
        if err:
            check(False, "summary-table", f"DB error: {err}")
            return
        if row and row[6] and row[6] > 0:  # message_count > 0
            break
        time.sleep(2)

    row, _ = get_summary_row()
    has_count = row and (row[6] or 0) > 0
    check(has_count, "compress-triggered",
          f"message_count={row[6] if row else 'N/A'}")


def scene_2_inject():
    """压缩后再发消息 → prompt dump 含新格式摘要块."""
    print("\n[2] 摘要注入")

    resp = send_sync([
        {"type": "Plain", "text": "你好，请简单回复。"},
        {"type": "At", "target": BOT_QQ},
    ])
    time.sleep(3)

    dump = get_dump_last()
    if not dump:
        check(False, "summary-in-prompt", "no prompt dump found")
        return
    has_new = "─── 群聊背景" in dump
    no_old = "[上下文摘要]" not in dump
    has_bullet = "- " in dump
    check(has_new, "summary-marker-new", f"dump {'contains' if has_new else 'missing'} ─── marker")
    check(no_old, "summary-marker-old-gone", f"dump {'contains' if not no_old else 'no'} [上下文摘要] (should be gone)")
    check(has_bullet, "summary-bullets", f"dump {'contains' if has_bullet else 'missing'} bullet lines")


def scene_3_facts_preserved():
    """在消息中埋关键信息 → 压缩后读 summary 表 → facts 字段含原值."""
    print("\n[3] 关键信息保留")

    secret_number = "938271645"
    secret_phrase = "P1保留测试专用标记"

    # 发送多条含关键信息的消息
    for i in range(5):
        send_sync([
            {"type": "Plain",
             "text": f"说到预算问题，编号{secret_number}的项目限价{secret_number}元。"
                     f"注意{secret_phrase}。另外闲聊内容长一点" + "测试" * 20},
            {"type": "At", "target": BOT_QQ},
        ])
        time.sleep(2)

    # 等压缩
    time.sleep(15)

    row, _ = get_summary_row()
    if not row:
        check(False, "facts-preserved", "no summary row")
        return

    # row: (session_name, topics, facts, decisions, refs, covered_until_ts,
    #        message_count, updated_at, cooldown_until)
    facts = (row[2] or "") + (row[1] or "")
    has_number = secret_number in facts
    has_phrase = secret_phrase in facts
    check(has_number, "facts-number", f"{secret_number} {'found' if has_number else 'missing'}")
    check(has_phrase, "facts-phrase", f"'{secret_phrase}' {'found' if has_phrase else 'missing'}")


def scene_4_tail_dedup():
    """压缩后 inject → timeline 不含已覆盖的消息（即 timeline 行数 < 15）."""
    print("\n[4] Tail 去重")

    resp = send_sync([
        {"type": "Plain", "text": "简单回复即可"},
        {"type": "At", "target": BOT_QQ},
    ])
    time.sleep(3)

    dump = get_dump_last()
    if not dump:
        check(False, "tail-dedup", "no prompt dump")
        return

    m = re.search(r"timeline \((\d+) lines", dump)
    lines = int(m.group(1)) if m else 999
    # 由于 covered_until_ts 过滤，timeline 应缩短
    check(lines < 15, "tail-shortened", f"timeline={lines} lines (should < 15)")


def scene_5_cooldown():
    """cooldown_until 应 > 当前时间（压缩刚完成）."""
    print("\n[5] 冷却期")

    row, _ = get_summary_row()
    if not row:
        check(False, "cooldown-set", "no summary row")
        return

    cooldown_until = row[8] or 0
    now = time.time()
    has_cooldown = cooldown_until > now
    check(has_cooldown, "cooldown-set",
          f"cooldown_until={cooldown_until:.0f} now={now:.0f} "
          f"(remaining={cooldown_until - now:.0f}s)")


def scene_6_disabled():
    """compression_enabled=false → prompt dump 不含摘要块（需手动关闭配置后测试）."""
    print("\n[6] 关闭压缩回退")
    skip("disabled-check", "需在 WebUI 关 compression_enabled 后手动验证")


def scene_7_second_compress():
    """二次压缩后 → facts 仍精确匹配（验证多轮不衰减）."""
    print("\n[7] 二次压缩保真")

    # 读当前 facts 作为基线
    row_before, _ = get_summary_row()
    if not row_before:
        skip("second-compress", "no baseline summary")
        return
    facts_before = row_before[2] or ""

    # 发送更多消息触发二次压缩
    for i in range(5):
        send_sync([
            {"type": "Plain",
             "text": f"追加消息第{i}条——讨论新话题。长一点" + "内容" * 20},
            {"type": "At", "target": BOT_QQ},
        ])
        time.sleep(2)

    time.sleep(15)

    row_after, _ = get_summary_row()
    if not row_after:
        check(False, "second-compress-triggered", "no summary after second round")
        return

    # 旧 facts 中的关键信息应保留
    facts_after = row_after[2] or ""
    preserved = "938271645" in facts_after
    check(preserved, "second-compress-facts",
          "number preserved across 2 rounds" if preserved else "number LOST after 2nd compression")


# ── main ───────────────────────────────────────────────


SCENES = {
    "1": scene_1_trigger,
    "2": scene_2_inject,
    "3": scene_3_facts_preserved,
    "4": scene_4_tail_dedup,
    "5": scene_5_cooldown,
    "6": scene_6_disabled,
    "7": scene_7_second_compress,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", help="只跑指定场景")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    start = time.time()

    if args.scene:
        scenes_to_run = {args.scene: SCENES[args.scene]}
    else:
        scenes_to_run = SCENES

    for name, fn in scenes_to_run.items():
        try:
            fn()
        except Exception as e:
            check(False, f"scene-{name}", f"exception: {e}")

    elapsed = time.time() - start

    if args.json:
        print(json.dumps({
            "passed": passed, "failed": failed, "skipped": skipped,
            "elapsed_s": round(elapsed, 1), "results": results,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'='*40}")
        print(f"Results: {passed} passed, {failed} failed, {skipped} skipped "
              f"({elapsed:.0f}s)")
        if failed:
            print("FAIL")
            sys.exit(1)
        else:
            print("PASS")


if __name__ == "__main__":
    import argparse
    main()
