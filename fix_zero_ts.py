"""修复 timestamp_unix=0 的记录，从 text 字段解析日期补充时间戳"""
import chromadb, time
from datetime import datetime, timezone, timedelta

BJT = timezone(timedelta(hours=8))
c = chromadb.PersistentClient(path="/app/data/chroma")
col = c.get_collection("da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc")
data = col.get(include=["metadatas"])

ids_fix, metas_fix = [], []
for i, m in enumerate(data["metadatas"]):
    if m.get("timestamp_unix", 0) != 0.0:
        continue
    ts_str = m.get("timestamp", "")
    text = m.get("text", "")
    if not ts_str:
        continue
    # 解析 MM-DD HH:MM 格式，补年份 2026
    try:
        dt = datetime.strptime(f"2026-{ts_str}", "%Y-%m-%d %H:%M")
        dt = dt.replace(tzinfo=BJT)
        ts_unix = dt.timestamp()
    except ValueError:
        continue

    doc_id = data["ids"][i]
    new_text = text.replace(f"[{ts_str}]", f"[{dt.strftime('%Y-%m-%d %H:%M')}]", 1)

    meta = dict(m)
    meta["timestamp"] = dt.strftime("%Y-%m-%d %H:%M")
    meta["timestamp_unix"] = ts_unix
    meta["text"] = new_text
    ids_fix.append(doc_id)
    metas_fix.append(meta)

print(f"待修复: {len(ids_fix)} 条")
if ids_fix:
    # 分批更新
    BATCH = 50
    for i in range(0, len(ids_fix), BATCH):
        col.update(
            ids=ids_fix[i:i+BATCH],
            metadatas=metas_fix[i:i+BATCH],
        )
        print(f"  [{min(i+BATCH, len(ids_fix))}/{len(ids_fix)}]")

    # 验证
    data2 = col.get(include=["metadatas"])
    still_zero = sum(1 for m in data2["metadatas"] if m.get("timestamp_unix", 0) == 0.0)
    print(f"修复后剩余 unix=0: {still_zero} 条")
