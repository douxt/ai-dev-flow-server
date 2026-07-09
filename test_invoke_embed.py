"""测试 invoke_embedding + vector_search 完整链路"""
import sys
sys.path.insert(0, '/app/.venv/lib/python3.12/site-packages')

# 模拟插件 API 调用
# 我们需要一个 plugin_runtime_handler 来调 invoke_embedding
# 由于不在插件进程中，改用 ChromaDB 测试

import chromadb
c = chromadb.PersistentClient(path='/app/data/chroma')
col = c.get_collection('da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc')

# 关键测试：用不同 query 文本的 embedding 搜索
# 取 "之前有人聊过纳西火锅吗？" 的向量(如果存在)
all_docs = col.get(include=['embeddings', 'documents'])

# 找两个 doc: A=原始问题 B=最近查询
query_a = None  # "纳西火锅是啥？"
query_b = None  # "之前有人聊过纳西火锅吗？"

for i in range(len(all_docs['ids'])):
    doc = all_docs['documents'][i] or ''
    if query_a is None and '纳西火锅是啥' in doc:
        query_a = (all_docs['embeddings'][i], doc)
    if query_b is None and '聊过纳西火锅' in doc and '机器豆' not in doc:
        query_b = (all_docs['embeddings'][i], doc)

if query_a and query_b:
    # 用 A 的向量搜
    r1 = col.query(query_embeddings=[query_a[0]], n_results=5, where={"type": "chat_history"})
    print('Query A (纳西火锅是啥？):')
    for j in range(len(r1['ids'][0])):
        d = r1['distances'][0][j]
        print(f'  dist={d:.4f} {"HIT" if d<=1.0 else ""} {(r1["documents"][0][j] or "")[:80]}')

    # 用 B 的向量搜
    r2 = col.query(query_embeddings=[query_b[0]], n_results=5, where={"type": "chat_history"})
    print('\nQuery B (之前有人聊过纳西火锅吗？):')
    for j in range(len(r2['ids'][0])):
        d = r2['distances'][0][j]
        print(f'  dist={d:.4f} {"HIT" if d<=1.0 else ""} {(r2["documents"][0][j] or "")[:80]}')

    # 检查 A 和 B 向量之间的相似度
    import math
    dot = sum(a*b for a,b in zip(query_a[0], query_b[0]))
    mag_a = math.sqrt(sum(a*a for a in query_a[0]))
    mag_b = math.sqrt(sum(b*b for b in query_b[0]))
    cos_sim = dot / (mag_a * mag_b)
    cos_dist = 1 - cos_sim
    print(f'\nA-B cosine distance: {cos_dist:.4f} (raw: {cos_dist*2:.4f})')
    print(f'If cos_dist*2 > 1.0, cross-query search would miss.')
