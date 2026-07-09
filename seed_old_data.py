"""插入半年前的测试数据"""
import chromadb, hashlib, json

c = chromadb.PersistentClient(path="/app/data/chroma")
col = c.get_collection("da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc")

fake_msgs = [
    ("2026-01-09 10:00", "张三", "最近想买个VR头盔，quest3和pico4哪个好？"),
    ("2026-01-09 10:05", "李四", "quest3吧，透视功能强，不过价格贵点"),
    ("2026-01-09 10:08", "王五", "pico4性价比高，国产生态，串流也方便"),
    ("2026-01-09 10:12", "张三", "那周末去店里试试quest3，有人想一起去吗？"),
    ("2026-01-09 14:30", "赵六", "今天天气真好，适合出去走走"),
    ("2026-01-09 14:35", "张三", "确实，春天的感觉"),
]

session = "group_1104330614"

for time_str, sender, text in fake_msgs:
    raw = f"{session}|{time_str}|{sender}|{text}"
    doc_id = f"chat:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"
    display = f"[{time_str}] {sender}: {text}"
    # 用简化的时间戳：把日期映射成 timestamp_unix
    ts_unix = 1736416800.0  # 2026-01-09 10:00 UTC
    meta = {
        "text": display,
        "sender_name": sender,
        "sender_id": "fake",
        "timestamp": time_str,
        "timestamp_unix": ts_unix,
        "session_id": session,
        "type": "chat_history",
    }
    try:
        col.add(ids=[doc_id], documents=[display], metadatas=[meta])
        print(f"Added: {display[:80]}")
    except Exception as e:
        print(f"Error: {e}")

print(f"\nKB total: {col.count()}")
