import chromadb, hashlib, json
c = chromadb.PersistentClient(path="/app/data/chroma")
col = c.get_collection("da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc")
msgs = [
    ("2026-03-20 10:00", "张三", "五一去海南怎么样？三亚还是海口？"),
    ("2026-03-20 10:05", "李四", "三亚海滩好，海口吃的多，看你想要啥"),
    ("2026-03-20 10:10", "王五", "三亚蜈支洲岛潜水超赞，就是住宿贵"),
    ("2026-03-20 10:15", "张三", "预算5000够吗？玩5天"),
    ("2026-03-20 10:20", "李四", "淡季够，五一翻倍，建议错峰"),
    ("2026-03-20 14:00", "赵六", "海南文昌鸡好吃，还有清补凉"),
    ("2026-03-20 14:05", "王五", "对对对，清补凉夏天绝了"),
]
session = "group_1104330614"
for ts, sender, text in msgs:
    raw = f"{session}|{ts}|{sender}|{text}"
    doc_id = f"chat:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"
    meta = {"text": f"[{ts}] {sender}: {text}", "sender_name": sender, "sender_id": "fake", "timestamp": ts, "timestamp_unix": 1742457600.0, "session_id": session, "type": "chat_history"}
    col.add(ids=[doc_id], documents=[f"[{ts}] {sender}: {text}"], metadatas=[meta])
    print(f"Added: [{ts}] {sender}: {text[:60]}")
print(f"KB: {col.count()}")
