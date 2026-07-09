"""测试 invoke_embedding 产生的向量 vs 存储的向量"""
import sys
sys.path.insert(0, '/app/.venv/lib/python3.12/site-packages')
import chromadb, json

c = chromadb.PersistentClient(path='/app/data/chroma')
col = c.get_collection('da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc')

# 取一个已知 doc 的 embedding
all_docs = col.get(include=['embeddings', 'documents'])
stored_vec = None
stored_text = None
for i in range(len(all_docs['ids'])):
    if '纳西火锅是啥' in (all_docs['documents'][i] or ''):
        stored_vec = all_docs['embeddings'][i]
        stored_text = all_docs['documents'][i]
        break

print(f'Stored vector: dim={len(stored_vec)}, first5={stored_vec[:5]}')
print(f'Stored text: {stored_text[:60]}')

# 用存储向量做 ChromaDB 搜索
r1 = col.query(query_embeddings=[stored_vec], n_results=5)
print('\nChromaDB query with stored vector:')
for j in range(len(r1['ids'][0])):
    d = r1['distances'][0][j]
    print(f'  dist={d:.4f} {(r1["documents"][0][j] or "")[:60]}')

# 现在我们需要 invok_embedding 的结果
# 无法直接调用，但可以用 LangBot MCP 或 API
# 临时：用存储的"之前有没有人聊过纳西火锅"向量
print('\n=== If invoke_embedding produces SAME dim vectors ===')
# 检查所有 doc 向量维度一致性
dims = set()
for e in all_docs['embeddings']:
    if e:
        dims.add(len(e))
print(f'Embedding dimensions in KB: {dims}')
