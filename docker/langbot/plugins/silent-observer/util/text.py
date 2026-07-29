"""文本处理 — 文档ID、元数据、时间线、角色标准化."""
import hashlib
import time

ROLE_CN = {'OWNER': '群主', 'ADMINISTRATOR': '管理员', 'MEMBER': '成员'}


def build_document_id(session_name, time_str, sender_id, text):
    raw = f"{session_name}|{time_str}|{sender_id}|{text}"
    return f"chat:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def build_msg_metadata(session_name, sender_name, sender_id, time_str, text, sender_role, sender_title):
    label = sender_name
    if sender_title:
        label += f'[{sender_title}]'
    if sender_role and sender_role != 'MEMBER':
        label += f'({ROLE_CN.get(sender_role, sender_role)})'
    return {
        'text': f"[{time_str}] {label}: {text}",
        'sender_name': sender_name,
        'sender_id': sender_id,
        'timestamp': time_str,
        'timestamp_unix': time.time(),
        'session_id': session_name,
        'type': 'chat_history',
    }


def format_timeline(items):
    lines = []
    for item in items:
        meta = item.get('metadata', {})
        text = meta.get('text', '') or item.get('document', '')
        if not text:
            for ce in item.get('content', []) or []:
                if isinstance(ce, dict) and ce.get('type') == 'text':
                    text = ce.get('text', '')
                    break
        if text:
            lines.append(text)
    return lines


def norm_role(perm) -> str:
    if perm is None:
        return ''
    if hasattr(perm, 'value'):
        return perm.value
    return str(perm)


def clean_description(text):
    text = (text or '').strip().strip('"').strip("'")
    for prefix in ['这张图片', '图片中', '图中', 'This image', 'The image', 'Image']:
        if text.startswith(prefix):
            text = text[len(prefix):]
            text = text.lstrip('是').lstrip('展示了').lstrip('显示').lstrip()
            break
    if not text or any(kw in text for kw in ['不能描述', '无法识别', 'cannot describe', 'violates']):
        return '[图片]'
    text = text.split('\n')[0][:60]
    return f'[图片: {text}]'
