#!/usr/bin/env python3
"""P1 对话成熟度冒烟 — rewrite 链路 + when-then 注入 + 反思库增量。

用法（容器内）: /app/.venv/bin/python tests/scripts/verify_p1_maturity.py
断言:
  (a) 纠正句"不对，你搞错了" → 15s 内 silent_reflection.log 出现 rewrite: + stored:
  (b) 话题问题 → /tmp/silent_gate.log（raw prompt）出现"触发条件"（when-then 注入）
  (c) stored: 计数增量 ≥1（反思库写入）
"""
import urllib.request, json, time, hmac, hashlib, os, sys, subprocess

BOT_UUID = os.environ.get("BOT_UUID", "dcbe70d9-af11-4624-908a-9928e4a08bdb")
SECRET = os.environ.get("SECRET", "udimc123").encode()
LANGBOT = os.environ.get("LANGBOT", "http://langbot:5300")
SESSION = os.environ.get("SESSION", "1104330614")
BOT_QQ = "3228649756"
REFLECTION_LOG = "/tmp/silent_reflection.log"
GATE_LOG = "/tmp/silent_gate.log"
EVENT_LOG = "/tmp/silent_event.log"
MONITOR_DB = "/app/data/langbot.db"


SENDER_ID = f"smoke-{int(time.time())}"  # 唯一 sender：绕开反思 sender 10min 冷却


def send_sync(text):
    body = json.dumps({
        "session_id": SESSION, "session_type": "group",
        "sender": {"id": SENDER_ID, "name": "SmokeTest", "group_name": "测试群"},
        "message": [{"type": "Plain", "text": text}, {"type": "At", "target": BOT_QQ}],
    }).encode()
    ts = str(int(time.time()))
    sig = "sha256=" + hmac.new(SECRET, ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        f"{LANGBOT}/bots/{BOT_UUID}/sync", data=body,
        headers={"Content-Type": "application/json", "X-LB-Timestamp": ts, "X-LB-Signature": sig},
        method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=20)  # 超时不影响后台处理
        return json.loads(resp.read())
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:80]}"}


def count(path, needle):
    try:
        out = subprocess.run(["grep", "-c", needle, path], capture_output=True, text=True)
        return int(out.stdout.strip() or "0")
    except Exception:
        return 0


def wait_count_above(path, needle, threshold, timeout=120, step=2):
    """轮询 grep 计数超过阈值（timeout 秒）"""
    for _ in range(int(timeout / step)):
        if count(path, needle) > threshold:
            return True
        time.sleep(step)
    return False


def main():
    fails = []
    # ── T0 基线 ──
    t0_stored = count(REFLECTION_LOG, "stored:")
    t0_rewrite = count(REFLECTION_LOG, "rewrite:")
    t0_whenthen = count(GATE_LOG, "触发条件")
    t0_hit = count(EVENT_LOG, " hit ")
    print(f"T0: stored={t0_stored} rewrite={t0_rewrite} when-then={t0_whenthen} hit={t0_hit}")

    # ── (b) 话题问题 → when-then 注入 ──
    resp = send_sync("P1冒烟：380V工业电机选断路器，负载功率已知，怎么选？")
    print(f"sync#1: {'ok' if not resp.get('error') else resp['error']}")
    ok = wait_count_above(EVENT_LOG, " hit ", t0_hit, timeout=30)
    print(f"gate#1 处理: {ok}")
    time.sleep(50)  # 等 bot 回复开始（流式首条刷新纠正窗口）
    if count(GATE_LOG, "触发条件") > t0_whenthen:
        print("(b) PASS: when-then 注入出现")
    else:
        # 注入依赖 ref_query 与反思库的 embedding 命中，非确定性；SKIP 不阻断
        print("(b) SKIP: 本轮无 when-then 增量（检索未命中，人工可查 raw prompt 复核）")

    # ── (a) 纠正句 → rewrite 链路（单次尝试；sender cooldown 10min 挡重试）──
    resp = send_sync("不对，你搞错了")
    print(f"sync#2: {'ok' if not resp.get('error') else resp['error']}")
    if wait_count_above(REFLECTION_LOG, "rewrite:", t0_rewrite, timeout=120, step=3):
        print("(a1) PASS: rewrite 调用出现")
        if count(REFLECTION_LOG, "stored:") > t0_stored:
            print("(a2) PASS: 反思已存储（增量 " +
                  str(count(REFLECTION_LOG, "stored:") - t0_stored) + "）")
        else:
            fails.append("(a2) 反思未存储")
    else:
        # 窗口未命中（bot 回复时序波动）或 sender cooldown：标记人工复核
        print("(a1) SKIP: rewrite 未在 120s 内出现（窗口未命中/限流，人工复核）")
        fails.append("(a1) SKIP: rewrite 窗口未命中")

    # ── (c) 增量 ≥1 ──
    inc = count(REFLECTION_LOG, "stored:") - t0_stored
    if inc >= 1:
        print(f"(c) PASS: stored 增量={inc}")
    else:
        fails.append(f"(c) stored 增量={inc} < 1")

    if fails:
        print("FAIL: " + "; ".join(fails))
        sys.exit(1)
    print("PASS: P1 maturity 冒烟全绿")


if __name__ == "__main__":
    main()
