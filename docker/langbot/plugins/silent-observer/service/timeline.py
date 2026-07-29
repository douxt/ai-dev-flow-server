"""时间线构建服务 — 消息链→文本 + timeline 格式化/去重/截断/图片标记增强."""
import asyncio
import re

from util.face import is_face_component, face_to_text


class TimelineService:
    def __init__(self, timeline_max_chars: int = 2000, history_count: int = 20):
        self.timeline_max_chars = timeline_max_chars
        self.history_count = history_count

    async def extract_text(self, message_chain, max_length: int = 300,
                           image_descriptions: dict | None = None, depth: int = 0) -> str:
        """递归提取消息链文本（含 Face/Forward/Quote/Image 处理）"""
        if message_chain is None:
            return ''
        if depth > 5:
            return '[引用链过长]'
        if image_descriptions is None:
            image_descriptions = {}

        chain_types = [c.type for c in message_chain]
        if chain_types == ['Source']:
            return ''

        parts = []
        for c in message_chain:
            if isinstance(c, str):
                parts.append(c)
                continue
            ctype = getattr(c, 'type', '')
            if ctype == 'Plain':
                parts.append(getattr(c, 'text', ''))
            elif is_face_component(c):
                parts.append(face_to_text(c))
            elif ctype == 'Image':
                desc = image_descriptions.get(len(parts), '')
                parts.append(desc if desc else '[图片]')
            elif ctype == 'At':
                parts.append('')
            elif ctype == 'Quote':
                origin = getattr(c, 'origin', None)
                if origin is not None:
                    inner = await self.extract_text(origin, max_length, image_descriptions, depth + 1)
                    if inner:
                        parts.append(f'[引用: {inner}]')
            elif ctype == 'Forward':
                nodes = getattr(c, 'node_list', []) or []
                for node in nodes:
                    mc = getattr(node, 'message_chain', None)
                    if mc is not None:
                        forward_text = await self.extract_text(mc, max_length, image_descriptions, depth + 1)
                        if forward_text:
                            parts.append(forward_text)
            elif ctype == 'File':
                parts.append('[文件]')
            else:
                if hasattr(c, 'text') and c.text:
                    parts.append(c.text)

        text = ' '.join(p for p in parts if p).strip()
        if len(text) > max_length:
            text = text[:max_length]
        return text

    def enhance_image_markers(self, lines: list[str]) -> tuple[list[str], int, int, int]:
        """强化 timeline 中图片识别标记，返回 (lines, identified, pending, failed)"""
        identified = 0
        pending = 0
        failed = 0
        for i, line in enumerate(lines):
            if '🖼️ 图' not in line:
                continue
            idx = line.index('🖼️ 图')
            pfx = line[:idx]
            rest = line[idx:]
            if '：⏳ 识别中' in rest:
                lines[i] = pfx + rest.replace('🖼️ 图', '⏳ [AI识图中] 图', 1)
                pending += 1
            else:
                m = re.match(r'🖼️ 图\d+：\[图片([^\]]*)\]', rest)
                if m:
                    img_prefix = rest[:rest.index('：')]
                    desc = m.group(1).strip()
                    if desc.startswith('('):
                        reason = desc.strip('()')
                        lines[i] = pfx + rest.replace('🖼️ 图', f'❌ [AI识图失败:{reason}] 图', 1)
                        failed += 1
                    else:
                        img_prefix_new = img_prefix.replace('🖼️ 图', '🤖 [AI识图] 图', 1)
                        after = rest[len(f'{img_prefix}：[图片{desc}]'):]
                        lines[i] = pfx + f'{img_prefix_new}：[{desc}]' + after
                        identified += 1
        return lines, identified, pending, failed

    def deduplicate(self, lines: list[str]) -> list[str]:
        """连续相同 bot 消息只保留第一条（防 relay 重复污染）"""
        deduped = []
        for line in lines:
            if not deduped or line != deduped[-1]:
                deduped.append(line)
        return deduped

    def truncate_by_chars(self, lines: list[str]) -> list[str]:
        """从最旧开始丢弃，直到总字符数 <= timeline_max_chars"""
        total_chars = sum(len(l) for l in lines)
        while lines and total_chars > self.timeline_max_chars:
            total_chars -= len(lines.pop(0))
        return lines
