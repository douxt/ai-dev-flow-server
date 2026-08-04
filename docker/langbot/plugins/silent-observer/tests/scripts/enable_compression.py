#!/usr/bin/env python3
"""启用 P1 压缩：修改 plugin_settings.config JSON，添加 compression_* 字段."""
import sqlite3, json, sys, os

DB_PATH = "/app/data/langbot.db"
BACKUP_DIR = "/tmp/compression_backup"


def main():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    db = sqlite3.connect(DB_PATH)

    # 1. 读现有 plugin config
    row = db.execute(
        "SELECT config FROM plugin_settings "
        "WHERE plugin_author='dou' AND plugin_name='langbot-silent-observer'"
    ).fetchone()
    if not row:
        print("ERROR: plugin_settings not found")
        sys.exit(1)

    cfg = json.loads(row[0])

    # 备份
    backup_path = f"{BACKUP_DIR}/plugin_config_before_compression.json"
    with open(backup_path, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"Backup: {backup_path}")

    # 2. 添加压缩配置
    ref_uuid = cfg.get("reflection_model_uuid", "")
    cfg["compression_enabled"] = True
    cfg["compression_model_uuid"] = cfg.get("compression_model_uuid", "") or ref_uuid
    cfg.setdefault("compression_tail_max_chars", 1500)
    cfg.setdefault("compression_cooldown_minutes", 10)
    cfg.setdefault("compression_history_count", 200)

    print(f"compression_enabled = {cfg['compression_enabled']}")
    print(f"compression_model_uuid = {cfg['compression_model_uuid']}")
    print(f"compression_tail_max_chars = {cfg['compression_tail_max_chars']}")
    print(f"reflection_model_uuid = {ref_uuid}")

    # 3. 写回
    new_json = json.dumps(cfg, ensure_ascii=False)
    db.execute(
        "UPDATE plugin_settings SET config = ? "
        "WHERE plugin_author='dou' AND plugin_name='langbot-silent-observer'",
        (new_json,),
    )
    db.commit()
    db.close()
    print("Done. Restart langbot-plugin to apply.")


if __name__ == "__main__":
    main()
