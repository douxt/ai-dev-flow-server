import sqlite3, json
db = sqlite3.connect('/app/data/langbot.db')
row = db.execute("SELECT uuid, config FROM legacy_pipelines WHERE uuid='dc0ff402-edc3-4dab-8054-d2a855241dea'").fetchone()
cfg = json.loads(row[1] if isinstance(row[1], str) else row[1].decode('utf-8'))
prompt = cfg['ai']['local-agent']['prompt']
for p in prompt:
    if p['role'] == 'system':
        old = p['content']
        # 替换之前临时加的记忆库说明
        old = old.replace('[全量记忆库]\n群聊记忆库包含所有历史消息。当收到 [记忆库检索结果] 标记的记录时，这些就是你的记忆的一部分，必须引用其中的信息。\n[群聊历史]', '[群聊历史]')
        # 在 [群聊历史] 段之前插入完整的两套记忆系统说明
        memory_block = '''[两套记忆系统]
你有两套独立的记忆系统，使用时需区分：

1. 长期记忆（LTM）— 由你主动管理
   - 写入：用 remember() 保存重要信息
   - 读取：用 recall_memory() 搜索已保存的记忆
   - 用户画像：用 update_profile() 更新
   - 内容：你主动提炼的关键事实、用户偏好、人物关系

2. 全量记忆库 — 自动注入，无需你调用
   - 每次对话自动从全部群聊历史中检索相关内容
   - 检索结果通过 [记忆库检索结果] 标记注入到对话中
   - 内容：所有群聊消息的原始记录，包括你之前说过的每句话
   - 注意：这些记录是你的记忆的一部分，必须引用，不可否认其中存在的内容

[群聊历史]'''
        new_content = old.replace('[群聊历史]', memory_block, 1)
        p['content'] = new_content
        print('=== NEW SYSTEM PROMPT (memory section) ===')
        for line in new_content.split('\n'):
            if '记忆' in line or '群聊历史' in line or '规则' in line or 'LTM' in line or 'remember' in line or 'recall' in line:
                print(line)
        break

new_raw = json.dumps(cfg, ensure_ascii=False)
db.execute("UPDATE legacy_pipelines SET config=? WHERE uuid=?", (new_raw, row[0]))
db.commit()
print('\nSaved.')
