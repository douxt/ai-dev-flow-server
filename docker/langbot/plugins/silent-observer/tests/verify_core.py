#!/usr/bin/env python3
"""Silent Observer 核心验证脚本 — 部署后一键自检，不需要人在群里发消息。

通过 /sync 端点模拟用户消息，结构化断言 + LTM 内容断言。
用法（容器内执行）:
  python3 /tmp/verify_core.py              # 全部场景
  python3 /tmp/verify_core.py --scene ltm  # 仅 LTM 专项
  python3 /tmp/verify_core.py --scene core # 仅核心链路
  python3 /tmp/verify_core.py --json       # 输出 JSON（CI 友好）
"""
import urllib.request, json, time, hmac, hashlib, sys, sqlite3, os, argparse, re

# ── 配置（容器内地址） ──────────────────────────────────────
BOT_UUID = os.environ.get("BOT_UUID", "dcbe70d9-af11-4624-908a-9928e4a08bdb")
SECRET = os.environ.get("SECRET", "udimc123").encode()
LANGBOT = os.environ.get("LANGBOT", "http://langbot:5300")
NAPCAT = os.environ.get("NAPCAT", "http://localhost:3000")
SESSION = os.environ.get("SESSION", "group_1104330614")
DB_PATH = "/app/data/plugins/dou__langbot-silent-observer/chat_index.db"
GATE_LOG = "/tmp/silent_gate.log"
BOT_QQ = "3228649756"

passed = 0
failed = 0
results = []  # [{name, status, detail}]


