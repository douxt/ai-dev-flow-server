#!/usr/bin/env python3
"""DevFlow Telegram 通知 — dispatch/reconciler 调用的通知脚本
用法:
  echo "消息" | python3 notify.py status                    # 状态通知
  python3 notify.py approve-request < payload.json           # 审批请求
  python3 notify.py --config .devflow/config.yaml status     # 显式指定 config
从 .devflow/config.yaml 读取 telegram_chat_id 和 telegram_bot_token。
"""
import sys, os, json, urllib.request


def load_config(workspace="."):
    """从 .devflow/config.yaml 读取通知配置"""
    config_path = os.path.join(workspace, ".devflow", "config.yaml")
    if not os.path.exists(config_path):
        print("❌ config.yaml 不存在", file=sys.stderr)
        sys.exit(1)

    # 简单 YAML 解析（无 pyyaml 依赖）
    chat_id = None
    bot_token = None
    with open(config_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("telegram_chat_id:"):
                chat_id = line.split(":", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("telegram_bot_token:"):
                bot_token = line.split(":", 1)[1].strip().strip('"').strip("'")

    if not chat_id or not bot_token or chat_id.startswith("<") or bot_token.startswith("<"):
        print("❌ Telegram 配置未设置或为占位符", file=sys.stderr)
        sys.exit(1)

    return chat_id, bot_token


def send_telegram(chat_id, bot_token, text):
    """直连 Telegram Bot API 发送消息"""
    text = text[:4000]  # Telegram 消息上限
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"❌ Telegram 发送失败: {e}", file=sys.stderr)
        # 兜底：写本地 log
        log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "notify-fallback.log"), "a") as lf:
            lf.write(f"[{__import__('datetime').datetime.now().isoformat()}] {text}\n")
        return None


def main():
    workspace = os.getcwd()

    # 解析 --config
    args = sys.argv[1:]
    if args and args[0] == "--config":
        workspace = os.path.dirname(args[1])
        args = args[2:]

    if not args:
        print("用法: notify.py [--config <path>] <status|approve-request>", file=sys.stderr)
        sys.exit(1)

    mode = args[0]
    chat_id, bot_token = load_config(workspace)

    if mode == "status":
        text = sys.stdin.read().strip()
        if not text:
            print("❌ 需要管道输入消息", file=sys.stderr)
            sys.exit(1)
    elif mode == "approve-request":
        payload = json.load(sys.stdin)
        issue = payload.get("issue", "?")
        pr_url = payload.get("pr_url", "")
        files = payload.get("files", [])
        text = f"🔍 *待审批 PR*\n\nIssue: `{issue}`\nPR: {pr_url}\n改动文件: {', '.join(files[:10])}"
    else:
        print(f"❌ 未知模式: {mode}", file=sys.stderr)
        sys.exit(1)

    result = send_telegram(chat_id, bot_token, text)
    if result and result.get("ok"):
        print("✅ 通知已发送")
    else:
        print("⚠️ 通知发送失败，已写本地 log")
        sys.exit(1)


if __name__ == "__main__":
    main()
