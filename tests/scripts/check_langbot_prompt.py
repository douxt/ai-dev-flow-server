#!/usr/bin/env python3
"""查看 LangBot 侧的 prompt 结构和大小。"""
import sqlite3, json

db = sqlite3.connect('/app/data/langbot.db')

# 1. Pipeline 配置（含 system prompt）
print("=== Pipeline configs ===")
for r in db.execute("SELECT name, uuid FROM legacy_pipelines"):
    print(f"  {r[0]} ({r[1]})")

# 2. Metadata 中的 prompt 相关
print("\n=== Metadata (prompt/system related) ===")
for r in db.execute("SELECT key, length(cast(value as text)) as vlen FROM metadata WHERE key LIKE '%prompt%' OR key LIKE '%system%' OR key LIKE '%persona%'"):
    print(f"  {r[0]}: {r[1]} chars")

# 3. 最近的 monitoring_messages（可能含完整 prompt）
print("\n=== Recent monitoring_messages (last 3) ===")
for r in db.execute("""
    SELECT timestamp, role, length(message_content) as clen,
           substr(message_content, 1, 150) as preview
    FROM monitoring_messages
    WHERE bot_id = '8053e7b4-f0b7-4264-b348-abc70eaa3550'
    ORDER BY timestamp DESC LIMIT 5
"""):
    print(f"  [{r[0][:19]}] role={r[1]:8s} len={r[2]:5d}  preview={r[3][:120]}")

# 4. 最近的 LLM 调用 + 对应的消息
print("\n=== Latest LLM call -> message correlation ===")
for r in db.execute("""
    SELECT l.timestamp, l.input_tokens, l.output_tokens, l.duration, l.session_id,
           m.message_content
    FROM monitoring_llm_calls l
    LEFT JOIN monitoring_messages m ON l.message_id = m.id
    WHERE l.bot_id = '8053e7b4-f0b7-4264-b348-abc70eaa3550'
      AND l.status = 'success'
    ORDER BY l.timestamp DESC LIMIT 1
"""):
    print(f"  time={r[0][:19]} in={r[1]} out={r[2]} dur={r[3]}ms sess={r[4]}")
    if r[5]:
        content = r[5]
        # Try to parse as JSON (might be structured)
        try:
            parsed = json.loads(content)
            if isinstance(parsed, list):
                for i, msg in enumerate(parsed):
                    role = msg.get('role', '?')
                    c = msg.get('content', '')
                    if isinstance(c, list):
                        # multimodal content
                        text = ' '.join([t.get('text', '') for t in c if t.get('type') == 'text'])
                    else:
                        text = str(c)
                    print(f"    [{i}] role={role} len={len(text)}c: {text[:100]}...")
            else:
                print(f"    content preview: {str(parsed)[:200]}")
        except:
            print(f"    raw({len(content)}c): {content[:200]}")

# 5. 全部 metadata keys
print("\n=== All metadata keys ===")
for r in db.execute("SELECT key FROM metadata"):
    print(f"  {r[0]}")
