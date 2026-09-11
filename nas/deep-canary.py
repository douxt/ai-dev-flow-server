#!/usr/bin/env python3
"""深度链路金丝雀（最小可证伪检查）——每 6 小时由 NAS cron 运行。

为什么不是完整 8 场景套件：那套是"部署后人工验证"用的，多场景串行会被
LangBot 的会话占用（409）干扰，实测重试后总时长超 240s 被掐断（rc=124）。
周期金丝雀只需要回答一个问题：**业务链路还能产出回复吗？**

检查三项：
  1. napcat 在线
  2. langbot /sync 接受消息（HTTP 200 且 code==0）
  3. 回复非空（证明检索 + LLM 通路可用）

每次使用独立会话，避免与真实群会话或上一次运行互相占用。
退出码：0 通过 / 1 失败
"""
import hashlib
import hmac
import json
import sys
import time
import urllib.request
import uuid

BOT_UUID = "dcbe70d9-af11-4624-908a-9928e4a08bdb"
SECRET = b"udimc123"
LANGBOT = "http://langbot:5300"
NAPCAT = "http://localhost:3000"


def main():
    fails = []

    # 1) napcat 在线
    try:
        with urllib.request.urlopen(f"{NAPCAT}/get_status?access_token=udimc123", timeout=10) as r:
            online = json.loads(r.read()).get("data", {}).get("online")
        if not online:
            fails.append("napcat not online")
        else:
            print("  ✅ napcat online")
    except Exception as e:
        fails.append(f"napcat probe error: {e}")
        print(f"  ❌ napcat probe: {e}")

    # 2)+3) 一次 @ 消息走完整链路
    session = f"group_1104330614-canary-{uuid.uuid4().hex[:6]}"
    body = json.dumps({
        "session_id": session, "session_type": "group",
        "sender": {"id": "999888777", "name": "Canary", "group_name": "测试群"},
        "message": [{"type": "At", "target": "3228649756"},
                    {"type": "Plain", "text": " 在吗"}],
    }).encode()
    ts = str(int(time.time()))
    sig = "sha256=" + hmac.new(SECRET, ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        f"{LANGBOT}/bots/{BOT_UUID}/sync", data=body,
        headers={"Content-Type": "application/json",
                 "X-LB-Timestamp": ts, "X-LB-Signature": sig},
        method="POST")

    reply = ""
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            payload = json.loads(r.read())
        if payload.get("code") != 0:
            fails.append(f"sync code={payload.get('code')} msg={payload.get('msg', '')[:60]}")
            print(f"  ❌ sync code={payload.get('code')}")
        else:
            print("  ✅ sync code=0")
        parts = payload.get("data", {}).get("message", [])
        reply = "".join(p.get("text", "") for p in parts if p.get("type") == "Plain")
        if len(reply.strip()) < 2:
            fails.append(f"empty/short reply: {reply[:60]!r}")
            print("  ❌ 回复为空")
        else:
            print(f"  ✅ 回复非空（{len(reply)} 字符）")
    except Exception as e:
        fails.append(f"sync error: {e}")
        print(f"  ❌ sync: {e}")

    if fails:
        print("CANARY: FAIL — " + "; ".join(fails))
        return 1
    print(f"CANARY: OK — reply={reply.strip()[:40]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
