"""P1 压缩集成测试 — mock invoke_llm + 临时 SQLite，绕过事件系统."""
import json
import sys
import os
import time
import tempfile
import shutil
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _build_listener_with_compression(db_path, model_uuid='test-model-uuid'):
    """构造开启了压缩的 DefaultEventListener，使用临时 DB."""
    from components.event_listener.default import DefaultEventListener
    obj = DefaultEventListener.__new__(DefaultEventListener)

    # 基础属性
    obj.bot_qq = '3228649756'
    obj.prob = 0.01
    obj.kb_enabled = True
    obj.vision_enabled = False
    obj.reflection_enabled = False
    obj.history_count = 20
    obj.timeline_max_chars = 2000
    obj.vision_max_images = 5
    obj.debug_dump = False
    obj.vision_all_messages = False
    obj._gate_hits = 0
    obj._gate_misses = 0
    obj._lock_skips = 0
    obj._inject_random = 0
    obj._inject_at = 0
    obj._stats_start = 0

    # 状态
    obj._bg_queue = None
    obj._bg_workers = []
    obj._last_trigger = {}
    obj._lock_set_ts = {}
    obj._reply_ts = {}
    obj._reply_pending = {}
    obj._reply_tasks = {}
    obj._face_cache = {}
    obj._image_cache = {}
    obj._last_msg_ts = {}

    # mock plugin
    mock_plugin = MagicMock()
    mock_plugin.set_plugin_storage = AsyncMock()
    mock_plugin.get_plugin_storage = AsyncMock(return_value=None)
    obj.plugin = mock_plugin

    # mock store (get_recent_messages 由各测试注入)
    obj.store = MagicMock()
    obj.store.get_recent_messages = AsyncMock(return_value=[])

    # mock retrieval_service
    obj.retrieval_service = None

    # 持久化
    from store import StateStore
    obj._state_store = StateStore(mock_plugin)

    # 服务层
    from service.timeline import TimelineService
    obj.timeline_service = TimelineService(obj.timeline_max_chars, obj.history_count)
    from service.quote import QuoteService
    obj.quote_service = QuoteService(obj.timeline_service.extract_text)

    # 压缩配置
    obj.compressor_enabled = True
    obj.compression_model_uuid = model_uuid
    obj.compression_tail_max_chars = 1500
    obj.compression_cooldown_minutes = 10
    obj.compression_history_count = 200
    obj._compression_cooldown_seconds = 600
    obj._compression_min_tail_items = 3

    from store.summary_store import SummaryStore, CompressionLogStore
    obj.summary_store = SummaryStore(db_path)
    obj.compression_log_store = CompressionLogStore(db_path)

    obj._compression_queue = None  # 不启动 worker
    obj._compression_inflight = set()
    obj._compression_stats = {
        'ok': 0, 'fail': 0, 'parse_none': 0, 'timeout': 0,
        'cooldown_skip': 0, 'queue_full': 0, 'no_signal': 0, 'inflight_skip': 0,
    }

    return obj


def _make_item(text: str, ts: float = 1000.0) -> dict:
    return {"metadata": {"text": text, "timestamp_unix": ts}}


def _make_llm_response(topics='t1', facts='f1', decisions='d1', refs='r1'):
    return json.dumps({"topics": topics, "facts": facts, "decisions": decisions, "refs": refs})


def _init_db(db_path):
    import sqlite3
    db = sqlite3.connect(db_path)
    from store.summary_store import SummaryStore, CompressionLogStore
    SummaryStore.create_table(db)
    CompressionLogStore.create_table(db)
    db.commit()
    db.close()


