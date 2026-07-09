import sqlite3, json
db = sqlite3.connect('/app/data/langbot.db')
row = db.execute("SELECT uuid, config FROM legacy_pipelines WHERE uuid='dc0ff402-edc3-4dab-8054-d2a855241dea'").fetchone()
cfg = json.loads(row[1] if isinstance(row[1], str) else row[1].decode('utf-8'))
prompt = cfg['ai']['local-agent']['prompt']
for p in prompt:
    if p['role'] == 'system':
        old = p['content']
        # 替换记忆系统段
        old_memory = '''[两套记忆系统]
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
   - 注意：这些记录是你的记忆的一部分，必须引用，不可否认其中存在的内容'''

        new_memory = '''[两套记忆系统]
你有两套独立的记忆系统：

1. 长期记忆（LTM）— 由你主动管理
   - recall_memory() 搜索你手动保存的精选记忆
   - remember() 保存重要信息
   - update_profile() 更新用户画像

2. 全量记忆库 — 系统自动注入，涵盖全部群聊历史
   - 对话中如出现 [记忆库检索结果] 标记，其中的记录即为你的记忆
   - 在判断"是否有人提过某话题"时，必须先查阅 [记忆库检索结果]，再查 LTM
   - 不可说"记忆库里没有"除非两套系统都没有'''

        old1 = old.replace(old_memory, new_memory, 1)

        # 改规则1：明确引用两套记忆
        old_rule1 = '1. 先回顾历史，用 recall_memory() 搜索相关记忆、用 update_profile() 更新用户画像、用 remember() 保存重要信息，再回复'
        new_rule1 = '1. 先回顾历史：查看 [记忆库检索结果]（如有），再用 recall_memory() 搜索 LTM，用 update_profile() 更新画像，用 remember() 保存重要信息。确认记忆来源后再回复'
        old2 = old1.replace(old_rule1, new_rule1, 1)

        p['content'] = old2
        print('=== UPDATED ===')
        for line in old2.split('\n'):
            if '记忆' in line or '规则' in line:
                print(line)
        break

new_raw = json.dumps(cfg, ensure_ascii=False)
db.execute("UPDATE legacy_pipelines SET config=? WHERE uuid=?", (new_raw, row[0]))
db.commit()
print('\nSaved.')
