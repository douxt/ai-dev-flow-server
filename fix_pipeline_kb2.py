import sqlite3, json
db = sqlite3.connect('/app/data/langbot.db')
row = db.execute("SELECT uuid, config FROM legacy_pipelines WHERE uuid='dc0ff402-edc3-4dab-8054-d2a855241dea'").fetchone()
uuid, cfg_raw = row
cfg = json.loads(cfg_raw if isinstance(cfg_raw, str) else cfg_raw.decode('utf-8'))
la = cfg['ai']['local-agent']
old_kbs = la.get('knowledge-bases', [])
dou_kb = 'da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc'
new_kbs = [k for k in old_kbs if k != dou_kb]
la['knowledge-bases'] = new_kbs
print(f'Was: {old_kbs}')
print(f'Now: {new_kbs}')
new_raw = json.dumps(cfg, ensure_ascii=False)
db.execute("UPDATE legacy_pipelines SET config = ? WHERE uuid = ?", (new_raw, uuid))
db.commit()
print('Saved.')
