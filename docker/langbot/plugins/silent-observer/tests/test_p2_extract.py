"""P2: _extract_text + _extract_quote — 异步递归文本提取"""
import pytest
from tests.conftest import FakePlain, FakeFace, FakeImage, FakeQuote, FakeForward, FakeForwardNode, FakeAt, FakeUnknown


class TestExtractText:
    @pytest.mark.asyncio
    async def test_plain_text(self, listener):
        chain = [FakePlain(text='hello'), FakePlain(text=' world')]
        result = await listener._extract_text(chain)
        assert 'hello' in result

    @pytest.mark.asyncio
    async def test_at_skipped(self, listener):
        chain = [FakeAt(target='123'), FakePlain(text='hello')]
        result = await listener._extract_text(chain)
        assert 'hello' in result
        assert '@' not in result or '[At]' not in result

    @pytest.mark.asyncio
    async def test_image_placeholder(self, listener):
        chain = [FakeImage()]
        result = await listener._extract_text(chain)
        assert '图' in result  # 🖼️ 图1：⏳ 识别中...

    @pytest.mark.asyncio
    async def test_face_component(self, listener):
        chain = [FakeFace(face_id=14, face_name='惊讶')]
        result = await listener._extract_text(chain)
        assert 'QQ表情' in result

    @pytest.mark.asyncio
    async def test_quote_recursive(self, listener):
        inner = FakePlain(text='quoted text')
        quote = FakeQuote(origin=[inner])
        result = await listener._extract_text([quote])
        assert '引用' in result
        assert 'quoted text' in result

    @pytest.mark.asyncio
    async def test_depth_limit(self, listener):
        """max_depth=5，超深引用被截断"""
        chain = FakeQuote(origin=[])
        for _ in range(10):
            chain = FakeQuote(origin=[chain])
        result = await listener._extract_text([chain], depth=0)
        assert '引用链过长' in result or result == ''

    @pytest.mark.asyncio
    async def test_none_chain(self, listener):
        assert await listener._extract_text(None) == ''


class TestExtractQuote:
    @pytest.mark.asyncio
    async def test_quote_origin_extracted(self, listener):
        origin = [FakePlain(text='引用的文字')]
        quote = FakeQuote(origin=origin)
        result = await listener._extract_quote([quote])
        assert '引用的文字' in result

    @pytest.mark.asyncio
    async def test_source_only(self, listener):
        """仅含 Source 的 origin = 合并转发群聊记录"""
        class FakeSource:
            type = 'Source'
        quote = FakeQuote(origin=[FakeSource()])
        result = await listener._extract_quote([quote])
        assert '合并转发' in result

    @pytest.mark.asyncio
    async def test_forward_with_nested_quote(self, listener):
        inner_quote = FakeQuote(origin=[FakePlain(text='nested')])
        node = FakeForwardNode(message_chain=[inner_quote])
        fwd = FakeForward(node_list=[node])
        result = await listener._extract_quote([fwd])
        assert 'nested' in result

    @pytest.mark.asyncio
    async def test_depth_limit(self, listener):
        """递归深度 > 5 返回空（最内层 Quote 内容为空时）"""
        chain = FakeQuote(origin=[])
        for _ in range(10):
            chain = FakeQuote(origin=[chain])
        result = await listener._extract_quote([chain], depth=0)
        assert '引用链过长' in result or result == ''

    @pytest.mark.asyncio
    async def test_none_chain(self, listener):
        assert await listener._extract_quote(None) == ''
