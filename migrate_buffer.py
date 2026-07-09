"""迁移 buffer 中近期消息到 KB"""
import json, sys, hashlib

sys.path.insert(0, "/app/data/plugins/dou__langbot-silent-observer")
# 注意：此脚本在容器内执行，需手动构造 metadata 和 doc_id

import sqlite3, time
from datetime import datetime

# 复用插件中的辅助函数
def build_document_id(session_name, time_str, sender_id, text):
    raw = f"{session_name}|{time_str}|{sender_id}|{text}"
    return f"chat:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"

# 配置
KB_ID = "da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc"
EMB_UUID = "62e075f9-733f-458c-8ce8-d983c411cad9"

# 从插件存储读 buffer
db = sqlite3.connect("/app/data/langbot.db")
rows = db.execute("SELECT key, value FROM binary_storages WHERE key LIKE 'buffer:%'").fetchall()

total = 0
for key, value in rows:
    session_name = key.replace("buffer:", "")
    try:
        data = json.loads(value if isinstance(value, str) else value.decode('utf-8'))
        msgs = data.get('messages', [])
    except Exception as e:
        print(f"SKIP {key}: parse error {e}")
        continue

    print(f"Migrating {len(msgs)} messages from {session_name}...")
    for m in msgs:
        text = f"[{m.get('time','?')}] {m.get('sender_name','?')}: {m.get('text','')}"
        doc_id = build_document_id(session_name, m.get('time',''), str(m.get('sender_id','')), m.get('text',''))
        # 需要 plugin.invoke_embedding + plugin.vector_upsert
        # 但这里没有 plugin 引用。用 ChromaDB 直接写入
        # 我们通过调用 silent-observer 的 API 来完成
        print(f"  {doc_id}: {text[:80]}")

    total += len(msgs)

print(f"\nTotal: {total} messages to migrate")

# 实际迁移通过直接操作 ChromaDB
# 使用 chromadb 直写的方式
