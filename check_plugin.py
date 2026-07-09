"""检查插件导入 + 自动迁移 buffer → KB"""
import sys, os
sys.path.insert(0, '/app/data/plugins/dou__langbot-silent-observer')
sys.path.insert(0, '/app/.venv/lib/python3.12/site-packages')

# 1. 测试导入
from components.event_listener.default import DefaultEventListener
print('default.py import OK')
from components.tool.search_chat_history import SearchChatHistory
print('tool import OK')

# 2. 检查 buffer 数据
import sqlite3, json
db = sqlite3.connect('/app/data/langbot.db')
rows = db.execute("SELECT key, value FROM binary_storages WHERE key LIKE 'buffer:%'").fetchall()
total = 0
for key, value in rows:
    data = json.loads(value if isinstance(value, str) else value.decode('utf-8'))
    n = len(data.get('messages', []))
    total += n
    print(f'  {key}: {n} msgs')
print(f'Total buffer: {total} msgs')

# 3. 检查 KB
import chromadb
c = chromadb.PersistentClient(path='/app/data/chroma')
col = c.get_collection('da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc')
print(f'Dou KB: {col.count()} docs')
