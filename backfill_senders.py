"""回填 ChromaDB 中的 sender_name：用群名片/头衔替换裸 QQ 昵称"""
import chromadb

c = chromadb.PersistentClient(path="/app/data/chroma")
col = c.get_collection("da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc")
data = col.get(include=["metadatas"])

# 构建 sender_id → 最佳 sender_name 映射（优先含群名片/头衔的）
sender_map = {}
for i, m in enumerate(data["metadatas"]):
    sid = m.get("sender_id", "")
    sname = m.get("sender_name", "")
    if not sid or sid in ("fake", "fake_ancient", "0", "unknown", ""):
        continue
    # 优先保留含 [] 或 () 的名字（有群名片/头衔/权限）
    if sid not in sender_map or ("[" in sname or "(" in sname):
        sender_map[sid] = sname

print(f"映射表: {len(sender_map)} 个 sender_id")

# 找出需要回填的：sender_id 在映射表中，但 sender_name 是裸名
updated = 0
for sid, best_name in sender_map.items():
    if "[" not in best_name and "(" not in best_name:
        continue  # 映射表里也是裸名，跳过

    # 找这个 sender_id 下所有裸名的消息
    bare_indices = []
    bare_ids = []
    new_metas = []
    for i, m in enumerate(data["metadatas"]):
        if m.get("sender_id") != sid:
            continue
        current_name = m.get("sender_name", "")
        if current_name == best_name:
            continue  # 已经是好的
        if "[" in current_name or "(" in current_name:
            continue  # 已有群名片信息，不覆盖

        # 需要更新
        old_text = m.get("text", "")
        new_text = old_text.replace(f"[{current_name}]", f"[{best_name}]", 1) if current_name else old_text
        if new_text == old_text:
            # 名字没出现在 text 前缀中，手动重建
            ts = m.get("timestamp", "")
            new_text = f"[{ts}] {best_name}: {old_text.split(']: ', 1)[-1] if ']: ' in old_text else old_text}"

        bare_ids.append(data["ids"][i])
        new_meta = dict(m)
        new_meta["sender_name"] = best_name
        new_meta["text"] = new_text
        new_metas.append(new_meta)

    if bare_ids:
        try:
            col.update(ids=bare_ids, metadatas=new_metas)
            updated += len(bare_ids)
            print(f"  {sid}: {best_name} ← 更新 {len(bare_ids)} 条")
        except Exception as e:
            print(f"  {sid}: 更新失败 - {e}")

print(f"\n回填完成: {updated} 条, KB 总计: {col.count()}")
