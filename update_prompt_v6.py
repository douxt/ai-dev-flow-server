import sqlite3, json
db = sqlite3.connect('/app/data/langbot.db')
row = db.execute("SELECT uuid, config FROM legacy_pipelines WHERE uuid='dc0ff402-edc3-4dab-8054-d2a855241dea'").fetchone()
cfg = json.loads(row[1] if isinstance(row[1], str) else row[1].decode('utf-8'))
prompt = cfg['ai']['local-agent']['prompt']
for p in prompt:
    if p['role'] == 'system':
        old = p['content']
        old_block = '''[你的记忆]
你的记忆有两个来源，但都在同一个记忆库里——不需要区分"哪个记忆库"：

- 来源一：长期记忆（LTM）— recall_memory() 搜索，remember() 写入，update_profile() 更新画像
- 来源二：全量群聊历史 — 系统自动检索，以 [记忆库检索结果] 标记注入

判断"有没有人提过某话题"的方法：
- 先看 [记忆库检索结果]（如有），再看 recall_memory()
- 任一来源有结果 → 就是"记忆库里有"
- 两个来源都没有 → 才可以说"记忆库没有"
- 回复时只说"有"或"没有"，不要说"LTM里没有但是在全量记忆里找到了"'''

        new_block = '''[记忆库（LTM）]
你的长期记忆，由你手动管理：
- recall_memory() 搜索已保存的记忆
- remember() 手动保存重要信息
- update_profile() 手动更新用户画像

[群聊历史检索]
系统自动从全部群聊记录中检索相关内容，以 [群聊历史检索] 标记注入到对话中。这些是早期聊天记录的搜索结果，可用于回答"之前有没有人提过XX"类问题。

判断"有没有人提过某话题"时：
- 先看 [群聊历史检索] 的结果，再用 recall_memory() 查记忆库
- 两者任一有结果 → 直接告知用户
- 两者都没有 → 才可以说没有'''

        old1 = old.replace(old_block, new_block, 1)

        old_rule1 = '1. 先回顾记忆：查阅 [记忆库检索结果]（如有），再用 recall_memory() 搜索。确认后回复。重要信息用 remember() 保存，用 update_profile() 更新画像'
        new_rule1 = '1. 先回顾：查阅 [群聊历史检索]（如有），再用 recall_memory() 搜索记忆库。确认后回复'
        old2 = old1.replace(old_rule1, new_rule1, 1)

        p['content'] = old2
        print('Saved.')
        break

new_raw = json.dumps(cfg, ensure_ascii=False)
db.execute("UPDATE legacy_pipelines SET config=? WHERE uuid=?", (new_raw, row[0]))
db.commit()
