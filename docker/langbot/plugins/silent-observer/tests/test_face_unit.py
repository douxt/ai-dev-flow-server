#!/usr/bin/env python3
"""Face 识别单元测试 - 直接在 langbot-plugin 容器内运行，不依赖 QQ"""
import sys, asyncio, json

sys.path.insert(0, '/app/data/plugins/dou__langbot-silent-observer')
from components.event_listener.default import _QQ_FACE_NAME

print("=" * 50)
print("测试1: _QQ_FACE_NAME 映射表")
print("=" * 50)
cases = [(0,'微笑'),(3,'发呆'),(14,'惊讶'),(178,'斜眼笑'),(264,'捂脸'),(277, None)]
passed = 0
for fid, expected in cases:
    result = _QQ_FACE_NAME.get(fid)
    ok = result == expected if expected else result is None
    tag = '✅' if ok else '❌'
    print(f'{tag} face_id={fid} → "{result}"')
    passed += 1 if ok else 0
print(f"  {passed}/{len(cases)} 通过\n")

from langbot_plugin.api.entities.builtin.platform.message import Face, Plain, At

def face_to_text(c):
    name = getattr(c, 'face_name', '') or _QQ_FACE_NAME.get(getattr(c, 'face_id', 0), '')
    if name:
        return f'[QQ表情:{name}]'
    return f'[QQ表情:{getattr(c, "face_id", "?")}]'

print("=" * 50)
print("测试2: Face组件 → 文本")
print("=" * 50)
cases2 = [(178, '', '斜眼笑'), (264, '[捂脸]', '捂脸'), (3, '', '发呆'), (277, '[汪汪]', '[汪汪]')]
passed2 = 0
for fid, fname, expected_in in cases2:
    c = Face(face_type='face', face_id=fid, face_name=fname)
    our = face_to_text(c)
    ok = expected_in in our and bool(our.strip())
    tag = '✅' if ok else '❌'
    print(f'{tag} id={fid} name="{fname}" → "{our}" (sys: {str(c)})')
    passed2 += 1 if ok else 0
print(f"  {passed2}/{len(cases2)} 通过\n")

print("=" * 50)
print("测试3: 混合消息链提取")
print("=" * 50)
chain = [At(target="3228649756"), Plain(text=" "), Face(face_type='face', face_id=178, face_name=''), Plain(text=" 这是什么")]
parts = []
for c in chain:
    if c.type == 'Face':
        parts.append(face_to_text(c))
    elif c.type == 'Plain':
        parts.append(getattr(c, 'text', ''))
    elif c.type == 'At':
        parts.append(f'@{getattr(c, "target", "")}')
text = ' '.join(parts).strip()
has_qqface = '[QQ表情:斜眼笑]' in text
no_unknown = '[Unknown]' not in text
tag = '✅' if has_qqface and no_unknown else '❌'
print(f'{tag} "{text}"')
print(f"  QQ表情:{has_qqface} 无Unknown:{no_unknown}\n")

import sqlite3
print("=" * 50)
print("测试4: chat_index 统计")
print("=" * 50)
db = sqlite3.connect('/app/data/plugins/dou__langbot-silent-observer/chat_index.db')
db.row_factory = sqlite3.Row
rows = db.execute("select formatted_text from chat_index where session_id='group_1104330614' order by timestamp_unix desc limit 20").fetchall()
unknown_cnt = sum(1 for r in rows if 'Unknown' in r['formatted_text'])
qqface_cnt = sum(1 for r in rows if 'QQ表情' in r['formatted_text'])
print(f"  Unknown: {unknown_cnt}次  QQ表情: {qqface_cnt}次")
db.close()

print(f"\n{'='*50}")
print(f"总计: {passed+passed2+(1 if has_qqface and no_unknown else 0)}/{len(cases)+len(cases2)+1} 通过")
print("=" * 50)
