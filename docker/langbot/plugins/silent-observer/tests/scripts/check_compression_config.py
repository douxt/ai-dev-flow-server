import sqlite3, json
db = sqlite3.connect('/app/data/langbot.db')
row = db.execute(
    "SELECT config FROM plugin_settings "
    "WHERE plugin_author='dou' AND plugin_name='langbot-silent-observer'"
).fetchone()
cfg = json.loads(row[0])
print(f"compression_enabled = {cfg.get('compression_enabled')}")
print(f"compression_model_uuid = {cfg.get('compression_model_uuid')}")
db.close()
