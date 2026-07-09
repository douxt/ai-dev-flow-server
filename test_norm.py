"""检查存储向量和查询向量的 norm"""
import chromadb, math
c = chromadb.PersistentClient(path='/app/data/chroma')
col = c.get_collection('da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc')
all_docs = col.get(include=['embeddings', 'documents'])

# 随机取 10 个存储向量的 norm
norms = []
for i in range(min(20, len(all_docs['ids']))):
    e = all_docs['embeddings'][i]
    if e is not None and len(e) > 0:
        norm = math.sqrt(sum(v*v for v in e))
        norms.append(norm)

print(f'Stored vectors norm: min={min(norms):.4f} max={max(norms):.4f} avg={sum(norms)/len(norms):.4f}')
print(f'Sample norms: {[f"{n:.2f}" for n in norms[:10]]}')

# 如果 norm ≈ 1.0，则是单位向量（归一化）
# 如果 norm ≈ sqrt(384) ≈ 19.6，则是未归一化

# 检查 ChromaDB 的 distance function
print(f'\nChromaDB collection metadata: {col.metadata}')