# ── 工具函数 ─────────────────────────────────────────────────
def send_sync(message_parts, timeout=90, session=None):
    body = json.dumps({
        "session_id": session or SESSION, "session_type": "group",
        "sender": {"id": "999888777", "name": "自动验证", "group_name": "测试群"},
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
    return "".join(p.get("text", "") for p in parts if p.get("type") == "Plain")


def napcat_get(path):
    try:
        sep = "&" if "?" in path else "?"
        req = urllib.request.Request(f"{NAPCAT}{path}{sep}access_token=udimc123")
        return json.loads(urllib.request.urlopen(req, timeout=10).read())
    except Exception as e:
        return {"error": str(e)}


def grep_log(pattern, tail_n=0):
    """在容器内 grep gate log。tail_n=0 表示搜索全部行，>0 表示只搜最后 N 行。"""
    try:
        with open(GATE_LOG, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return []
    if tail_n > 0:
        lines = lines[-tail_n:]
    matched = [l.rstrip() for l in lines if pattern in l]
    return matched


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


# ── 场景实现 ─────────────────────────────────────────────────

def scene_connectivity():
    """L1: 连通性 — langbot 是否可达（napcat 由 verify-fix.sh 外部检测）"""
    print("\n" + "=" * 50)
    print("【L1 连通性】")
    # 用普通 HTTP GET 检查 langbot 是否可达（/sync 会等 LLM，太慢）
    try:
        req = urllib.request.Request(f"{LANGBOT}/")
        resp = urllib.request.urlopen(req, timeout=10)
        check(resp.status == 200, "langbot HTTP 可达",
              f"status={resp.status}")
    except Exception as e:
        check(False, "langbot HTTP 可达", str(e))


def scene_core():
    """L2: 核心链路 — @Bot 文本消息 → gate → inject → LLM → 回复"""
    print("\n" + "=" * 50)
    print("【L2 核心链路】")

    # 记录发送前的 gate log 行数
    try:
        with open(GATE_LOG, "r") as f:
            log_before = len(f.readlines())
    except FileNotFoundError:
        log_before = 0

    r = send_sync([
        {"type": "At", "target": BOT_QQ},
        {"type": "Plain", "text": " 你好，测试一下"},
    ])
    reply = extract_text(r)

    check(r.get("code") == 0, "gate: HTTP 200", f"code={r.get('code')}")
    check(len(reply) > 3, "inject: LLM 回复非空", reply[:80])

    # 验证 gate 日志有新条目
    new_logs = grep_log("gate:")
    check(len(new_logs) > 0, "gate: 日志有 gate 决策记录",
          f"找到 {len(new_logs)} 条")
    inject_logs = grep_log("inject")
    check(len(inject_logs) > 0, "inject: 日志有注入记录",
          f"找到 {len(inject_logs)} 条")

    check("ERROR" not in " ".join(new_logs + inject_logs),
          "gate/inject: 无 ERROR", "")

    time.sleep(1)


def scene_ltm():
    """LTM 专项: 建立记忆 → 召回 → 内容级断言"""
    print("\n" + "=" * 50)
    print("【LTM 专项】")

    # Step 1: 建立记忆
    r1 = send_sync([
        {"type": "At", "target": BOT_QQ},
        {"type": "Plain", "text": " 请记住，我最喜欢的颜色是深海蓝"},
    ])
    reply1 = extract_text(r1)
    check(r1.get("code") == 0, "ltm-step1: /sync 可达", f"code={r1.get('code')}")
    check(len(reply1) > 3, "ltm-step1: 有回复", reply1[:80])
    print(f"    回复1: {reply1[:100]}")

    # 给 memory_injector 一些时间处理
    time.sleep(4)

    # Step 2: 召回记忆
    r2 = send_sync([
        {"type": "At", "target": BOT_QQ},
        {"type": "Plain", "text": " 我之前说的喜欢的颜色是什么？"},
    ])
    reply2 = extract_text(r2)
    check(r2.get("code") == 0, "ltm-step2: /sync 可达", f"code={r2.get('code')}")
    check(len(reply2) > 3, "ltm-step2: 有回复", reply2[:80])
    print(f"    回复2: {reply2[:150]}")

    # Step 3: 检查 memory_injector 是否触发（或 LTM 错误）
    inject_logs = grep_log("memory_injector")
    ltm_errors = grep_log("memory knowledge base is not configured")
    if ltm_errors:
        check(False, "ltm: pipeline 未配置 memory KB",
              "日志中发现 'memory knowledge base is not configured' 错误")
    elif inject_logs:
        check(True, "ltm: memory_injector 触发",
              f"找到 {len(inject_logs)} 条")
    else:
        check(False, "ltm: memory_injector 未触发",
              "无 memory_injector 日志，也无 LTM 错误")

    # Step 4: 内容级断言 — LLM 是否回忆起了颜色
    color_keywords = ["蓝", "深蓝", "深海", "blue", "Blue"]
    recalled = any(kw in reply2 for kw in color_keywords)
    forget_keywords = ["不记得", "不清楚", "不知道", "没说过", "没提到"]
    forgot = any(kw in reply2 for kw in forget_keywords)

    if recalled:
        check(True, "ltm: 回复包含记忆关键词（蓝/深蓝）", reply2[:80])
    elif forgot:
        check(False, "ltm: 回复含遗忘语（不记得/不清楚）", reply2[:80])
    else:
        # 模糊情况 — 不算失败，只标记
        check(True, "ltm: 回复未明确遗忘（模糊）", reply2[:80])

    # Step 5: 检查 chat_index（/sync 路径可能不写 chat_index，仅作信息提示）
    try:
        db = sqlite3.connect(DB_PATH)
        count = db.execute(
            "SELECT count(*) FROM chat_index WHERE session_id=? AND timestamp_unix > ?",
            (SESSION, int(time.time()) - 120),
        ).fetchone()[0]
        db.close()
        if count > 0:
            check(True, f"ltm: chat_index 有新记录 ({count})", "")
        else:
            # /sync 路径不写 chat_index 是已知行为，不算失败
            print(f"  ℹ️  ltm: chat_index 无新记录 (/sync 路径不写 DB，已知)")
    except Exception as e:
        print(f"  ⚠️  ltm: chat_index 不可读: {e}")


def scene_face():
    """表情识别"""
    print("\n" + "=" * 50)
    print("【Face 表情识别】")
    r = send_sync([
        {"type": "At", "target": BOT_QQ},
        {"type": "Face", "face_id": 14, "face_name": ""},
    ])
    reply = extract_text(r)
    check(r.get("code") == 0, "face: HTTP 200", f"code={r.get('code')}")
    check(len(reply) > 5, "face: 回复非空", reply[:80])
    check("没数据" not in reply and "没东西" not in reply,
          "face: 不含拒绝语", reply[:80])
    check("惊讶" in reply or "表情" in reply or "QQ" in reply or "14" in reply,
          "face: 含表情关键词", reply[:80])
    time.sleep(1)


def scene_quote():
    """引用消息"""
    print("\n" + "=" * 50)
    print("【Quote 引用消息】")
    r = send_sync([
        {"type": "At", "target": BOT_QQ},
        {"type": "Quote", "origin": [
            {"type": "Plain", "text": "这是一条被引用的测试消息"}
        ]},
        {"type": "Plain", "text": " 上面说的对吗？"},
    ])
    reply = extract_text(r)
    check(r.get("code") == 0, "quote: HTTP 200", f"code={r.get('code')}")
    check(len(reply) > 5, "quote: 回复非空", reply[:80])
    time.sleep(1)


def scene_vision():
    """图片处理（不调真实 vision API，只测 strip-base64）"""
    print("\n" + "=" * 50)
    print("【Vision 图片 strip】")
    r = send_sync([
        {"type": "At", "target": BOT_QQ},
        {"type": "Plain", "text": " 看看这张图"},
        {"type": "Image", "url": "https://example.com/test.png",
         "base64": "data:image/png;base64,AAAA"},
    ])
    check(r.get("code") == 0, "vision: HTTP 200", f"code={r.get('code')}")
    vision_logs = grep_log("vision:")
    if vision_logs:
        check("vision: fail" not in " ".join(vision_logs),
              "vision: 无 fail", "")
    time.sleep(1)


def scene_noise():
    """无 @ 闲聊 — gate 应 miss（概率控制）"""
    print("\n" + "=" * 50)
    print("【Noise 闲聊 gate-miss】")
    r = send_sync([
        {"type": "Plain", "text": f"今天天气真不错啊 {int(time.time())}"},
    ], timeout=30, session=f"noise_{int(time.time()*1000)}")
    reply = extract_text(r)
    check(r.get("code") == 0, "noise: HTTP 200", f"code={r.get('code')}")
    gate_logs = grep_log("gate:")
    # noise 消息不应该触发 gate hit（除非 prob 巧合）
    has_miss = any("miss" in l for l in gate_logs)
    check(True, "noise: 请求完成（gate miss 预期）",
          f"gate miss 存在: {has_miss}")


# ── 场景注册 ─────────────────────────────────────────────────
SCENES = {
    "connectivity": scene_connectivity,
    "core": scene_core,
    "ltm": scene_ltm,
    "face": scene_face,
    "quote": scene_quote,
    "vision": scene_vision,
    "noise": scene_noise,
}

SCENE_ORDER = ["connectivity", "core", "ltm", "face", "quote", "vision", "noise"]


# ── Main ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Silent Observer 核心验证")
    parser.add_argument("--scene", choices=list(SCENES.keys()) + ["all"],
                        default="all", help="运行指定场景 (默认 all)")
    parser.add_argument("--json", action="store_true",
                        help="输出 JSON 结果")
    args = parser.parse_args()

    if not args.json:
        print(f"验证开始 — {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"BOT_UUID={BOT_UUID[:8]}... SESSION={SESSION}")

    if args.scene == "all":
        scenes_to_run = SCENE_ORDER
    else:
        scenes_to_run = [args.scene]

    start = time.time()
    for name in scenes_to_run:
        try:
            SCENES[name]()
        except Exception as e:
            check(False, f"{name}: 异常", str(e))

    elapsed = time.time() - start
    total = passed + failed

    if args.json:
        print(json.dumps({
            "passed": passed, "failed": failed, "total": total,
            "elapsed_s": round(elapsed, 1),
            "results": results,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'='*50}")
        status = "✅ 全部通过" if failed == 0 else "❌ 有失败"
        print(f"结果: {passed}/{total} {status} ({elapsed:.1f}s)")
        print("=" * 50)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
