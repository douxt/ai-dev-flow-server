#!/usr/bin/env python3
"""P1.5 注入治理冒烟 — 压制条款上屏 / 电气条目不再注入 / dists 采样.

用法（容器内）: /app/.venv/bin/python tests/scripts/verify_p15_inject.py
断言:
  预检  目标群最后 hit 距今 <120s 或日志缺失 → exit 2（改期再跑）
  需显式 SECRET 环境变量
  (a)   本轮 RAW PROMPT 含"仅供你内部理解"（压制条款，FAIL 门禁）
  (b)   本轮 RAW PROMPT 的"触发条件："行不含 电气/380V/断路器/DS920（门槛+清理双保险，FAIL 门禁）
  (c)   T0 后 silent_reflection.log 出现 inject candidates: → 打印 dists（信息性，供阈值校准）
  (d)   相近问题有注入则断言头注前缀；无注入 SKIP（检索非确定性）
"""
import urllib.request, json, time, hmac, hashlib, os, sys, subprocess

BOT_UUID = os.environ.get("BOT_UUID", "dcbe70d9-af11-4624-908a-9928e4a08bdb")
SECRET_RAW = os.environ.get("SECRET", "")
if not SECRET_RAW:
    print("FATAL: 需显式 SECRET 环境变量（不落盘密钥）")
    sys.exit(2)
SECRET = SECRET_RAW.encode()
LANGBOT = os.environ.get("LANGBOT", "http://langbot:5300")
SESSION = os.environ.get("SESSION", "1104330614")
BOT_QQ = "3228649756"
REFLECTION_LOG = "/tmp/silent_reflection.log"
GATE_LOG = "/tmp/silent_gate.log"
EVENT_LOG = "/tmp/silent_event.log"

SENDER_ID = f"smoke2-{int(time.time())}"
ELEC = ("电气", "380V", "断路器", "DS920")


def send_sync(text):
    body = json.dumps({
        "session_id": SESSION, "session_type": "group",
        "sender": {"id": SENDER_ID, "name": "SmokeTest2", "group_name": "测试群"},
        "message": [{"type": "Plain", "text": text}, {"type": "At", "target": BOT_QQ}],
    }).encode()
    ts = str(int(time.time()))
    sig = "sha256=" + hmac.new(SECRET, ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        f"{LANGBOT}/bots/{BOT_UUID}/sync", data=body,
        headers={"Content-Type": "application/json", "X-LB-Timestamp": ts, "X-LB-Signature": sig},
        method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:80]}"}


def count(path, needle):
    try:
        out = subprocess.run(["grep", "-c", needle, path], capture_output=True, text=True)
        return int(out.stdout.strip() or "0")
    except Exception:
        return 0


def last_raw_prompt():
    """gate.log 最后一个 LLM RAW PROMPT 段（本轮注入的唯一完整落盘）"""
    try:
        with open(GATE_LOG, 'r', errors='replace') as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 2_000_000))
            data = f.read()
    except Exception:
        return ''
    i = data.rfind('LLM RAW PROMPT')
    if i < 0:
        return ''
    seg = data[i:]
    j = seg.find('=== END RAW PROMPT ===')
    return seg[:j] if j > 0 else seg


def wait_inject(t0_inject, timeout=90):
    needle = f'group_{SESSION} inject '
    for _ in range(timeout // 3):
        if count(EVENT_LOG, needle) > t0_inject:
            return True
        time.sleep(3)
    return False


def last_hit_age(scope):
    """最后一条 hit 距今秒数。hit-inject 累计差含 lock_skip/prevent_default 历史噪声，
    真实积压只能看新鲜度。"""
    try:
        out = subprocess.run(["grep", "-a", f'{scope} hit ', EVENT_LOG],
                             capture_output=True, text=True)
        lines = [l for l in out.stdout.splitlines() if l]
        if not lines:
            return -1.0  # 日志缺失，状态未知
        return time.time() - float(lines[-1].split()[0])
    except Exception:
        return 0.0


def main():
    fails = []
    # ── 预检：目标群近 2 分钟无正在处理的消息 ──
    scope = f"group_{SESSION}"
    age = last_hit_age(scope)
    if age < 0:
        print(f'PREFLIGHT FAIL: {scope} 无 hit 记录或日志缺失，无法确认在途状态')
        sys.exit(2)
    if age < 120:
        print(f'PREFLIGHT FAIL: {scope} {age:.0f}s 前刚有 hit（可能有在途消息），稍后再跑')
        sys.exit(2)
    print(f'preflight ok: {scope} last hit {age:.0f}s ago')

    t0_inject = count(EVENT_LOG, f'{scope} inject ')
    t0_cand = count(REFLECTION_LOG, "inject candidates:")

    # ── (a)(b) VR 无关问题 ──
    resp = send_sync("Quest3 玩节奏光剑卡顿怎么解决？")
    print(f"sync#1: {'ok' if not resp.get('error') else resp['error']}")
    if not wait_inject(t0_inject):
        print('FAIL: 90s 内无 inject（gate 未处理本轮）')
        sys.exit(1)
    time.sleep(3)  # RAW PROMPT 落盘在 inject 前一步，留缓冲
    seg = last_raw_prompt()
    if not seg:
        fails.append("(a) gate.log 无 RAW PROMPT 段可读")
    elif '节奏光剑' not in seg:
        fails.append("(a) 末段不含本轮提问文本——段归属不明（并发或本轮未处理），拒判")
    else:
        if '仅供你内部理解' in seg:
            print("(a) PASS: 压制条款已进 prompt")
        else:
            fails.append("(a) 压制条款缺失")
        bad = [ln for ln in seg.splitlines()
               if '触发条件：' in ln and any(k.lower() in ln.lower() for k in ELEC)]
        if bad:
            fails.append(f"(b) 电气反思仍被注入: {bad[0][:60]}")
        else:
            print("(b) PASS: 无电气条目注入")

    # ── (c) dists 采样 ──
    time.sleep(2)
    try:
        out = subprocess.run(["grep", "-a", "inject candidates:", REFLECTION_LOG],
                             capture_output=True, text=True)
        lines = [l for l in out.stdout.splitlines() if l][-3:]
    except Exception:
        lines = []
    new_cand = count(REFLECTION_LOG, "inject candidates:") - t0_cand
    print(f"(c) 本轮新增 candidates 日志 {new_cand} 行（累计 {count(REFLECTION_LOG, 'inject candidates:')}）")
    for l in lines:
        print('   ', l[-160:])
    if new_cand < 1:
        print("    (反思未召回或 inject 未走到检索段——清理后属正常，持续观察)")

    # ── (d) 相近问题注入头注（库空则 SKIP）──
    t0_inject2 = count(EVENT_LOG, f'group_{SESSION} inject ')
    resp = send_sync("之前聊过的电机选型，断路器多大合适来着？")
    print(f"sync#2: {'ok' if not resp.get('error') else resp['error']}")
    wait_inject(t0_inject2)
    seg2 = last_raw_prompt()
    if '断路器' not in seg2:
        print("(d) SKIP: 末段不含本轮提问（段归属不明），不判定")
    elif '触发条件：' in seg2:
        if '[先前经验 · 仅供内部参考' in seg2:
            print("(d) PASS: 注入含头注前缀")
        else:
            fails.append("(d) 有注入但缺头注前缀")
    else:
        print("(d) SKIP: 本轮无注入（库空/门槛过滤，非缺陷）")

    if fails:
        print("FAIL: " + "; ".join(fails))
        sys.exit(1)
    print("PASS: P1.5 冒烟全绿")


if __name__ == "__main__":
    main()
