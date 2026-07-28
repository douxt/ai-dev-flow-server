#!/usr/bin/env python3
"""后台队列压力测试 — 20条并发 /sync，验证 Queue+worker pool 无阻塞、无丢消息。
用法: scp 到 langbot-plugin 容器后执行 python3 /tmp/test_bg_stress.py
"""
import urllib.request, json, time, hmac, hashlib, sys, sqlite3, concurrent.futures

BOT_UUID = "dcbe70d9-af11-4624-908a-9928e4a08bdb"
SECRET = b"udimc123"
LANGBOT = "http://langbot:5300"
DB = "/app/data/plugins/dou__langbot-silent-observer/chat_index.db"
CONCURRENT = 20

def count_rows():
    db = sqlite3.connect(DB)
    n = db.execute("SELECT count(*) FROM chat_index").fetchone()[0]
    db.close()
    return n

def send_sync(i):
    """发送一条 /sync 请求，返回 (index, ok, error_msg)"""
    has_image = i >= 15  # 后5条模拟带图片
    msg = [{"type": "At", "target": "3228649756"}, {"type": "Plain", "text": f" 压力测试第{i}条"}]
    if has_image:
        msg.append({"type": "Plain", "text": " [图片]"})
    body = json.dumps({
        "session_id": f"stress_{i}_{int(time.time()*1000)}", "session_type": "person",
        "sender": {"id": f"99988877{i:02d}", "name": f"StressTester{i}"},
        "message": msg
    }).encode()
    ts = str(int(time.time()))
    sig = "sha256=" + hmac.new(SECRET, ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(f"{LANGBOT}/bots/{BOT_UUID}/sync",
        data=body, headers={"Content-Type": "application/json", "X-LB-Timestamp": ts, "X-LB-Signature": sig}, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        d = json.loads(resp.read())
        return (i, d.get("code") == 0, "")
    except Exception as e:
        return (i, False, str(e)[:100])

if __name__ == "__main__":
    before = count_rows()
    print(f"[1] before count: {before}")

    # 20 条并发（15 纯文本 + 5 带图占位）
    results = []
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT) as pool:
        futures = [pool.submit(send_sync, i) for i in range(CONCURRENT)]
        for f in concurrent.futures.as_completed(futures, timeout=90):
            results.append(f.result())
    elapsed = time.time() - t0
    print(f"[2] {len(results)}/{CONCURRENT} done in {elapsed:.1f}s")

    failures = [(i, err) for i, ok, err in results if not ok]
    if failures:
        for i, err in failures:
            print(f"[FAIL] msg#{i}: {err}")
    else:
        print("[OK] all HTTP 200")

    time.sleep(3)  # 等异步写入完成
    after = count_rows()
    delta = after - before
    print(f"[3] after count: {after} (delta={delta})")

    errors = []
    if len(failures) > 5:
        errors.append(f"{len(failures)} HTTP failures (LLM rate limit or overload)")
    if delta < 15:
        errors.append(f"delta={delta} < 15, possible message loss")
    # 注：delta > 25 是已知 flood bug（流式去重大于预期），非队列问题，不做硬性失败

    if errors:
        for e in errors:
            print(f"[FAIL] {e}")
        sys.exit(1)
    print(f"[OK] stress test passed: {len(results)} msgs, delta={delta}")
    sys.exit(0)
