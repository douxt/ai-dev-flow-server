"""步骤 4：持久化测试 — StateStore + _collect_state / _restore_state."""
import json
from datetime import date, datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

BJT = timezone(timedelta(hours=8))


class TestStateCollect:
    """_collect_state() 序列化测试"""

    def test_collect_all_fields(self, listener):
        listener._vision_daily_count = 5
        listener._vision_daily_date = date(2026, 7, 29)
        listener._vision_fail_streak = 3
        listener._vision_circuit_open_until = 1234567890.5
        listener._vision_stats = {'total': 10, 'success': 7, 'fail': 3, 'total_tokens': 500}
        listener._last_trigger = {'g1': ('at', 'doc1', 'mc_obj')}
        listener._lock_set_ts = {'g1': 1000.0}
        listener._reply_ts = {'g1': 2000.0}
        listener._last_msg_ts = {'g1': 3000.0}
        listener._gate_hits = 42
        listener._gate_misses = 100
        listener._lock_skips = 3
        listener._inject_random = 10
        listener._inject_at = 32
        listener._stats_start = 99999.0

        state = listener._collect_state()

        assert state['vision_daily_count'] == 5
        assert state['vision_daily_date'] == '2026-07-29'
        assert state['vision_fail_streak'] == 3
        assert state['vision_circuit_open_until'] == 1234567890.5
        assert state['vision_stats'] == {'total': 10, 'success': 7, 'fail': 3, 'total_tokens': 500}
        assert state['gate_hits'] == 42
        assert state['gate_misses'] == 100
        assert state['lock_skips'] == 3
        assert state['inject_random'] == 10
        assert state['inject_at'] == 32
        assert state['stats_start'] == 99999.0

    def test_collect_strips_message_chain(self, listener):
        """_last_trigger 的 message_chain 不可序列化，必须剥离"""
        listener._last_trigger = {'s1': ('at', 'doc123', object())}
        state = listener._collect_state()
        assert state['last_trigger'] == {'s1': ['at', 'doc123']}

    def test_collect_empty_state(self, listener):
        state = listener._collect_state()
        assert state['gate_hits'] == 0
        assert state['last_trigger'] == {}
        assert state['lock_set_ts'] == {}

    def test_collect_none_date(self, listener):
        listener._vision_daily_date = None
        state = listener._collect_state()
        assert state['vision_daily_date'] is None


class TestStateRestore:
    """_restore_state() 反序列化测试"""

    def test_restore_all_fields(self, listener):
        saved = {
            'vision_daily_count': 5,
            'vision_daily_date': '2026-07-29',
            'vision_fail_streak': 3,
            'vision_circuit_open_until': 1234567890.5,
            'vision_stats': {'total': 10, 'success': 7, 'fail': 3, 'total_tokens': 500},
            'last_trigger': {'g1': ['at', 'doc1']},
            'lock_set_ts': {'g1': 1000.0},
            'reply_ts': {'g1': 2000.0},
            'last_msg_ts': {'g1': 3000.0},
            'gate_hits': 42,
            'gate_misses': 100,
            'lock_skips': 3,
            'inject_random': 10,
            'inject_at': 32,
            'stats_start': 99999.0,
        }

        listener._restore_state(saved)

        assert listener._vision_daily_count == 5
        assert listener._vision_daily_date == date(2026, 7, 29)
        assert listener._vision_fail_streak == 3
        assert listener._vision_circuit_open_until == 1234567890.5
        assert listener._vision_stats == {'total': 10, 'success': 7, 'fail': 3, 'total_tokens': 500}
        assert listener._gate_hits == 42
        assert listener._gate_misses == 100
        assert listener._lock_skips == 3
        assert listener._inject_random == 10
        assert listener._inject_at == 32
        assert listener._stats_start == 99999.0

    def test_restore_last_trigger_no_message_chain(self, listener):
        """恢复后 message_chain 为 None"""
        saved = {'last_trigger': {'s1': ['at', 'doc123']}}
        listener._restore_state(saved)
        assert listener._last_trigger == {'s1': ('at', 'doc123', None)}

    def test_restore_missing_fields_get_defaults(self, listener):
        listener._restore_state({})
        assert listener._vision_daily_count == 0
        assert listener._gate_hits == 0
        assert listener._last_trigger == {}
        assert listener._lock_set_ts == {}
        assert listener._stats_start != 0  # 用当前时间填充

    def test_restore_invalid_date_fallback(self, listener):
        listener._restore_state({'vision_daily_date': None})
        assert listener._vision_daily_date is not None  # 回退到今天

    def test_restore_empty_last_trigger(self, listener):
        saved = {'last_trigger': {}}
        listener._restore_state(saved)
        assert listener._last_trigger == {}


