"""模拟真实查询：之前有没有人聊过纳西火锅？"""
import chromadb
c = chromadb.PersistentClient(path='/app/data/chroma')
col = c.get_collection('da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc')

# 用一条纳西文档的向量搜
all_docs = col.get(include=['embeddings', 'documents', 'metadatas'])
# 找"纳西火锅是啥？"作为锚点
for i in range(len(all_docs['ids'])):
    doc = all_docs['documents'][i] or ''
    if '纳西火锅是啥' in doc:
        qv = all_docs['embeddings'][i]
        print(f'Anchor: {doc[:80]}')
        results = col.query(query_embeddings=[qv], n_results=10)
        print(f'\nTop 10 (cosine distance, lower=more similar):')
        for j, mid in enumerate(results['ids'][0]):
            dist = results['distances'][0][j]
            text = (results['documents'][0][j] or '')[:80]
            hit = ' *** HIT (dist<=1.0)' if dist <= 1.0 else ''
            print(f'  dist={dist:.4f}{hit} {text}')
        break
