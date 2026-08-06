#!/usr/bin/env python3
"""P1 测试共享库 — 常量、HTTP/DB 工具、测试辅助."""
import urllib.request, urllib.error, json, time, hmac, hashlib, sys, os, sqlite3

# ── 常量 ──────────────────────────────────────────────
BOT_UUID = os.environ.get("BOT_UUID", "dcbe70d9-af11-4624-908a-9928e4a08bdb")
SECRET = os.environ.get("SECRET", "udimc123").encode()
LANGBOT = os.environ.get("LANGBOT", "http://langbot:5300")
BOT_QQ = "3228649756"
PROMPT_DUMP = "/tmp/silent_prompt_dump.log"
STATS_LOG = "/tmp/silent_stats.log"
COMPRESSION_LOG = "/tmp/silent_compression.log"
GATE_LOG = "/tmp/silent_gate.log"
SUMMARY_DB = "/app/data/plugins/dou__langbot-silent-observer/chat_index.db"
LANGBOT_DB = "/app/data/langbot.db"
PIPELINE_UUID = "dc0ff402-edc3-4dab-8054-d2a855241dea"
PLUGIN_AUTHOR = "dou"
PLUGIN_NAME = "langbot-silent-observer"
COOLDOWN_SECONDS = 600  # compression_cooldown_minutes=10

# ── 结果收集 ──────────────────────────────────────────
_results = []


def check(condition, name, detail=""):
    global _results
    if condition:
        _results.append({"name": name, "status": "PASS", "detail": detail})
        print(f"  ✅ {name}")
    else:
        _results.append({"name": name, "status": "FAIL", "detail": detail})
        print(f"  ❌ {name}: {detail}")
    return condition


def skip(name, reason=""):
    global _results
    _results.append({"name": name, "status": "SKIP", "detail": reason})
    print(f"  ⊘  {name}: {reason}")


def json_result():
    return {"results": _results, "passed": sum(1 for r in _results if r["status"] == "PASS"),
            "failed": sum(1 for r in _results if r["status"] == "FAIL"),
            "skipped": sum(1 for r in _results if r["status"] == "SKIP")}


def reset_results():
    global _results
    _results = []


# ── HTTP / Sync ───────────────────────────────────────
def send_sync(session_id, message_parts, timeout=120):
    """发送 /sync 请求，含 409 重试."""
    body = json.dumps({
        "session_id": session_id,
        "session_type": "group",
        "sender": {"id": "p15test", "name": "P15Tester", "group_name": "P15测试群"},
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
    last_err = None
    for attempt in range(5):
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 409:
                time.sleep(3)
                continue
            return {"error": str(e)}
        except Exception as e:
            last_err = e
            time.sleep(2)
    return {"error": str(last_err)}


def extract_text(resp):
    """从 sync 响应中提取纯文本."""
    if not resp or not isinstance(resp, dict):
        return None
    reply = resp.get("reply")
    if isinstance(reply, list):
        parts = []
        for r in reply:
            if isinstance(r, dict) and r.get("type") == "text":
                t = r.get("text", "")
                if t:
                    parts.append(t)
        return "".join(parts) if parts else None
    if isinstance(reply, str):
        return reply
    return None


# ── Session ───────────────────────────────────────────
def unique_session():
    """生成唯一测试 session ID."""
    return f"p15test_{time.time_ns()}"


def session_name_of(session_id):
    """插件内部格式：f'{launcher_type}_{launcher_id}'."""
    return f"group_{session_id}"


# ── Prompt Dump ───────────────────────────────────────
def get_dump_last():
    """返回最后一次 prompt dump 内容."""
    try:
        with open(PROMPT_DUMP, "r") as f:
            content = f.read()
    except FileNotFoundError:
        return None
    idx = content.rfind("=== PROMPT DUMP")
    if idx == -1:
        return None
    return content[idx:]


# ── Summary DB ────────────────────────────────────────
def get_summary_row(session_name):
    """读 summary 表行，返回 tuple 或 None."""
    try:
        db = sqlite3.connect(SUMMARY_DB, timeout=5)
        row = db.execute(
            "SELECT * FROM summary WHERE session_name = ?", (session_name,)
        ).fetchone()
        db.close()
        return row
    except Exception:
        return None


def clear_cooldown(session_name):
    """清除 cooldown，允许立即触发压缩."""
    try:
        db = sqlite3.connect(SUMMARY_DB, timeout=5)
        db.execute(
            "UPDATE summary SET cooldown_until = 0 WHERE session_name = ?",
            (session_name,),
        )
        db.commit()
        db.close()
    except Exception:
        pass


def cleanup_session(session_name):
    """删除测试 session 的 summary + chat_index 行."""
    try:
        db = sqlite3.connect(SUMMARY_DB, timeout=5)
        db.execute("DELETE FROM summary WHERE session_name = ?", (session_name,))
        db.commit()
        db.execute("DELETE FROM chat_index WHERE session_id = ?", (session_name,))
        db.commit()
        db.close()
    except Exception:
        pass


def wait_for_summary(session_name, timeout=90):
    """轮询等待 compression 完成（message_count > 0），返回 row 或 None."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        row = get_summary_row(session_name)
        if row and row[6] and row[6] > 0:  # message_count > 0
            return row
        time.sleep(2)
    return get_summary_row(session_name)


# ── LangBot DB ────────────────────────────────────────
def get_plugin_config():
    """读 plugin_settings.config JSON."""
    try:
        db = sqlite3.connect(LANGBOT_DB, timeout=5)
        row = db.execute(
            "SELECT config FROM plugin_settings WHERE plugin_author=? AND plugin_name=?",
            (PLUGIN_AUTHOR, PLUGIN_NAME),
        ).fetchone()
        db.close()
        return json.loads(row[0]) if row else None
    except Exception:
        return None


def get_pipeline_config():
    """读 legacy_pipelines.config JSON."""
    try:
        db = sqlite3.connect(LANGBOT_DB, timeout=5)
        row = db.execute(
            "SELECT config FROM legacy_pipelines WHERE uuid=?", (PIPELINE_UUID,)
        ).fetchone()
        db.close()
        return json.loads(row[0]) if row else None
    except Exception:
        return None


def get_system_prompt():
    """提取 system prompt 文本."""
    cfg = get_pipeline_config()
    if not cfg:
        return None
    try:
        return cfg["ai"]["local-agent"]["prompt"][0]["content"]
    except (KeyError, IndexError, TypeError):
        return None


# ── 日志检查 ──────────────────────────────────────────
def log_mtime(path):
    """返回日志文件最后修改时间（UNIX ts），不存在返回 0."""
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0


def log_recent_lines(path, max_lines=50):
    """返回日志文件最后 N 行."""
    try:
        with open(path, "r") as f:
            lines = f.readlines()
        return lines[-max_lines:]
    except (FileNotFoundError, OSError):
        return []
