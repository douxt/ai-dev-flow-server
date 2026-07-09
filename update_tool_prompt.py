"""更新 pipeline 提示词，加入 search_chat_history 工具说明"""
import sqlite3, json

db = sqlite3.connect("/app/data/langbot.db")
row = db.execute("SELECT uuid, config FROM legacy_pipelines WHERE uuid='dc0ff402-edc3-4dab-8054-d2a855241dea'").fetchone()
cfg = json.loads(row[1]) if isinstance(row[1], str) else json.loads(row[1].decode())
prompt = cfg["ai"]["local-agent"]["prompt"]

old_ltm = """[记忆库（LTM）]
你的长期记忆，由你手动管理：
- recall_memory() 搜索已保存的记忆
- remember() 手动保存重要信息
- update_profile() 手动更新用户画像"""

new_ltm = """[可用工具]
以下是你可以在对话中主动调用的工具：

- recall_memory() — 搜索已保存的长期记忆
- remember() — 手动保存重要信息到长期记忆
- update_profile() — 手动更新用户画像
- search_chat_history(query, sender_name?, days?, top_k?) — 主动搜索全部群聊历史。
  当自动注入的[群聊历史检索]不足以回答问题，或需要查找特定人的发言/某时间段的话题时，主动调用此工具。
  参数：query(必填,搜索关键词), sender_name(可选,按发送者筛选), days(可选,限定最近N天), top_k(可选,返回条数,默认5)"""

for p in prompt:
    if p["role"] == "system" and old_ltm in p["content"]:
        p["content"] = p["content"].replace(old_ltm, new_ltm)
        print("已替换 LTM 工具段")
        break
else:
    print("未找到 LTM 段，检查内容...")
    for i, p in enumerate(prompt):
        if p["role"] == "system":
            print(f"Block {i}: {p['content'][:100]}...")

new_raw = json.dumps(cfg, ensure_ascii=False)
db.execute("UPDATE legacy_pipelines SET config=? WHERE uuid=?", (new_raw, row[0]))
db.commit()
print("提示词已更新")
