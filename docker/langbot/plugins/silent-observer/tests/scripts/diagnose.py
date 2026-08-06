#!/usr/bin/env python3
"""P1.5 一键诊断 — 只读检查系统健康状态.
用法:
  python3 diagnose.py           # 人类可读输出
  python3 diagnose.py --json    # JSON 输出
退出码: 0=全部OK(含INFO), 1=有WARN, 2=有ERROR
"""
import sys, os, time, sqlite3, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import (
    STATS_LOG, PROMPT_DUMP, COMPRESSION_LOG, SUMMARY_DB, LANGBOT_DB, PIPELINE_UUID,
    PLUGIN_AUTHOR, PLUGIN_NAME, get_plugin_config, get_system_prompt, log_mtime,
    log_recent_lines, COOLDOWN_SECONDS,
)

ERRORS = []
WARNS = []
INFOS = []


def error(msg):
    ERRORS.append(msg)
    print(f"❌ {msg}")


def warn(msg):
    WARNS.append(msg)
    print(f"⚠️  {msg}")


def info(msg):
    INFOS.append(msg)
    print(f"ℹ️  {msg}")


def ok(msg):
    print(f"✅ {msg}")


# ── 检查项 ─────────────────────────────────────────────

def check_1_plugin_alive():
    """#1 插件进程存活 — stats.log 最近 120s 内有写入."""
    mtime = log_mtime(STATS_LOG)
    age = time.time() - mtime if mtime else 9999
    if mtime == 0:
        error(f"stats.log 不存在 ({STATS_LOG})")
    elif age > 120:
        error(f"stats.log {age:.0f}s 未更新 — 插件可能已挂")
    else:
        ok(f"插件进程存活 (stats {age:.0f}s 前更新)")


def check_2_chat_index():
    """#2 chat_index.db 可读."""
    try:
        db = sqlite3.connect(SUMMARY_DB, timeout=5)
        count = db.execute("SELECT COUNT(*) FROM summary").fetchone()[0]
        sessions = db.execute("SELECT COUNT(*) FROM chat_index").fetchone()[0]
        db.close()
        ok(f"chat_index.db 可读 ({count} sessions, {sessions} messages)")
    except Exception as e:
        error(f"chat_index.db 不可读: {e}")


def check_3_langbot_db():
    """#3 langbot.db 可读 + plugin config 可解析."""
    cfg = get_plugin_config()
    if cfg is None:
        error("langbot.db 不可读或 plugin_settings 不存在")
    else:
        ok("langbot.db 可读 + plugin config 已解析")


def check_4_compression_enabled():
    """#4 compression_enabled."""
    cfg = get_plugin_config()
    if cfg is None:
        warn("compression_enabled: 无法读取配置")
        return
    enabled = cfg.get("compression_enabled", False)
    if enabled:
        ok(f"compression_enabled=True")
    else:
        warn("compression_enabled=False — 压缩未启用")


def check_5_kb_enabled():
    """#5 kb_enabled — KB 是压缩前置条件."""
    cfg = get_plugin_config()
    if cfg is None:
        error("kb_enabled: 无法读取配置")
        return
    kb_id = cfg.get("kb_id", "") or ""
    emb = cfg.get("embedding_model_uuid", "") or ""
    if kb_id and emb:
        ok(f"kb_enabled=True (kb_id=..., embedding_model=...)")
    else:
        error(f"kb_enabled=False — 压缩无法触发（缺 kb_id={bool(kb_id)} embedding={bool(emb)}）")


def check_6_model_uuid():
    """#6 compression_model_uuid 有效."""
    cfg = get_plugin_config()
    if cfg is None:
        warn("compression_model_uuid: 无法读取配置")
        return
    comp_uuid = str(cfg.get("compression_model_uuid", "") or "")
    ref_uuid = str(cfg.get("reflection_model_uuid", "") or "")
    effective = comp_uuid or ref_uuid
    if not effective:
        warn("compression_model_uuid 为空且无 fallback reflection_model_uuid")
        return
    # 验证在 llm_models 表中存在
    try:
        db = sqlite3.connect(LANGBOT_DB, timeout=5)
        row = db.execute(
            "SELECT model_name FROM llm_models WHERE id=?", (effective,)
        ).fetchone()
        db.close()
        if row:
            ok(f"compression_model_uuid={effective} (valid: {row[0]})")
        else:
            warn(f"compression_model_uuid={effective} — 在 llm_models 表中未找到（可能已删除）")
    except Exception as e:
        warn(f"compression_model_uuid={effective} — 无法验证: {e}")


def check_7_system_prompt():
    """#7 System Prompt [检索决策] 格式."""
    prompt = get_system_prompt()
    if prompt is None:
        warn("System Prompt: 无法读取 pipeline config")
        return
    has_new = "「群聊背景」" in prompt
    has_old = "先看【】时间线和群聊历史（系统已注入）" in prompt
    if has_new and not has_old:
        ok("System Prompt: 「群聊背景」格式已更新")
    elif has_new and has_old:
        warn("System Prompt: 新旧格式并存，需检查")
    else:
        warn("System Prompt: 未检测到新格式「群聊背景」引用")


