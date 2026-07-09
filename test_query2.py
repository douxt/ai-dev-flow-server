"""扩展查询：纳西火锅，n_results=30"""
import chromadb
c = chromadb.PersistentClient(path='/app/data/chroma')
col = c.get_collection('da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc')
all_docs = col.get(include=['embeddings', 'documents'])
for i in range(len(all_docs['ids'])):
    if '纳西火锅是啥' in (all_docs['documents'][i] or ''):
        qv = all_docs['embeddings'][i]
        results = col.query(query_embeddings=[qv], n_results=30)
        # Count 07-08 messages in results
        old = [(j, d, t[:60]) for j, (d, t) in enumerate(zip(results['distances'][0], results['documents'][0])) if '07-08' in t]
        print(f'Found {len(old)} 07-08 messages:')
        for j, d, t in old:
            print(f'  dist={d:.4f} {t}')
        # Show ALL matching 纳西 docs with distances
        print(f'\nAll 纳西-related docs:')
        for j in range(len(results['ids'][0])):
            doc = results['documents'][0][j] or ''
            dist = results['distances'][0][j]
            if '纳西' in doc or '火锅' in doc:
                print(f'  dist={dist:.4f} {doc[:80]}')
        break
