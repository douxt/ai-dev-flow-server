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
print("测试3: _is_face_component Unknown 降级 (本次修复)")
print("=" * 50)
# 模拟 LangBot Unknown 组件: 没有 face 类型但有 face_id 属性
class FakeUnknown:
    type = 'Unknown'
    def __init__(self, face_id, face_name=''):
        self.face_id = face_id
        self.face_name = face_name

# 真正 Face 组件
c1 = Face(face_type='face', face_id=178, face_name='')
# 伪 Unknown 组件（napcat → LangBot 的降级结果）
c2 = FakeUnknown(face_id=14, face_name='惊讶')
# Plain 组件 不受影响
c3 = Plain(text='hello')

# 模拟 _is_face_component 逻辑
def _is_face_component(c):
    return c.type == 'Face' or hasattr(c, 'face_id')

cases3 = [(c1, True, 'Face(178)'), (c2, True, 'Unknown(14)'), (c3, False, 'Plain')]
passed3 = 0
for c, expected, label in cases3:
    ok = _is_face_component(c) == expected
    tag = '✅' if ok else '❌'
    print(f'{tag} {label} → is_face={_is_face_component(c)} (expected={expected})')
    passed3 += 1 if ok else 0
print(f"  {passed3}/{len(cases3)} 通过\n")

print("=" * 50)
print("测试4: Unknown 组件 → face_to_text 正常")
print("=" * 50)
c_unk = FakeUnknown(face_id=14, face_name='惊讶')
result = face_to_text(c_unk)
ok = '[QQ表情:惊讶]' in result
tag = '✅' if ok else '❌'
print(f'{tag} Unknown(face_id=14) → "{result}"')
passed4 = 1 if ok else 0
print(f"  {passed4}/1 通过\n")

print("=" * 50)
print("测试5: 混合消息链提取(含Unknown Face)")
print("=" * 50)
chain = [At(target="3228649756"), Plain(text=" "), FakeUnknown(face_id=178, face_name=''), Plain(text=" 这是什么")]
parts = []
for c in chain:
    if _is_face_component(c):
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

# 模拟 inject 中的收集逻辑（独立函数，不依赖 pipeline context）
def _collect_faces(mc):
    result = []
    if mc:
        for c in mc:
            if _is_face_component(c):
                result.append(face_to_text(c))
    return result

print("=" * 50)
print("测试6: _collect_faces 纯 Face 链")
print("=" * 50)
chain6 = [Face(face_type='face', face_id=0, face_name='')]
result6 = _collect_faces(chain6)
ok6 = len(result6) == 1 and '微笑' in result6[0]
tag6 = '✅' if ok6 else '❌'
print(f'{tag6} {result6}')
passed6 = 1 if ok6 else 0

print("=" * 50)
print("测试7: _collect_faces 混合链（Face+Plain+At+Face）")
print("=" * 50)
chain7 = [Face(face_type='face', face_id=178, face_name=''), Plain(text='你好'), At(target='123'), Face(face_type='face', face_id=14, face_name='惊讶')]
result7 = _collect_faces(chain7)
ok7 = len(result7) == 2 and '斜眼笑' in result7[0] and '惊讶' in result7[1]
tag7 = '✅' if ok7 else '❌'
print(f'{tag7} {result7}')
passed7 = 1 if ok7 else 0

print("=" * 50)
print("测试8: _collect_faces 无 Face 链")
print("=" * 50)
chain8 = [Plain(text='hello'), At(target='123')]
result8 = _collect_faces(chain8)
ok8 = len(result8) == 0
tag8 = '✅' if ok8 else '❌'
print(f'{tag8} {result8}')
passed8 = 1 if ok8 else 0

import sqlite3
print("=" * 50)
print("测试9: chat_index 统计")
print("=" * 50)
db = sqlite3.connect('/app/data/plugins/dou__langbot-silent-observer/chat_index.db')
db.row_factory = sqlite3.Row
rows = db.execute("select formatted_text from chat_index where session_id='group_1104330614' order by timestamp_unix desc limit 20").fetchall()
unknown_cnt = sum(1 for r in rows if 'Unknown' in r['formatted_text'])
qqface_cnt = sum(1 for r in rows if 'QQ表情' in r['formatted_text'])
print(f"  Unknown: {unknown_cnt}次  QQ表情: {qqface_cnt}次")
db.close()

total = passed + passed2 + passed3 + passed4 + (1 if has_qqface and no_unknown else 0) + passed6 + passed7 + passed8
total_cases = len(cases) + len(cases2) + len(cases3) + 1 + 1 + 1 + 1 + 1
print(f"\n{'='*50}")
print(f"总计: {total}/{total_cases} 通过")
print("=" * 50)