class TestStateStore:
    """StateStore 底层读写测试"""

    def test_save_calls_set_plugin_storage(self, listener):
        store = listener._state_store
        state = {'gate_hits': 42}
        import asyncio
        asyncio.run(store.save(state))
        store.plugin.set_plugin_storage.assert_called_once()
        call_args = store.plugin.set_plugin_storage.call_args
        assert call_args[0][0] == 'silent_observer_state'
        saved_bytes = call_args[0][1]
        decoded = json.loads(saved_bytes.decode('utf-8'))
        assert decoded == state

    def test_load_returns_parsed_dict(self, listener):
        store = listener._state_store
        state = {'gate_hits': 42, 'vision_daily_count': 5}
        store.plugin.get_plugin_storage.return_value = json.dumps(state).encode('utf-8')
        import asyncio
        result = asyncio.run(store.load())
        assert result == state

    def test_load_returns_none_when_no_data(self, listener):
        store = listener._state_store
        store.plugin.get_plugin_storage.return_value = None
        import asyncio
        result = asyncio.run(store.load())
        assert result is None

    def test_load_returns_none_on_error(self, listener):
        store = listener._state_store
        store.plugin.get_plugin_storage.side_effect = Exception('storage down')
        import asyncio
        result = asyncio.run(store.load())
        assert result is None

    def test_save_load_round_trip(self, listener):
        """完整 round-trip：collect → save → load → restore → 状态一致"""
        from datetime import date
        listener._gate_hits = 77
        listener._vision_daily_count = 3
        listener._vision_daily_date = date(2026, 7, 28)
        listener._last_trigger = {'g1': ('at', 'doc1', 'mc')}
        listener._lock_set_ts = {'g1': 5000.0}

        store = listener._state_store
        import asyncio

        # Save
        state = listener._collect_state()
        asyncio.run(store.save(state))

        # Verify stored bytes
        saved_bytes = store.plugin.set_plugin_storage.call_args[0][1]
        loaded = json.loads(saved_bytes.decode('utf-8'))

        # Simulate restore: reset listener state, then restore from loaded dict
        listener._gate_hits = 0
        listener._vision_daily_count = 0
        listener._vision_daily_date = None
        listener._last_trigger = {}
        listener._lock_set_ts = {}

        listener._restore_state(loaded)

        assert listener._gate_hits == 77
        assert listener._vision_daily_count == 3
        assert listener._vision_daily_date == date(2026, 7, 28)
        assert listener._last_trigger == {'g1': ('at', 'doc1', None)}
        assert listener._lock_set_ts == {'g1': 5000.0}

    def test_json_serializable(self, listener):
        """_collect_state 输出必须可直接 json.dumps"""
        listener._vision_daily_date = date(2026, 7, 29)
        listener._vision_circuit_open_until = 12345.6
        state = listener._collect_state()
        encoded = json.dumps(state, ensure_ascii=False)
        decoded = json.loads(encoded)
        assert decoded['vision_daily_date'] == '2026-07-29'
        assert decoded['vision_circuit_open_until'] == 12345.6
