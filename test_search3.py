"""测试 纳西火锅 查询"""
import chromadb
c = chromadb.PersistentClient(path='/app/data/chroma')
col = c.get_collection('da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc')

# 用几条带纳西的 doc 的向量交叉搜索
# 找一条含"纳西"的 doc 的向量
all_docs = col.get(include=['embeddings', 'documents', 'metadatas'])
naxi_idx = None
for i in range(len(all_docs['ids'])):
    if '纳西' in (all_docs['documents'][i] or ''):
        naxi_idx = i
        break

if naxi_idx is not None:
    qv = all_docs['embeddings'][naxi_idx]
    print(f'Query doc: {all_docs["documents"][naxi_idx][:80]}')
    results = col.query(query_embeddings=[qv], n_results=10)
    print(f'\nTop 10 results:')
    for j, mid in enumerate(results['ids'][0]):
        dist = results['distances'][0][j]
        doc = results['documents'][0][j][:80]
        marker = ' <=1.0' if dist <= 1.0 else ''
        print(f'  [{mid[:12]}] dist={dist:.4f}{marker} {doc}')

# 再测另一条纳西文档
all_naxi = [i for i in range(len(all_docs['ids'])) if '纳西' in (all_docs['documents'][i] or '')]
print(f'\nTotal 纳西 docs: {len(all_naxi)}')
for ni in all_naxi[:2]:
    qv2 = all_docs['embeddings'][ni]
    r2 = col.query(query_embeddings=[qv2], n_results=5)
    print(f'\nQuery: {all_docs["documents"][ni][:60]}')
    for j in range(len(r2['ids'][0])):
        print(f'  dist={r2["distances"][0][j]:.4f} {r2["documents"][0][j][:80]}')
