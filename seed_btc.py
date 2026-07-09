"""插入3个月前的比特币讨论"""
import chromadb, hashlib, time

c = chromadb.PersistentClient(path="/app/data/chroma")
col = c.get_collection("da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc")

msgs = [
    ("2026-04-15 09:00", "张三", "最近比特币涨疯了，要不要入一点？"),
    ("2026-04-15 09:05", "李四", "别追高，上次6万入的被套了大半年"),
    ("2026-04-15 09:10", "王五", "我定投两年了，成本3万，现在翻倍了"),
    ("2026-04-15 09:15", "张三", "那定投确实稳，我研究一下"),
    ("2026-04-15 14:20", "赵六", "听说比特币挖矿很费电，不环保"),
    ("2026-04-15 14:25", "李四", "挖矿现在都是大矿场了，个人挖不了"),
]

session = "group_1104330614"

for time_str, sender, text in msgs:
    raw = f"{session}|{time_str}|{sender}|{text}"
    doc_id = f"chat:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"
    display = f"[{time_str}] {sender}: {text}"
    meta = {
        "text": display,
        "sender_name": sender,
        "sender_id": "fake",
        "timestamp": time_str,
        "timestamp_unix": 1744700000.0,
        "session_id": session,
        "type": "chat_history",
    }
    col.add(ids=[doc_id], documents=[display], metadatas=[meta])
    print(f"Added: {display[:80]}")

print(f"\nKB total: {col.count()}")
