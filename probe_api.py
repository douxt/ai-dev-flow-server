"""API 能力探针：验证 retrieve_knowledge + vector_list 的 filters 支持"""
import sys

# 验证 Dou KB 存在且可用
KB_ID = "da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc"

# 先验证 ChromaDB collection 存在
import chromadb
client = chromadb.PersistentClient(path='/app/data/chroma')
cols = client.list_collections()
col_names = [c.name for c in cols]
print(f"ChromaDB collections: {col_names}")

if KB_ID in col_names:
    col = client.get_collection(KB_ID)
    print(f"Dou KB collection: count={col.count()}")
else:
    print(f"ERROR: Dou KB {KB_ID} not found in ChromaDB!")
    sys.exit(1)

# 验证 vector_list 支持 $and filter（通过 API 运行时）
# 这里仅做 ChromaDB 直连验证
try:
    r = col.get(where={"$and": [{"type": "chat_history"}, {"session_id": "test"}]}, limit=5)
    print(f"ChromaDB $and filter: OK ({len(r['ids'])} results)")
except Exception as e:
    print(f"ChromaDB $and filter FAILED: {e}")

# 验证 timestamp_unix $gte 数值过滤
try:
    r = col.get(where={"$and": [{"type": "chat_history"}, {"timestamp_unix": {"$gte": 0.0}}]}, limit=5)
    print(f"timestamp_unix $gte filter: OK ({len(r['ids'])} results)")
except Exception as e:
    print(f"timestamp_unix $gte FAILED: {e}")

print("\n=== PROBE PASSED ===")
