#!/usr/bin/env python3
"""直接验证 QQ 表情修复：构造 Unknown Face 组件 → normalize → 断言."""
import sys
sys.path.insert(0, '/app/.venv/lib/python3.12/site-packages')
from langbot_plugin.api.entities.builtin.platform.message import Plain, Unknown, MessageChain

# 模拟旧 bug：monkey-patch 失效，Face → Unknown
chain = MessageChain(root=[
    Unknown(text='Unknown component type: Face'),
    Unknown(text='Unknown component type: Face'),
    Plain(text='你好'),
])

sys.path.insert(0, '/app/data/plugins/dou__langbot-silent-observer')
from util.face import normalize_face_components, is_face_component, face_to_text

passed = 0
failed = 0
def t(cond, name):
    global passed, failed
    if cond: passed += 1
    else: failed += 1; print(f'FAIL: {name}')

# 1. is_face_component 检测 Unknown Face
t(is_face_component(chain.root[0]), 'is_face detects Unknown Face[0]')
t(is_face_component(chain.root[1]), 'is_face detects Unknown Face[1]')
t(not is_face_component(chain.root[2]), 'is_face ignores Plain')

# 2. face_to_text for Unknown Face
t(face_to_text(chain.root[0]) == '[QQ表情]', f'Unknown→text={face_to_text(chain.root[0])}')
t(face_to_text(chain.root[2]) == '[QQ表情]', f'Plain→text={face_to_text(chain.root[2])}')  # Plain has no face data

# 3. normalize
normalize_face_components(chain)
has_unknown_face = any(c.type == 'Unknown' and 'Face' in (c.text or '') for c in chain)
has_qq = any('[QQ表情]' in (c.text or '') for c in chain)
t(not has_unknown_face, 'no Unknown Face after normalize')
t(has_qq, 'has [QQ表情] after normalize')

# 4. 正常 Face 组件（带 face_id）
from langbot_plugin.api.entities.builtin.platform.message import Face as LangBotFace
chain2 = MessageChain(root=[
    LangBotFace(face_id=14, face_name='惊讶'),
    Plain(text='测试'),
])
t(is_face_component(chain2.root[0]), 'real Face detected')
t(face_to_text(chain2.root[0]) == '[QQ表情:惊讶]', f'real Face→text={face_to_text(chain2.root[0])}')
normalize_face_components(chain2)
has_qq2 = any('[QQ表情:惊讶]' in (c.text or '') for c in chain2)
t(has_qq2, 'real Face → [QQ表情:惊讶] after normalize')

print(f'PASS={passed} FAIL={failed}')
sys.exit(0 if failed == 0 else 1)
