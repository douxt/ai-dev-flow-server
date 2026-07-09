import sqlite3, json
db = sqlite3.connect('/app/data/langbot.db')
row = db.execute("SELECT uuid, config FROM legacy_pipelines WHERE uuid='dc0ff402-edc3-4dab-8054-d2a855241dea'").fetchone()
uuid, cfg_raw = row
cfg = json.loads(cfg_raw if isinstance(cfg_raw, str) else cfg_raw.decode('utf-8'))
la = cfg['ai']['local-agent']
old_kbs = la.get('knowledge-bases', [])
new_kb = 'da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc'
if new_kb not in old_kbs:
    old_kbs.append(new_kb)
    la['knowledge-bases'] = old_kbs
    print(f'Added Dou KB. New list: {old_kbs}')
else:
    print('Already in list')
new_raw = json.dumps(cfg, ensure_ascii=False)
db.execute("UPDATE legacy_pipelines SET config = ? WHERE uuid = ?", (new_raw, uuid))
db.commit()
print('Saved.')
