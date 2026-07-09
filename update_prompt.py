import sqlite3, json
db = sqlite3.connect('/app/data/langbot.db')
row = db.execute("SELECT uuid, config FROM legacy_pipelines WHERE uuid='dc0ff402-edc3-4dab-8054-d2a855241dea'").fetchone()
cfg = json.loads(row[1] if isinstance(row[1], str) else row[1].decode('utf-8'))
prompt = cfg['ai']['local-agent']['prompt']
for p in prompt:
    if p['role'] == 'system':
        content = p['content']
        if '[全量记忆库]' not in content and '[群聊历史]' in content:
            content = content.replace(
                '[群聊历史]',
                '[全量记忆库]\n群聊记忆库包含所有历史消息。当收到 [记忆库检索结果] 标记的记录时，这些就是你的记忆的一部分，必须引用其中的信息。\n[群聊历史]'
            )
            p['content'] = content
            print('Added memory bank section to system prompt')
            break

new_raw = json.dumps(cfg, ensure_ascii=False)
db.execute("UPDATE legacy_pipelines SET config=? WHERE uuid=?", (new_raw, row[0]))
db.commit()
print('Saved.')
