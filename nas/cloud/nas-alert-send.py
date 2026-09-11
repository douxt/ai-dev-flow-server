#!/usr/bin/env python3
"""把 stdin 的文本经 Telegram 发出。

在阿里云运行（唯一具备 Telegram 通道的机器）。凭据与代理复用
/opt/maf-hub/config/telegram.json —— 单一事实源，不复制 token。

用法: echo "消息" | python3 nas-alert-send.py
退出码: 0 已发送 / 2 空消息 / 3 无 chat_id / 4 API 返回 not ok / 5 网络失败
"""
import json
import sys
import urllib.request

CONF = "/opt/maf-hub/config/telegram.json"


def main():
    text = sys.stdin.read().strip()
    if not text:
        print("empty message", file=sys.stderr)
        return 2
    try:
        with open(CONF) as f:
            conf = json.load(f)
    except Exception as e:
        print(f"读取 {CONF} 失败: {e}", file=sys.stderr)
        return 3

    token = conf.get("bot_token")
    chat_id = conf.get("chat_id")
    if not token or not chat_id:
        print("bot_token/chat_id 未配置", file=sys.stderr)
        return 3

    handlers = []
    proxy = conf.get("proxy") or ""
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)

    data = json.dumps({
        "chat_id": chat_id,
        "text": text[:4000],
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener.open(req, timeout=15) as r:
            ok = json.loads(r.read()).get("ok")
    except Exception as e:
        print(f"发送失败: {e}", file=sys.stderr)
        return 5
    if not ok:
        print("API 返回 not ok", file=sys.stderr)
        return 4
    print("sent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