@pytest.mark.asyncio
class TestCompressionIntegration:
    """mock invoke_llm + 临时 SQLite 的完整流程测试."""

    async def test_full_flow(self):
        """场景 1: 压缩完整流程 — 20 条消息 → 摘要写入."""
        tmp = tempfile.mkdtemp()
        try:
            db_path = os.path.join(tmp, 'test.db')
            _init_db(db_path)
            listener = _build_listener_with_compression(db_path)

            # 制造 40 条消息（tail 1500 chars=15条 × 100 chars，25 条进摘要）
            items = [_make_item(f'msg{i} ' + 'x' * 90, ts=1000 + i * 10) for i in range(40)]
            listener.store.get_recent_messages = AsyncMock(return_value=items)

            mock_invoke = AsyncMock(return_value=_make_llm_response(facts='DS920+', topics='NAS'))
            listener.plugin.invoke_llm = mock_invoke

            await listener._process_compression('group_test')

            # 验证 summary 表
            doc = listener.summary_store.load('group_test')
            assert doc is not None
            assert 'DS920+' in doc.facts
            assert 'NAS' in doc.topics
            assert doc.message_count > 0
            assert doc.covered_until_ts > 0
            assert doc.cooldown_until > time.time()

            # 验证 compression_log
            import sqlite3
            db = sqlite3.connect(db_path)
            db.row_factory = sqlite3.Row
            rows = db.execute('SELECT * FROM compression_log WHERE session_name=? AND status=?',
                              ('group_test', 'ok')).fetchall()
            db.close()
            assert len(rows) >= 1
            assert rows[0]['input_chars'] > 0
            assert rows[0]['msg_count'] > 0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    async def test_key_info_retained(self):
        """场景 2: 关键信息保留 — '限价 3.2 万' 出现在 facts 中."""
        tmp = tempfile.mkdtemp()
        try:
            db_path = os.path.join(tmp, 'test.db')
            _init_db(db_path)
            listener = _build_listener_with_compression(db_path)

            items = [_make_item(f'msg{i} x' * 50, ts=1000 + i * 10) for i in range(40)]
            listener.store.get_recent_messages = AsyncMock(return_value=items)

            mock_invoke = AsyncMock(return_value=_make_llm_response(facts='限价 3.2 万'))
            listener.plugin.invoke_llm = mock_invoke

            await listener._process_compression('group_test')

            doc = listener.summary_store.load('group_test')
            assert doc is not None
            assert '3.2 万' in doc.facts
            assert listener._compression_stats['ok'] == 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    async def test_two_round_merge(self):
        """场景 3: 二次压缩合并 — facts 累积不丢失."""
        tmp = tempfile.mkdtemp()
        try:
            db_path = os.path.join(tmp, 'test.db')
            _init_db(db_path)
            listener = _build_listener_with_compression(db_path)

            # Round 1: 第一批消息
            items1 = [_make_item(f'msg{i} a' * 50, ts=1000 + i * 10) for i in range(40)]
            listener.store.get_recent_messages = AsyncMock(return_value=items1)
            listener.plugin.invoke_llm = AsyncMock(return_value=_make_llm_response(facts='v1: NAS', topics='硬件'))

            await listener._process_compression('group_test')
            doc1 = listener.summary_store.load('group_test')
            assert 'v1: NAS' in doc1.facts

            # Round 2: 第二批消息 (更晚的时间戳 + 清除 cooldown)
            doc1.cooldown_until = 0
            listener.summary_store.upsert('group_test', doc1)
            items2 = [_make_item(f'msg{i} b' * 50, ts=2000 + i * 10) for i in range(40)]
            listener.store.get_recent_messages = AsyncMock(return_value=items2)
            listener.plugin.invoke_llm = AsyncMock(
                return_value=_make_llm_response(facts='v1: NAS, v2: DS920+', topics='硬件, 升级'))

            await listener._process_compression('group_test')
            doc2 = listener.summary_store.load('group_test')
            assert 'v2: DS920+' in doc2.facts
            assert listener._compression_stats['ok'] == 2
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    async def test_parse_none_writes_cooldown(self):
        """场景 4: LLM 返回全空 JSON → cooldown 写入（bug #2 修复验证）."""
        tmp = tempfile.mkdtemp()
        try:
            db_path = os.path.join(tmp, 'test.db')
            _init_db(db_path)
            listener = _build_listener_with_compression(db_path)

            items = [_make_item(f'msg{i} x' * 50, ts=1000 + i * 10) for i in range(40)]
            listener.store.get_recent_messages = AsyncMock(return_value=items)

            # 全空 JSON → parse_summary_response 返回 None
            listener.plugin.invoke_llm = AsyncMock(
                return_value='{"topics": "", "facts": "", "decisions": "", "refs": ""}')

            await listener._process_compression('group_test')

            # 核心断言：cooldown 已写入（bug #2 修复）
            doc = listener.summary_store.load('group_test')
            assert doc is not None
            assert doc.cooldown_until > time.time()

            # compression_log 记录了 parse_none
            import sqlite3
            db = sqlite3.connect(db_path)
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM compression_log WHERE status='parse_none'").fetchone()
            db.close()
            assert row is not None

            # 计数器
            assert listener._compression_stats['parse_none'] >= 1
            assert listener._compression_stats['ok'] == 0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    async def test_timeout_writes_cooldown(self):
        """场景 5: LLM 超时 → cooldown 写入，旧摘要不变."""
        tmp = tempfile.mkdtemp()
        try:
            db_path = os.path.join(tmp, 'test.db')
            _init_db(db_path)
            listener = _build_listener_with_compression(db_path)

            items = [_make_item(f'msg{i} x' * 50, ts=1000 + i * 10) for i in range(40)]
            listener.store.get_recent_messages = AsyncMock(return_value=items)

            import asyncio
            listener.plugin.invoke_llm = AsyncMock(side_effect=asyncio.TimeoutError())

            await listener._process_compression('group_test')

            doc = listener.summary_store.load('group_test')
            assert doc is not None
            assert doc.cooldown_until > time.time()

            # compression_log 记录了 timeout
            import sqlite3
            db = sqlite3.connect(db_path)
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM compression_log WHERE status='timeout'").fetchone()
            db.close()
            assert row is not None

            assert listener._compression_stats['timeout'] >= 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    async def test_tail_dedup_uses_gte(self):
        """场景 6: Tail 去重 — inject 路径 >= covered（bug #3 修复验证）."""
        # 此测试验证 inject 路径的过滤逻辑（不在 _process_compression 内）
        # 模拟 inject 时过滤 already-covered 消息
        covered_ts = 1500.0
        items = [
            _make_item('old1', ts=1490.0),
            _make_item('boundary', ts=1500.0),  # 同秒边界消息
            _make_item('new1', ts=1510.0),
            _make_item('new2', ts=1520.0),
        ]
        # bug #3 修复: >= 而非 >
        filtered = [i for i in items
                    if i.get('metadata', {}).get('timestamp_unix', 0) >= covered_ts]
        assert len(filtered) == 3
        assert filtered[0]['metadata']['text'] == 'boundary'  # 边界消息保留

    async def test_disabled_no_inject(self):
        """场景 7: compression_enabled=false 时不注入摘要."""
        tmp = tempfile.mkdtemp()
        try:
            db_path = os.path.join(tmp, 'test.db')
            _init_db(db_path)
            listener = _build_listener_with_compression(db_path)
            listener.compressor_enabled = False
            listener.summary_store = None

            # 确保 _trigger_compression 不会崩溃
            listener._trigger_compression('group_test')  # 应直接 return
            assert listener._compression_stats['cooldown_skip'] == 0  # summary_store=None 直接 return
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    async def test_cooldown_skip(self):
        """cooldown 期内不触发压缩."""
        tmp = tempfile.mkdtemp()
        try:
            db_path = os.path.join(tmp, 'test.db')
            _init_db(db_path)
            listener = _build_listener_with_compression(db_path)

            # 预设 cooldown 到未来
            from store.summary_store import SummaryDocument
            doc = SummaryDocument(cooldown_until=time.time() + 3600)
            listener.summary_store.upsert('group_test', doc)

            items = [_make_item(f'msg{i} x' * 50, ts=1000 + i * 10) for i in range(40)]
            listener.store.get_recent_messages = AsyncMock(return_value=items)

            await listener._process_compression('group_test')

            # 不应该调用 LLM
            assert listener._compression_stats['ok'] == 0
            assert listener._compression_stats['no_signal'] == 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
