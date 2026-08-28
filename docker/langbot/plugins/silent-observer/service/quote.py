"""引用解析服务 — 递归提取引用文本 + 引用图片检测."""
import asyncio
import re

# 宿主 1a 展平产生的归属头 [nick MM-DD HH:MM]，可能成串出现
_FWD_HEAD = re.compile(r'(?:^|\s)\[[^\]\n]+ \d\d-\d\d \d\d:\d\d\]')


class QuoteService:
    def __init__(self, extract_text_callback):
        """extract_text_callback: async (message_chain, max_length, image_descriptions, depth) -> str"""
        self._extract_text = extract_text_callback

    def has_image(self, message_chain) -> bool:
        """轻量同步检查：引用中是否包含 [图片] 占位（不调 API，不阻塞事件循环）"""
        if message_chain is None:
            return False
        for c in message_chain:
            if c.type == 'Quote':
                origin = getattr(c, 'origin', None)
                if origin is not None and hasattr(origin, '__iter__'):
                    for x in origin:
                        if getattr(x, 'type', '') == 'Image':
                            return True
        return False

    async def extract(self, message_chain, depth: int = 0) -> str:
        """从 message_chain 的 Quote 组件提取引用文本（含 yield 点 + 深度限制）"""
        if message_chain is None:
            return ''
        if depth > 5:
            return ''
        for i, c in enumerate(message_chain):
            if i > 0 and i % 10 == 0:
                await asyncio.sleep(0)
            if c.type == 'Quote':
                origin = getattr(c, 'origin', None)
                if origin is not None:
                    origin_types = [x.type for x in (origin if hasattr(origin, '__iter__') else [])]
                    has_fwd = 'Forward' in origin_types
                    if origin_types == ['Source']:
                        return '[转发消息（内容未展开）]'
                    inner = await self._extract_text(origin, 300, depth=1)
                    if inner and not _FWD_HEAD.sub('', inner).strip():
                        inner = ''  # 只剩归属头（正文组件提取失败），回退占位判定
                    if has_fwd:
                        return f'[转发消息] {inner}' if inner else '[转发消息（内容未展开）]'
                    if not inner and origin_types:
                        return '[转发消息（内容未展开）]'
                    return inner
            elif c.type == 'Forward':
                nodes = getattr(c, 'node_list', []) or []
                for ni, node in enumerate(nodes):
                    if ni > 0 and ni % 5 == 0:
                        await asyncio.sleep(0)
                    mc = getattr(node, 'message_chain', None)
                    if mc is not None:
                        result = await self.extract(mc, depth + 1)
                        if result:
                            return result
        return ''