def check_8_summary_state():
    """#8 summary 表状态."""
    try:
        db = sqlite3.connect(SUMMARY_DB, timeout=5)
        rows = db.execute(
            "SELECT session_name, facts, datetime(updated_at,'unixepoch','localtime'), message_count "
            "FROM summary WHERE session_name NOT LIKE 'group_p15test_%' ORDER BY updated_at DESC"
        ).fetchall()
        db.close()
        for r in rows:
            fmt = "旧 (Python repr)" if r[1].startswith("[") else "新 (bullet)" if r[1].startswith("- ") else "?"
            info(f"  {r[0]}: {r[3]}msgs updated={r[2]} fmt={fmt}")
        if not rows:
            info("  (无 summary 行)")
    except Exception as e:
        warn(f"summary 表状态: 查询失败 {e}")


def check_9_last_compression():
    """#9 最近压缩时间（排除测试 session）."""
    try:
        db = sqlite3.connect(SUMMARY_DB, timeout=5)
        row = db.execute(
            "SELECT session_name, datetime(updated_at,'unixepoch','localtime'), "
            "CAST((strftime('%s','now') - updated_at) AS INTEGER) "
            "FROM summary WHERE session_name NOT LIKE 'group_p15test_%' "
            "ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        db.close()
        if row:
            info(f"最近压缩: {row[1]} ({row[2]}s 前) session={row[0]}")
        else:
            info("最近压缩: (无)")
    except Exception as e:
        warn(f"最近压缩: 查询失败 {e}")


def check_10_failed_compression():
    """#10 压缩失败检测 — cooldown 但 message_count==0."""
    try:
        db = sqlite3.connect(SUMMARY_DB, timeout=5)
        now = time.time()
        rows = db.execute(
            "SELECT session_name, cooldown_until FROM summary "
            "WHERE cooldown_until > ? AND message_count = 0", (now,)
        ).fetchall()
        db.close()
        for r in rows:
            warn(f"压缩失败: {r[0]} (cooldown 中但 message_count=0，上次压缩可能报错)")
        if not rows:
            ok("压缩队列: 无失败记录")
    except Exception as e:
        warn(f"压缩失败检测: 查询失败 {e}")


def check_11_lock_skips():
    """#11 409 锁检测 — stats.log 中 lock_skips."""
    lines = log_recent_lines(STATS_LOG, 100)
    for line in reversed(lines):
        if "lock_skips" in line:
            try:
                val = int(line.split("lock_skips")[-1].split("=")[-1].split()[0].rstrip(","))
                if val > 5:
                    warn(f"lock_skips={val}（最近 100 行）— 可能有 session 锁死")
                else:
                    info(f"lock_skips={val} — 正常范围")
            except Exception:
                pass
            break
    else:
        info("lock_skips: 未检测到（stats 可能不含此字段）")


def check_12_compression_errors():
    """#12 压缩异常日志."""
    lines = log_recent_lines(COMPRESSION_LOG, 200)
    failed = [l for l in lines if "FAILED" in l or "parse returned None" in l]
    recent = [l for l in failed if "compression" in l.lower() or "FAILED" in l]
    if recent:
        warn(f"压缩异常: 最近 {len(recent)} 条 FAILED/parse-None ({recent[-1].strip()[-80:]})")
    else:
        ok("压缩日志: 无近期异常")


def check_13_prompt_dump():
    """#13 prompt dump 可用性."""
    mtime = log_mtime(PROMPT_DUMP)
    try:
        size = os.path.getsize(PROMPT_DUMP)
    except OSError:
        size = 0
    if size > 0:
        age = time.time() - mtime if mtime else 0
        info(f"prompt dump 可用 ({size//1024}KB, 最后 {age:.0f}s 前)")
    else:
        info("prompt dump: 空或不存在")


# ── Main ───────────────────────────────────────────────
CHECKS = [
    check_1_plugin_alive,
    check_2_chat_index,
    check_3_langbot_db,
    check_4_compression_enabled,
    check_5_kb_enabled,
    check_6_model_uuid,
    check_7_system_prompt,
    check_8_summary_state,
    check_9_last_compression,
    check_10_failed_compression,
    check_11_lock_skips,
    check_12_compression_errors,
    check_13_prompt_dump,
]


def main():
    use_json = "--json" in sys.argv

    if not use_json:
        print(f"=== P1.5 诊断 [{time.strftime('%m-%d %H:%M')}] ===")

    for fn in CHECKS:
        try:
            fn()
        except Exception as e:
            error(f"{fn.__doc__ or fn.__name__}: 异常 {e}")

    if not use_json:
        print("─" * 24)
        print(f"结果: {len(CHECKS)-len(ERRORS)-len(WARNS)} 通过, {len(WARNS)} 警告, {len(ERRORS)} 失败")

    if use_json:
        print(json.dumps({
            "errors": ERRORS, "warns": WARNS, "infos": INFOS,
            "exit_code": 2 if ERRORS else 1 if WARNS else 0,
        }, ensure_ascii=False, indent=2))

    if ERRORS:
        sys.exit(2)
    if WARNS:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
