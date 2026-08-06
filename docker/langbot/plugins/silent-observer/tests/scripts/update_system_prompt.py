#!/usr/bin/env python3
"""更新 System Prompt [检索决策]：旧格式 → 引用「群聊背景」+【】时间线."""
import sqlite3, json, sys, os, re

DB_PATH = "/app/data/langbot.db"
PIPELINE_UUID = "dc0ff402-edc3-4dab-8054-d2a855241dea"
BACKUP_DIR = "/tmp/prompt_backup"

OLD_LINE = "1. 先看【】时间线和群聊历史（系统已注入）"
OLD_LINE2 = "2. 不足时调 search_chat_history() 或 recall_memory()"
NEW_LINE = "1. 先看「群聊背景」（压缩摘要，系统已注入）再看【】时间线（最近原文，系统已注入），不足时调 search_chat_history() 或 recall_memory()"


def update():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    db = sqlite3.connect(DB_PATH)

    row = db.execute(
        "SELECT config FROM legacy_pipelines WHERE uuid=?", (PIPELINE_UUID,)
    ).fetchone()
    if not row:
        print("ERROR: pipeline not found")
        sys.exit(1)

    cfg = json.loads(row[0])
    prompt = cfg["ai"]["local-agent"]["prompt"][0]["content"]

    # 备份
    backup_path = f"{BACKUP_DIR}/system_prompt_before.txt"
    with open(backup_path, "w") as f:
        f.write(prompt)
    print(f"Backup: {backup_path}")

    # 检查前提条件
    assert OLD_LINE in prompt, f"OLD line 1 not found — already updated?\nExpected: {OLD_LINE}"
    assert OLD_LINE2 in prompt, f"OLD line 2 not found\nExpected: {OLD_LINE2}"

    # 替换
    prompt = prompt.replace(OLD_LINE, NEW_LINE)
    prompt = prompt.replace(OLD_LINE2, "")
    # 清理空行
    prompt = re.sub(r'\n{3,}', '\n\n', prompt)
    # 重编号 3→2, 4→3
    prompt = prompt.replace("3. 说明信息来源", "2. 说明信息来源")
    prompt = prompt.replace("4. 重要信息主动", "3. 重要信息主动")

    cfg["ai"]["local-agent"]["prompt"][0]["content"] = prompt
    new_json = json.dumps(cfg, ensure_ascii=False)
    db.execute(
        "UPDATE legacy_pipelines SET config = ? WHERE uuid = ?",
        (new_json, PIPELINE_UUID),
    )
    db.commit()
    db.close()
    print("Updated. Restart langbot to apply.")


def verify():
    db = sqlite3.connect(DB_PATH)
    row = db.execute(
        "SELECT config FROM legacy_pipelines WHERE uuid=?", (PIPELINE_UUID,)
    ).fetchone()
    if not row:
        print("VERIFY ERROR: pipeline not found")
        sys.exit(1)

    cfg = json.loads(row[0])
    prompt = cfg["ai"]["local-agent"]["prompt"][0]["content"]
    db.close()

    errors = []
    if NEW_LINE not in prompt:
        errors.append(f"NEW_LINE not in prompt")
    if OLD_LINE in prompt:
        errors.append(f"OLD_LINE still in prompt")
    if OLD_LINE2 in prompt:
        errors.append(f"OLD_LINE2 still in prompt")
    if "1." in prompt and "2. 说明信息来源" not in prompt:
        errors.append("renumbering failed: line 3 not renumbered to 2")
    if "3. 重要信息主动" not in prompt:
        errors.append("renumbering failed: line 4 not renumbered to 3")

    if errors:
        print("VERIFY FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("VERIFY OK")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "update"
    if cmd == "update":
        update()
    elif cmd == "verify":
        verify()
    elif cmd == "full":
        update()
        verify()
    else:
        print(f"Usage: {sys.argv[0]} [update|verify|full]")
        sys.exit(1)
