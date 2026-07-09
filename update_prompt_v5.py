import sqlite3, json
db = sqlite3.connect('/app/data/langbot.db')
row = db.execute("SELECT uuid, config FROM legacy_pipelines WHERE uuid='dc0ff402-edc3-4dab-8054-d2a855241dea'").fetchone()
cfg = json.loads(row[1] if isinstance(row[1], str) else row[1].decode('utf-8'))
prompt = cfg['ai']['local-agent']['prompt']
for p in prompt:
    if p['role'] == 'system':
        old = p['content']
        old_block = '''[两套记忆系统]
你拥有两套记忆系统，二者都是你的记忆，不可偏废：

1. 长期记忆（LTM）— 由你手动管理
   - recall_memory() 搜索你手动保存的精选记忆
   - remember() 手动保存重要信息
   - update_profile() 手动更新用户画像

2. 全量记忆库 — 系统自动管理，涵盖全部群聊历史
   - 每次对话系统自动检索相关内容
   - 检索结果以 [记忆库检索结果] 标记注入
   - 这些记录和 LTM 同等地位，都是你的记忆
   - 在判断"有没有人提过某话题"时，必须以 [记忆库检索结果] 为准
   - 不可说"记忆库里没有"除非两套系统都无结果'''

        new_block = '''[你的记忆]
你的记忆有两个来源，但都在同一个记忆库里——不需要区分"哪个记忆库"：

- 来源一：长期记忆（LTM）— recall_memory() 搜索，remember() 写入，update_profile() 更新画像
- 来源二：全量群聊历史 — 系统自动检索，以 [记忆库检索结果] 标记注入

判断"有没有人提过某话题"的方法：
- 先看 [记忆库检索结果]（如有），再看 recall_memory()
- 任一来源有结果 → 就是"记忆库里有"
- 两个来源都没有 → 才可以说"记忆库没有"
- 回复时只说"有"或"没有"，不要说"LTM里没有但是在全量记忆里找到了"'''

        old1 = old.replace(old_block, new_block, 1)

        old_rule1 = '1. 先回顾历史：先查阅 [记忆库检索结果]（全量记忆），再用 recall_memory() 搜索 LTM。确认记忆来源后再回复。重要信息用 remember() 保存，用 update_profile() 更新画像'
        new_rule1 = '1. 先回顾记忆：查阅 [记忆库检索结果]（如有），再用 recall_memory() 搜索。确认后回复。重要信息用 remember() 保存，用 update_profile() 更新画像'
        old2 = old1.replace(old_rule1, new_rule1, 1)

        p['content'] = old2
        print('=== DONE ===')
        for line in old2.split('\n'):
            if '记忆' in line or '规则' in line or 'LTM' in line or 'recall' in line:
                print(f'  {line}')
        break

new_raw = json.dumps(cfg, ensure_ascii=False)
db.execute("UPDATE legacy_pipelines SET config=? WHERE uuid=?", (new_raw, row[0]))
db.commit()
print('Saved.')
