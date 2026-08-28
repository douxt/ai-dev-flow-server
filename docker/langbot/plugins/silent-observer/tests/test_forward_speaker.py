"""转发说话人归属测试——extract_text Forward 归属前缀 + _save_text_only 展开链联动"""
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from conftest import FakePlain, FakeImage, FakeQuote, FakeForward, FakeForwardNode  # noqa: E402


# SDK mock 由 autouse fixture 运行时注入，业务模块禁止 collection 期顶层 import


def _node(name=None, sid='', texts=('内容甲',), chain=None):
    return FakeForwardNode(
        message_chain=chain if chain is not None else [FakePlain(text=t) for t in texts],
        sender_name=name or '', sender_id=sid)


@pytest.fixture
def tl():
    from service.timeline import TimelineService
    return TimelineService(2000, 20)


class TestExtractForward:

    async def test_single_node_sender_prefix(self, tl):
        fwd = FakeForward(node_list=[_node('怪异的萌', '111', ('我帕萨特不烧机油',))])
        out = await tl.extract_text([fwd])
        assert '[怪异的萌] 我帕萨特不烧机油' in out

    async def test_multi_nodes_attributed(self, tl):
        fwd = FakeForward(node_list=[
            _node('怪异的萌', '111', ('我车不烧',)),
            _node('小邋遢', '222', ('EA888必修',)),
        ])
        out = await tl.extract_text([fwd])
        i1, i2 = out.index('[怪异的萌]'), out.index('[小邋遢]')
        assert i1 < i2
        # 归属前缀独立成段：小邋遢头前是换行（join 不粘连上一节点文本）
        assert '\n[小邋遢]' in out

    async def test_fallback_to_sender_id(self, tl):
        fwd = FakeForward(node_list=[_node(None, '999', ('x',))])
        out = await tl.extract_text([fwd])
        assert '[999] x' in out

    async def test_fallback_to_question(self, tl):
        fwd = FakeForward(node_list=[_node(None, '', ('y',))])
        out = await tl.extract_text([fwd])
        assert '[?] y' in out

    async def test_nested_forward_attributed(self, tl):
        inner = FakeForward(node_list=[_node('内层甲', '333', ('z',))])
        fwd = FakeForward(node_list=[_node(None, '', chain=[inner])])
        out = await tl.extract_text([fwd])
        assert '[内层甲] z' in out

    async def test_plain_path_regression(self, tl):
        out = await tl.extract_text([FakePlain(text='普通消息'), FakePlain(text='第二条')])
        assert out == '普通消息 第二条'

    async def test_quote_with_patched_origin_regression(self, tl):
        # 宿主 1a 补丁后 Quote.origin 首元素为归属头 Plain——插件拼入 [引用: ...] 无异常
        origin = [FakePlain(text='[喵酱 08-24 02:55]'), FakePlain(text='我车不烧')]
        out = await tl.extract_text([FakeQuote(origin=origin)])
        assert out.startswith('[引用: ') and '我车不烧' in out


class TestSaveTextOnlyWithForward:
    """P1.5 联动：宿主 1b 修复后 chain=['Source','Forward'] 不再误入 forward-only 早退"""

    def _event(self, chain):
        return SimpleNamespace(
            message_chain=chain, sender_id='u9', message_event=None,
            launcher_type='group', launcher_id='g1', text_message='')

    async def test_expanded_forward_stores_content(self, reflection_listener, log_dir):
        listener = reflection_listener
        listener.kb_enabled = False
        fwd = FakeForward(node_list=[_node('甲', '1', ('A 内容',)), _node('乙', '2', ('B 内容',))])
        event = self._event([SimpleNamespace(type='Source', id=1, time=None), fwd])
        doc_id = await listener._save_text_only(event)
        assert doc_id is not None
        gate_log = (log_dir / 'silent_gate.log').read_text() if (log_dir / 'silent_gate.log').exists() else ''
        assert 'forward-only' not in gate_log

    async def test_source_only_still_placeholder(self, reflection_listener, log_dir):
        listener = reflection_listener
        listener.kb_enabled = False
        event = self._event([SimpleNamespace(type='Source', id=1, time=None)])
        await listener._save_text_only(event)
        gate_log = (log_dir / 'silent_gate.log').read_text()
        assert 'forward-only (Source only)' in gate_log
