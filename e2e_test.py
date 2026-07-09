"""端到端测试：模拟 inject 中的搜索链路"""
import sys
sys.path.insert(0, '/app/.venv/lib/python3.12/site-packages')

# Step 1: 用 ChromaDB 取得一个已知 doc 的向量
import chromadb
c = chromadb.PersistentClient(path='/app/data/chroma')
col = c.get_collection('da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc')
print(f'KB total: {col.count()}')

# Step 2: 测试 vector_search（模拟 self.plugin.vector_search）
# 取 "纳西火锅是啥？" 的向量作为查询
all_docs = col.get(include=['embeddings', 'documents'])
for i in range(len(all_docs['ids'])):
    if '纳西火锅是啥' in (all_docs['documents'][i] or ''):
        qv = all_docs['embeddings'][i]
        print(f'Query doc: {all_docs["documents"][i][:80]}')

        # 模拟 vector_search with type filter
        results = col.query(query_embeddings=[qv], n_results=10,
                           where={"type": "chat_history"})
        print(f'\nTop 10 (with type filter):')
        hit_count = 0
        for j in range(len(results['ids'][0])):
            dist = results['distances'][0][j]
            doc = (results['documents'][0][j] or '')[:80]
            meta = results['metadatas'][0][j]
            hit = ' HIT' if dist <= 1.0 else ''
            if dist <= 1.0:
                hit_count += 1
            print(f'  dist={dist:.4f}{hit} [{meta.get("timestamp","?")}] {doc}')
        print(f'\nResults within threshold (dist<=1.0): {hit_count}/10')
        break

# Step 3: 用另一个向量测试（更接近真实查询）
# 取 "之前有没有人聊过纳西火锅" 的向量
print('\n=== Second test ===')
for i in range(len(all_docs['ids'])):
    if '聊过纳西火锅' in (all_docs['documents'][i] or '') and '机器豆' not in (all_docs['documents'][i] or ''):
        qv2 = all_docs['embeddings'][i]
        print(f'Query doc: {all_docs["documents"][i][:80]}')
        results2 = col.query(query_embeddings=[qv2], n_results=10,
                            where={"type": "chat_history"})
        hit_count2 = 0
        for j in range(len(results2['ids'][0])):
            dist = results2['distances'][0][j]
            doc = (results2['documents'][0][j] or '')[:80]
            meta = results2['metadatas'][0][j]
            hit = ' HIT' if dist <= 1.0 else ''
            if dist <= 1.0:
                hit_count2 += 1
            print(f'  dist={dist:.4f}{hit} [{meta.get("timestamp","?")}] {doc}')
        print(f'\nResults within threshold (dist<=1.0): {hit_count2}/10')
        break
