"""直接测试 Dou KB 搜索"""
import sys
sys.path.insert(0, '/app/.venv/lib/python3.12/site-packages')
import chromadb, json

c = chromadb.PersistentClient(path='/app/data/chroma')
col = c.get_collection('da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc')
total = col.count()
print(f'Dou KB: {total} docs')

# 1. 检查 metadata 字段
r = col.get(limit=5)
for i in range(len(r['ids'])):
    meta = r['metadatas'][i]
    doc = r['documents'][i][:80]
    print(f'  [{meta.get("timestamp","?")}] text={meta.get("text","")[:60]}')
    print(f'    doc={doc}')

# 2. 检查向量
r2 = col.get(limit=3, include=['embeddings'])
emb = r2.get('embeddings')
if emb:
    e0 = emb[0]
    if e0:
        print(f'\nEmbedding dim: {len(e0)}, first 5 values: {e0[:5]}')
        has_real = sum(abs(v) for v in e0) > 0.01
        print(f'Has real values: {has_real}')
    else:
        print('\nEmbedding is None/null')
else:
    print('\nNo embeddings field')

# 3. 检查第一个 doc 的向量，用自身向量搜自己（验证向量有效）
print('\n--- Self-search test ---')
r3 = col.get(limit=1, include=['embeddings'])
if r3.get('embeddings') and r3['embeddings'][0]:
    qv = r3['embeddings'][0]
    results = col.query(query_embeddings=[qv], n_results=3)
    ids_found = results['ids'][0]
    dists = results['distances'][0] if results['distances'] else []
    print(f'Self-search: {len(ids_found)} results')
    for j, mid in enumerate(ids_found):
        doc = results['documents'][0][j][:80] if results['documents'] else ''
        print(f'  [{mid[:12]}] dist={dists[j]:.4f} doc={doc}')
else:
    print('No embedding for first doc - vectors might be zero or missing')
