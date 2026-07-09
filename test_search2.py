"""直接测试 KB 向量搜索"""
import chromadb
c = chromadb.PersistentClient(path='/app/data/chroma')
col = c.get_collection('da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc')
r3 = col.get(limit=3, include=['embeddings', 'documents', 'metadatas'])
for i in range(len(r3['ids'])):
    e = r3['embeddings'][i]
    non_zero = sum(1 for v in e if abs(v) > 0.001)
    print(f'  [{r3["ids"][i][:12]}] dim={len(e)} non-zero={non_zero} doc={r3["documents"][i][:60]}')

# Self-search: use first doc's vector
qv = r3['embeddings'][0]
results = col.query(query_embeddings=[qv], n_results=5)
print(f'\nSelf-search results:')
for j, mid in enumerate(results['ids'][0]):
    dist = results['distances'][0][j]
    doc = results['documents'][0][j][:80]
    print(f'  [{mid[:12]}] dist={dist:.4f} {doc}')
