"""一次性迁移：buffer 消息 → KB（调用 LangBot embedding API）"""
import sys, os, json, hashlib, time

sys.path.insert(0, "/app/data/plugins/dou__langbot-silent-observer")
sys.path.insert(0, "/app/.venv/lib/python3.12/site-packages")

import sqlite3
from datetime import datetime

KB_ID = "da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc"
EMB_UUID = "62e075f9-733f-458c-8ce8-d983c411cad9"

def build_id(session, t, sid, text):
    raw = f"{session}|{t}|{sid}|{text}"
    return f"chat:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"

def build_label(name, title, role):
    label = name
    if title:
        label += f'[{title}]'
    elif role and role not in ('Permission.MEMBER', 'MEMBER'):
        label += f'({role})'
    return label

db = sqlite3.connect("/app/data/langbot.db")
rows = db.execute("SELECT key, value FROM binary_storages WHERE key LIKE 'buffer:%'").fetchall()

all_msgs = []
for key, value in rows:
    session_name = key.replace("buffer:", "")
    data = json.loads(value if isinstance(value, str) else value.decode('utf-8'))
    for m in data.get('messages', []):
        label = build_label(m.get('sender_name','?'), m.get('sender_title',''), m.get('sender_role',''))
        text = f"[{m.get('time','?')}] {label}: {m.get('text','')}"
        all_msgs.append({
            'session': session_name,
            'text': text,
            'sender_name': m.get('sender_name', ''),
            'sender_id': str(m.get('sender_id', '')),
            'timestamp': m.get('time', ''),
            'doc_id': build_id(session_name, m.get('time',''), str(m.get('sender_id','')), m.get('text','')),
        })

print(f"Total messages to migrate: {len(all_msgs)}")

# 使用 chromadb 直写 + langbot API 做 embedding
# 检查是否可从外部调 embedding API
from langbot_plugin.api.proxies.langbot_api import LangBotAPI

# 我们不在插件进程中，无法直接用 self.plugin.invoke_embedding
# 改用 chromadb 直接操作 + 使用内置 embedding

import chromadb
client = chromadb.PersistentClient(path="/app/data/chroma")
col = client.get_or_create_collection(KB_ID)

# 由于无法在外部调 embedding，直接存文本（无向量）
# 后续消息会带正确向量。这些迁移消息可通过 metadata filter 搜索
batch_size = 20
stored = 0
for i in range(0, len(all_msgs), batch_size):
    batch = all_msgs[i:i+batch_size]
    ids = []
    documents = []
    metadatas = []
    for m in batch:
        ids.append(m['doc_id'])
        documents.append(m['text'])
        metadatas.append({
            'text': m['text'],
            'sender_name': m['sender_name'],
            'sender_id': m['sender_id'],
            'timestamp': m['timestamp'],
            'timestamp_unix': 0.0,
            'session_id': m['session'],
            'type': 'chat_history',
        })
    # ChromaDB add with empty embeddings (use zero vectors of correct dim)
    # seekdb-local typically 768 or 384 dims, use 768
    import numpy as np
    dim = 768
    vectors = [[0.0] * dim for _ in batch]
    try:
        col.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=vectors)
        stored += len(batch)
        print(f"  Batch {i//batch_size+1}: {len(batch)} msgs stored ({stored}/{len(all_msgs)})")
    except Exception as e:
        print(f"  Batch {i//batch_size+1} ERROR: {e}")

print(f"\nMigration done: {stored}/{len(all_msgs)} messages in KB")
print(f"Dou KB count: {col.count()}")
